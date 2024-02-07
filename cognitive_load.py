from export_visuals import ExportVisuals

import datetime
import os
import json
import pandas as pd
from math import sqrt, ceil
from numpy import nan, repeat
import pywt

# creates folders if needed
if not os.path.exists("analysis/cognitive load logs/"):
    os.makedirs('analysis/cognitive load logs')


def calc_distance(x1: float, x2: float, y1: float, y2: float) -> float:
    """
    Basic distance formula
    :param x1: float
    :param x2: float
    :param y1: float
    :param y2: float
    :return: float: resulting distance
    """
    distance = sqrt((x2-x1)**2 + (y2-y1)*2)
    return distance


class CognitiveLoad:
    def __init__(self, file_name: str, hz: int):
        """
        Initiated after the cleaning process is done and creates two files:
        1. the data combined with cognitive load values (pupil disparity, blinks per minute,
        smoothed pupil dilation and average ICA for both pupils seperatly)
        2. A file of all fixations
        The main action of this process happens here, iterating over every gaze group and calculating those values
        :param file_name: string
        :param hz: int
        """
        print('\n---=== ANALYZING DATA ===---')
        self.cog_starting_time = datetime.datetime.now()
        self.file_name = file_name
        self.hz = hz
        self.screen_w, self.screen_h = 1920, 1080
        self.minute_index = 60 * self.hz
        self.pupil_minimums = []
        self.df = pd.read_csv(f'analysis/clean logs/{file_name}_clean.csv')
        print('---=== finished loading file (cognitive) ===---')
        self.df.insert(1, 'disparity', nan)
        self.df.insert(2, 'bkmin', 0)
        self.df.insert(3, 'lpp', nan)
        self.df.insert(4, 'rpp', nan)
        self.df.insert(5, 'l_ica', nan)
        self.df.insert(6, 'r_ica', nan)
        with open(f'analysis/jsons/{self.file_name}.json', 'r') as f:
            self.config = json.load(f)
        print('---=== finished loading json (cognitive) ===---')

        # fixation deviation index (fdi) relevant only for 150 hz, equivalent to roughly 30ms
        # and degrees to number of pixels that count as a fixation area (2.5%: 48px and 27px)
        self.fdi = 5
        self.x_degree, self.y_degree = ceil(0.025*self.screen_w), ceil(0.025*self.screen_h)
        self.fixation_df = pd.DataFrame(columns=['starting time', 'duration', 'x', 'y', 'deviations'])

        for group in self.config.items():
            self.length = group[1]['length']
            starting_cnt = group[1]['start_CNT']
            end_cnt = group[1]['end_CNT']

            while starting_cnt >= 0:
                try:
                    starting_index = self.df.index[self.df['CNT'] == starting_cnt].tolist()[0]
                    break
                except IndexError:
                    starting_cnt += 1
            while end_cnt >= 0:
                try:
                    end_index = self.df.index[self.df['CNT'] == end_cnt].tolist()[0]
                    break
                except IndexError:
                    end_cnt -= 1

            print(f'--- {starting_index}, {end_index} CNTS({starting_cnt}, {end_cnt}) ---')

            self.pupil_dilation(starting_index + 3 * self.hz, end_index)
            self.disparity(starting_index, end_index)

            if self.length > 60:
                blink_times_list = list(group[1]['blinks'].values())
                self.blink_rate(starting_index * self.minute_index, end_index, blink_times_list)

            if self.hz >= 150:
                self.ica(starting_index, end_index)
                self.fixations(starting_index, end_index)

        self.div_pupil_minimum()
        self.save_file()

    def pupil_dilation(self, s_i: int, e_i: int) -> None:
        """
        Smooths each pupil's dilation with a sliding mean window of 3 seconds
        :param s_i: int: starting index
        :param e_i: int: ending index
        :return:
        """
        while s_i <= e_i:
            three_s_before = s_i - (3 * self.hz)
            sliced_df = self.df[three_s_before:s_i]

            left_average = sliced_df['LPMM'].mean()
            right_average = sliced_df['RPMM'].mean()

            self.df.at[s_i, 'lpp'] = left_average
            self.df.at[s_i, 'rpp'] = right_average

            s_i += 1

    def blink_rate(self, s_i: int, e_i: int, bk_times: list) -> None:
        """
        If the gaze group is longer than 60 seconds we check the blink rate
        :param s_i: int: starting index
        :param e_i: int: ending index
        :param bk_times: list: all blink times
        :return:
        """
        while s_i <= e_i:
            minute_before_index = s_i - self.minute_index
            time_now = self.df.at[s_i, 'sim_time']
            time_before = self.df.at[minute_before_index, 'sim_time']
            bk_per_min = len([n for n in bk_times if time_before < n < time_now])
            self.df.at[s_i, 'bkmin'] = bk_per_min

            s_i += 1

    def disparity(self, s_i: int, e_i: int) -> None:
        """
        Calculates the distance between pupils
        :param s_i: int: starting index
        :param e_i: int: ending index
        :return:
        """
        while s_i <= e_i:
            if self.df.at[s_i, 'LPOGV'] == 1 and self.df.at[s_i, 'RPOGV'] == 1:
                self.df.at[s_i, 'disparity'] = calc_distance(
                    self.df.at[s_i, 'LPOGX'], self.df.at[s_i, 'RPOGX'],
                    self.df.at[s_i, 'LPOGY'], self.df.at[s_i, 'RPOGY'])

            s_i += 1

    def ica(self, s_i: int, e_i: int) -> None:
        """
        What is ICA (independent component analysis) you ask. well.
        At high rates such as 150/s, we can see out pupils have little jumps in dilation
        using the DWT (discrete wavelength transformation) function we find those jumps and count them per second
        with a sliding window of 5 seconds
        :param s_i: int: starting index
        :param e_i: int: ending index
        :return:
        """
        series = self.df.loc[s_i:e_i, ['LPMM', 'RPMM']]

        series['LPMM'] = series['LPMM'].rolling(2).mean()
        series['RPMM'] = series['RPMM'].rolling(2).mean()

        cd_df = pd.DataFrame(columns=['left_cd', 'right_cd'])
        (left_cA, left_cD) = pywt.dwt(series['LPMM'], 'db32')
        (right_cA, right_cD) = pywt.dwt(series['RPMM'], 'db32')
        cd_df['left_cd'], cd_df['right_cd'] = left_cD, right_cD
        cd_df['left_cd_b'], cd_df['right_cd_b'] = cd_df['left_cd'] >= 0.069, cd_df['right_cd'] >= 0.069
        cd_df['left_cd_b'], cd_df['right_cd_b'] = cd_df['left_cd_b'].astype(int), cd_df['right_cd_b'].astype(int)

        double_df = pd.DataFrame()
        double_df['doubled_left'] = repeat(cd_df['left_cd_b'], 2)
        double_df['doubled_right'] = repeat(cd_df['right_cd_b'], 2)
        double_df = double_df.reset_index(drop=True)

        double_df['l_res'] = double_df['doubled_left'].rolling(self.hz*5).sum()
        double_df['r_res'] = double_df['doubled_right'].rolling(self.hz*5).sum()
        # divide by 2 because the 1's are doubled, and divide by 5 to get rate/second for last 5 seconds
        double_df['l_res'] = double_df['l_res'] / 10
        double_df['r_res'] = double_df['r_res'] / 10

        self.df.loc[s_i:e_i, 'l_ica'] = double_df.loc[:e_i-s_i, 'l_res'].values
        self.df.loc[s_i:e_i, 'r_ica'] = double_df.loc[:e_i-s_i, 'r_res'].values

    def fixations(self, s_i: int, e_i: int) -> None:
        """
        Calculates fixations, when out eyes stay in a certain area of the screen for some time
        takes note of short deviations outside this area
        :param s_i: int: starting index
        :param e_i: int: ending index
        :return:
        """
        duration = 0
        deviations = 0
        dist = 1
        while s_i <= e_i:
            x, y = self.df.at[s_i, 'BPOGX'] * self.screen_w, self.df.at[s_i, 'BPOGY'] * self.screen_h
            new_fix = False
            while not new_fix:
                try:
                    x_a, y_a = self.df.at[s_i + dist, 'BPOGX'] * self.screen_w, \
                               self.df.at[s_i + dist, 'BPOGY'] * self.screen_h
                    if abs(x_a - x) <= self.x_degree and abs(y_a - y) <= self.y_degree:
                        duration += 1/self.hz
                        dist += 1
                    else:
                        x_n, y_n = self.df.at[s_i + self.fdi, 'BPOGX'] * self.screen_w, \
                                   self.df.at[s_i + self.fdi, 'BPOGY'] * self.screen_h
                        if abs(x_n - x) <= self.x_degree and abs(y_n - y) <= self.y_degree:
                            duration += self.fdi * (1/self.hz)
                            dist += self.fdi
                            s_i += self.fdi
                            deviations += 1
                        else:
                            if duration >= 0.133:
                                starting_time = self.df.at[s_i, 'sim_time'] - duration
                                self.fixation_df.loc[len(self.fixation_df.index)] = \
                                    [starting_time, duration, x, y, deviations]
                            duration = 0
                            deviations = 0
                            dist = 0
                            break
                except KeyError:
                    break
            s_i += 1

    def div_pupil_minimum(self) -> None:
        """
        To know if someone is under cognitive stress we need to compare the pupil dilation to their resting value
        Since each person is different, these rest values are compared to ourselves
        we get the minimum from the first 3 minutes of gazing and divide everything else by that
        :return:
        """
        three_min = 3 * self.minute_index
        three_min_sliced_df = self.df[:three_min]

        left_minimum = three_min_sliced_df['lpp'].min()
        right_minimum = three_min_sliced_df['rpp'].min()

        self.df['lpp'] /= left_minimum
        self.df['rpp'] /= right_minimum

    def save_file(self) -> None:
        """
        Saves the files and initiates the next class, visualizations
        :return:
        """
        self.df.to_csv(f'analysis/cognitive load logs/{self.file_name}_load.csv', index=False)
        print('--- saved load csv ---')
        self.fixation_df = self.fixation_df[(self.fixation_df['x'].between(0, self.screen_w)) &
                                            (self.fixation_df['y'].between(0, self.screen_h))]
        self.fixation_df.reset.index(drop=True)
        self.fixation_df.to_csv(f'analysis/cognitive load logs/{self.file_name}_fixations.csv', index_label='id')
        print('--- saved fixation csv ---')

        print(f'---=== time elapsed analyzing {datetime.datetime.now() - self.cog_starting_time} ===---')
        ExportVisuals(self.file_name, self.hz)


if __name__ == '__main__':
    # independent running
    CognitiveLoad(input('file_name\n> '), int(input('hz\n> ')))
