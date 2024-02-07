import sys
import pandas as pd
import matplotlib.pyplot as plt
from scipy.ndimage.filters import gaussian_filter
from PIL import Image
import numpy as np
from math import floor
import os
import datetime


class ExportVisuals:
    def __init__(self, file_name: str, hz: int):
        """
        This class is initiated after the analyzing process is finished
        the main results are the path and heatmap images, graphs often need individual altering to look presentable
        exports everything to a folder with the same name as the file name
        :param file_name: string
        :param hz: int
        """
        print('\n---=== EXPORTING VISUALS ===---')
        self.exp_starting_time = datetime.datetime.now()
        self.file_name = file_name
        self.hz = hz
        self.screen_w, self.screen_h = 1920, 1080
        self.raw_df = pd.read_csv(f'analysis/cognitive load logs/{self.file_name}_load.csv')
        self.fix_df = pd.read_csv(f'analysis/cognitive load logs/{self.file_name}_fixations.csv')
        print(f'---=== finished loading {self.file_name} fixations ===---')
        print(f'--- data length {len(self.raw_df)} ---')

        # creates the folders
        if not os.path.exists('analysis/img/'):
            os.makedirs('analysis/img')
        if not os.path.exists(f'analysis/img/{self.file_name}'):
            os.makedirs(f'analysis/img/{self.file_name}')

        self.gaze_path()
        self.heatmap()
        self.pupil_dilation_graph()
        self.disparity_graph()

        print(f'---=== time elapsed visualizing {datetime.datetime.now() - self.exp_starting_time}')
        sys.exit()

    def gaze_path(self) -> None:
        """
        Draws the gaze path with lines
        :return:
        """
        df = self.raw_df[(self.raw_df["BPOGX"].between(0, 1)) & (self.raw_df['BPOGY'].between(0, 1)) &
                         (self.raw_df['BPOGV'] == 1)]

        bpogx_list = df['BPOGX'].tolist()
        bpogy_list = df['BPOGY'].tolist()

        plt.figure(dpi=300)
        plt.axis('off')

        for i in range(0, len(bpogx_list), self.hz):
            try:
                plt.plot(bpogx_list[i-self.hz:1], bpogy_list[i-self.hz:i],
                         c='indigo', alpha=0.03, solid_capstyle='butt')
            except IndexError:
                break

        plt.savefig(f'analysis/img/{self.file_name}/{self.file_name}_gaze_path.png', transparent=False)
        plt.show(block=False)
        plt.close()
        im = Image.open(f'analysis/img/{self.file_name}/{self.file_name}_gaze_path.png')
        out = im.rotate(180)
        out.save(f'analysis/img/{self.file_name}/{self.file_name}_gaze_path.png')

        print('--- finished gaze path ---')

    def heatmap(self) -> None:
        """
        The first time a data file is made this function creates a .npy array file alongside the JSON that contains
        a 2D matrix representing the places looked at across the screen
        Then loads that array and draws a heatmap based on that matrix
        :return:
        """
        if not os.path.exists(f'analysis/jsons/{self.file_name}_heatmap.npy'):
            print('--- creating npy matrix ---')
            data = np.zeros([self.screen_h, self.screen_w])
            heat_df = self.raw_df[self.raw_df['BPOGV'] != 0 &
                                  self.raw_df['BPOGX'].between(0, 1) & self.raw_df['BPOGY'].between(0, 1)]
            heat_df = heat_df.reset_index(drop=True)

            for i in range(len(heat_df)):
                y, x = floor(heat_df.at[i, 'BPOGY'] * self.screen_h), floor(heat_df.at[i, 'BPOGX'] * self.screen_w)
                try:
                    data[y, x] += 1
                except IndexError:
                    pass
            np.save(f'analysis/jsons/{self.file_name}_heatmap.npy', data)
        else:
            data = np.load(f'analysis/jsons/{self.file_name}_heatmap.npy')

        data[data <= 1] = 0

        smooth_data = gaussian_filter(data, sigma=2)
        masked_data = np.ma.masked_where(smooth_data == 0, smooth_data)

        plt.figure(dpi=300)
        plt.imshow(masked_data, cmap='jet')

        plt.axis('off')
        plt.savefig(f'analysis/img/{self.file_name}/{self.file_name}_heat_map.png', transparent=True)
        plt.show(block=False)
        plt.close()

        print('--- finished heatmap ---')

    def pupil_dilation_graph(self) -> None:
        """
        Basic line graph
        :return:
        """
        series = self.raw_df[['lpp', 'rpp' 'sim_time']].dropna()
        mean_val = 6666
        series['bpp'] = series[['lpp', 'rpp']].mean(axis=1)
        data = series['bpp'].rolling(mean_val).mean()

        plt.figure(figsize=(50, 20), dpi=300)
        plt.plot(series['sim_time'], data, c='indigo', alpha=0.5)

        plt.savefig(f'analysis/img/{self.file_name}/{self.file_name}_pupil_dilation.png')
        plt.show(block=False)
        plt.close()

        print('--- finished pupil dilation graph ---')

    def disparity_graph(self) -> None:
        """
        Basic line graph
        :return:
        """
        series = self.raw_df[['disparity', 'sim_time']].dropna()

        maximum_val, mean_val = 0.13, 150
        series = series[series['disparity'] <= maximum_val]
        data = series['disparity'].rolling(mean_val).mean()

        plt.figure(figsize=(50, 20), dpi=300)
        plt.plot(series['sim_time'], data, c='indigo', alpha=0.5)

        plt.savefig(f'analysis/img/{self.file_name}/{self.file_name}_disparity.png')
        plt.show(block=False)
        plt.close()
        print('--- finished disparity graph ---')


if __name__ == '__main__':
    # this is here mainly because the graphs need to be modified for the final report
    # so, change the rolling window and ceilings and produce the graphs again to your liking :)
    # or make new graphs with the data idk go wild
    ExportVisuals(input('file_name\n> '), int(input('hz\n> ')))
