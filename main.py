import gui
from cleaning_data import FileCleaner
import os
import json
import sys
import datetime
from PyQt5 import QtGui, QtWidgets
from socket import socket, AF_INET, SOCK_STREAM
import pandas as pd
import threading
import csv
import urllib
from sqlalchemy import create_engine


def sql_connection(db: str):
    """
    Creates SQL connection
    :param db: string, database name
    :return: SQL connection
    """
    conn_str = "DRIVER={SQL Server Native Client 16.0};SERVER=DanielaSRV;DATABASE=" + db + \
               ";UID=dani;PWD=ela;MARS_Connection=Yes;"
    params = urllib.parse.quote_plus(conn_str)
    engine = create_engine("mssql+pyodbc:///?odbc_connect=%s" % params)
    connection = engine.connect()
    return connection


# reads the config file
with open('configs/config.json', 'r') as f:
    config = json.load(f)

HOST = config['host_ip']
PORT = config['port']
ADDRESS = (HOST, PORT)
csv_name = config['commands']
db_name = config['db_name']
hz = config['hz']
tick = 1 / hz

# connects to database
conn = sql_connection(db_name)

# gets the API commands from csv
api_csv = pd.read_csv(f'configs/{csv_name}.csv')
command_list = [x for x in api_csv['command'] if x != '-']

# makes a dictionary out of the variables from excel
var_dict = {}
closing_line = []

for var in api_csv['variable']:
    var_dict[f'{var}'] = 0
    closing_line.append(0)
var_dict['sim_time'] = 0

# global socket
s = socket(AF_INET, SOCK_STREAM)

# creates folder if needed
if not os.path.exists("csv logs"):
    os.makedirs('csv logs')


class Gui(QtWidgets.QMainWindow, gui.GazepointUI):
    def __init__(self):
        """
        This class derived from PyQT is instantiating the main dialog window of the GUI.
        """
        super(Gui, self).__init__()
        self.setup_ui(self)

        self.labelHost.setText(f'{HOST}:{PORT}')

        self.buttonSave.setDisabled(True)
        self.buttonFeed.setDisabled(True)
        self.buttonAck.setDisabled(True)

        self.buttonSet.clicked.connect(self._get_file_name)
        self.lineResultName.returnPressed.connect(self._get_file_name)
        self.buttonAck.clicked.connect(self._open_socket)
        self.buttonFeed.clicked.connect(self._call_data_feed)
        self.buttonSave.clicked.connect(self._save_exit)

    def _get_file_name(self) -> None:
        """
        Called when the 'set' button is pressed in order to get the wanted file name
        returns as long as the name is not empty, has invalid characters or already exists
        (underscore _ is valid)
        :return:
        """
        self.name = self.lineResultName.text()
        name_check = ''.join(self.name.split('_'))

        # cheat code for testing
        if self.name == 'caitvi':
            print('--- cheat code activated :) ---')
            conn.close()
            app.quit()
            FileCleaner(input('file_name\n> '), int(input('hz\n> ')))

        if self.name == '' or os.path.exists(f'csv logs/{self.name}.csv') or not name_check.isalnum():
            self.labelFileExists.setText('Choose a different name')
            self.labelFileExists.setstylesheet("font-weight: bold; color: red; font-size: 13pt")
        else:
            print(f'--- file name {self.name} ---')
            self.lineResultName.setDisabled(True)
            self.buttonSet.setDisabled(True)
            self.buttonAck.setDisabled(False)
            self.labelFileExists.setText(f'Name set: {self.name}.csv')
            self.labelFileExists.setstyleSheet('font-weight: bold; color: green; font-size: 13pt')
        return

    def _open_socket(self) -> None:
        """
        Makes sure the TCP socket can connect and sends the wanted API commands
        Also instantiating the class responsible for the thread passing the data
        calls for the next function automatically
        :return:
        """
        try:
            s.connect(ADDRESS)
        except ConnectionRefusedError:
            self.labelFileExists.setText('Failed: open Gazepoint Control')
            self.labelFileExists.setStyleSheet('font-weight: bold; color: red; font-size: i5pt')
            return

        self.feeder = Feeder(self.name, True)

        for command in command_list:
            s.send(str.encode(f'<SET ID="{command}" STATE="1" />\r\n'))
        s.send(str.encode('<SET ID="ENABLE_SEND_DATA" STATE="1" />\r\n'))
        print('--- socket opened ---')
        self._acknowledge(False)

    def _acknowledge(self, ack: bool) -> None:
        """
        Makes sure all the API commands were sent and acknowledged properly
        :param ack: bool: are the commands acknowledged?
        :return:
        """
        ack_counter = 0
        while not ack:
            data = bytes.decode(s.recv(1024))
            if data.find('ACK') == 1:
                ack_counter += data.count('ACK')
                print(f"--- acknowledged {ack_counter} out of {len(command_list) + 1} commands ---")
            if ack_counter == len(command_list) + 1:
                self.buttonAck.setDisabled(True)
                self.buttonFeed.setDisabled(False)
                self.imgAck.setPixmap(QtGui.QPixmap("icons/v.png"))
                ack = True

    def _call_data_feed(self) -> None:
        """
        Calls for a thread of the data feeder setup function
        :return:
        """
        self.buttonSave.setDisabled(False)
        self.buttonFeed.setDisabled(True)

        self.feeder.paused = False
        threading.Thread(target=self.feeder.setup_thread).start()

    def _save_exit(self) -> None:
        """
        Reads the CSV file written by the write_csv function and removes any invalid
        rows, then exits the GUI and starts the cleaning, analyzing and visualizing processes
        :return:
        """
        self.feeder.paused = True
        ui.hide()
        convert_df = pd.read_csv(f'csv logs/{self.name}.csv')
        convert_df = convert_df[convert_df.iloc[:, 1] != 0]
        convert_df = convert_df[(convert_df['LPMM'] <= 6) & (convert_df['RPMM'] <= 6)]
        convert_df = convert_df.reset_index(drop=True)
        convert_df.to_csv(f'csv logs/{self.name}.csv', index_label='CNT')
        print(f'---=== file saved, dataframe size: {len(convert_df.index)} ===---')
        conn.close()
        app.quit()
        # start cleaning
        FileCleaner(self.name, hz)


