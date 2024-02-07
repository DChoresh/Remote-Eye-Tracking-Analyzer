from cognitive_load import CognitiveLoad

import pandas as pd
import math
import json
import os
from datetime import datetime

# dictionary of valid groups
gaze_groups_dict = {}

# creates folders if needed
if not os.path.exists('analysis/jsons'):
    os.makedirs('analysis/jsons')
if not os.path.exists('analysis/clean logs'):
    os.makedirs('analysis/clean logs')


def bridge_formula(mms: float, mme: float, r: int, tr: int) -> float:
    """
    Bridges the pupil dilation before and after a blink
    :param mms: float: pupil MM at the start
    :param mme: float: pupil MM at the end
    :param r: int: the current blink row
    :param tr: int: total blink rows
    :return: float: correct dilation
    """
    result = mms + (r * (mme - mms) / tr)
    return result


def add_to_dict(key: int, start: float, end: float, blinks: list, s_i: int, e_i: int) -> None:
    """
    Responsible for the JSON detailing basic info of the group as well as blink times
    :param key: int: the number of the group
    :param start: float: starting time
    :param end: float: ending time
    :param blinks: list: blink times, each blink gets an id
    :param s_i: int: starting index (CNT)
    :param e_i: int: ending index (CNT)
    :return:
    """
    blinks_dict = {}
    for i, blink in enumerate(blinks):
        if start < blink < end:
            blinks_dict[f'blink_{i}'] = blink

    gaze_groups_dict[f'group_{key}'] = {
        "start": start,
        "end": end,
        "start_CNT": s_i,
        "end_CNT": e_i,
        "length": end - start,
        "blinks": blinks_dict
    }


class FileCleaner:
    def __init__(self, file_name: str, hz: int):
        """
        This class is initiated right after the data stream is stopped and cleans, trims and categorizes
        the data in a new CSV file as well as a JSON file of the gaze groups' properties
        :param file_name: string
        :param hz: int
        """
        print('\n---=== CLEANING DATA ===---')
        self.clean_starting_time = datetime.now()
        self.file_name = file_name
        self.hz = hz
        self.df = pd.read_csv(f'csv logs/{self.file_name}.csv')
        print('---=== finished loading file (cleaning) ===---')
        self.index = 1
        self.output_df = pd.DataFrame()
        self.blink_trim_cnt_list = []
        self.blink_trim = int(math.ceil(0.05 * self.hz))
        self.edge_trim = int(2 * self.hz)
        self.blink_starting_index = int()
        self.blinks_list = []

        # start cleaning
        self.get_gaze_groups()

    def get_gaze_groups(self, searching=True) -> None:
        """
        This is the main action of the class, we iterate over the file searching for valid data,
        when we encounter a break we check if it's a blink. when a longer break is found we
        add the group to the dictionary only if it's above 10 seconds, and when we reach the end of the file
        the save function is called and the next process class (analyzing) is initiated.
        :param searching: bool
        :return:
        """
        starting_index = self.index + self.edge_trim
        self.blinks_list = []
        while searching:
            try:
                if self.df.at[self.index, 'LPMMV'] == 1 or self.df.at[self.index, "RPMMV"] == 1:
                    self.index += 1
                    continue
            except KeyError:
                self.save()
            else:
                if self.is_blink():
                    continue
                else:
                    if self.blink_starting_index - starting_index >= 10 * self.hz:
                        self.output_df = \
                            self.output_df.append(self.df.iloc[starting_index:self.blink_starting_index])
                        add_to_dict(
                            len(gaze_groups_dict.keys()) + 1,
                            self.df.at[starting_index, 'sim_time'],
                            self.df.at[self.blink_starting_index - 1, 'sim_time'],
                            self.blinks_list,
                            starting_index, self.blink_starting_index - 1)
                    try:
                        self.get_gaze_groups()
                    except IndexError:
                        self.save()

    def is_blink(self, blink_rows=0) -> bool:
        """
        This function checks if a break is a blink or not, while gathering more info
        :param blink_rows: int
        :return: bool: blink is true
        """
        while self.df.at[self.index, 'LPMMV'] == 0 and self.df.at[self.index, 'RPMMV'] == 0:
            blink_rows += 1
            self.index += 1
        else:
            self.blink_starting_index = self.index - blink_rows
            if blink_rows <= (self.hz * 0.5) + 1:
                self.blinks_list.append(self.df.at[self.blink_starting_index, 'sim_time'])

                for x in range(1, self.blink_trim + 1):
                    self.blink_trim_cnt_list.append(self.blink_starting_index - x)
                    self.blink_trim_cnt_list.append((self.index + x) - 1)

                self.bridge_blink_eyemm(blink_rows, self.blink_starting_index, self.index)
                return True
            else:
                return False

    def bridge_blink_eyemm(self, rows: int, start: float, end: float) -> None:
        """
        If a blink is detected this function bridges the pupil dilation while the eye was closed
        :param rows: int: how many rows is the blink
        :param start: float: starting time
        :param end: float: ending time
        :return:
        """
        lpmm_start = self.df.at[start, "LPMM"]
        rpmm_start = self.df.at[start, "RPMM"]

        new_end = end
        lpmm_end = self.df.at[end, "LPMM"]
        while lpmm_end == lpmm_start:
            new_end += 1
            lpmm_end = self.df.at[new_end, "LPMM"]

        new_end = end
        rpmm_end = self.df.at[end, "RPMM"]
        while rpmm_end == rpmm_start:
            new_end += 1
            rpmm_end = self.df.iloc[new_end]["RPMM"]

        for n in range(1, rows + 1):
            l_result = bridge_formula(lpmm_start, lpmm_end, n, rows)
            self.df.at[start + n, 'LPMM'] = l_result
            r_result = bridge_formula(rpmm_start, rpmm_end, n, rows)
            self.df.at[start + n, 'RPMM'] = r_result

    def save(self) -> None:
        """
        Saves the clean file and a JSON to their designated directories, trims a couple of rows before and after
        each blink in the file and initiates the analyzing class
        :return:
        """
        with open(f'analysis/jsons/{self.file_name}.json', 'w+') as f:
            json.dump(gaze_groups_dict, f, indent=2, separators=(',', ': '))
        print('--- saved json ---')
        self.output_df = self.output_df[~self.output_df['CNT'].isin(self.blink_trim_cnt_list)]
        print("--- trimmed around blinks ---")
        self.output_df.to_csv(f'analysis/clean logs/{self.file_name}_clean.csv', index=False)
        print('--- saved clean csv ---')
        print(f'---=== time elapsed cleaning = {datetime.now() - self.clean_starting_time} ===---')

        # start cognitive load
        CognitiveLoad(self.file_name, self.hz)


if __name__ == '__main__':
    # independent running
    FileCleaner(input('file_name\n> '), int(input('hz\n> ')))