class Feeder:
    def __init__(self, file_name: str, paused: bool):
        """
        This class recieves the data and writes it to a file on a different thread so the GUI
        can continue being responsive
        :param file_name: string
        :param paused: bool
        """
        self.file_name = file_name
        self.paused = paused

    def setup_thread(self) -> None:
        """
        As the name might suggest, this is the function that starts in a different thread
        and calls both the generator and writing functions
        To sync the data with the current simulator time we take the last sim_time from the SQL table
        :return:
        """
        time_query = f"""
        SELECT TOP (1) sim_time AS st
        FROM dis.inGameTime
        ORDER BY WorldTime DESC
        """
        time_result = pd.read_sql_query(time_query, conn)
        if not time_result.empty:
            var_dict['sim_time'] = time_result['st'][0]

        self.write_csv(self.decoder_gen())

    def decoder_gen(self, buffer='') -> str:
        """
        This is a generator function that listens to the TCP stream and yields full messages
        :param buffer: string
        :return: string: a full message
        """
        self.starting_time = datetime.datetime.now()
        print(f'---=== started inserting messages at {self.starting_time} ===---')
        while not self.paused:
            data = bytes.decode(s.recv(1024))
            buffer += data
            while '\n' in buffer:
                lines = buffer.split('\n')
                buffer = lines.pop()
                for line in lines:
                    yield line

    def write_csv(self, generator) -> None:
        """
        The function that iterates over the full messages and writes a roe to the CSV
        :param generator: generator function
        :return:
        """
        file = open(f'csv logs/{self.file_name}.csv', 'w+', newline='')
        writer = csv.writer(file)
        writer.writerow(var_dict.keys())

        for message in generator:
            string_list = message.split(' ')[1:-1]

            for string in string_list:
                key = string.split("=")[0]
                if key in var_dict.keys():
                    var_dict[f'{key}'] = string.split('\"')[1]

            var_dict['sim_time'] += tick
            writer.writerow(var_dict.values())

        writer.writerow(closing_line)
        file.close()
        print(f'---=== time elapsed inserting {datetime.datetime.now() - self.starting_time} ===---')


# start GUI
app = QtWidgets.QApplication(sys.argv)
ui = Gui()
ui.show()
app.exec_()
