Gazepoint
===
This program uses the Gazepoint sensor and API to make CSV files of the data remotely, 
as well as cleaning, analyzing and producing visuals automatically.
---
Running
===
Add a `config.json` file to the `configs` directory;
```json
"host_ip": "IP",
"port": PORT,
"commands": "COMMAND CSV NANE.csv",
"db_name": "DATABASE NAME",
"hz": 60/150
```

`host_ip` is the computer with the Gazepoint sensor and software <br>
`port` is the port defined in Gazepoint control <br>
`excel_name` is the command excel file <br>
`db_name` is the database name <br>
`hz` is the number of messages sent per second from the sensor (60/150) <br>
Run `main.py` (or build an EXE, instructions below)
---
Build EXE - PyInstaller
===
There is a script `build_exe.py` to create a new EXE if needed. Just run it and 3 new items will appear: <br>
* The `EXE` directory containing the distributable file
* The `Build` directory responsible for creating the dist file
* A `.spec` file with the dist file specifications <br>
The EXE can be moved to a different path, but make sure that the needed assets directories `configs`, `icons`, are with the dist file. 
---
Setup and steps
===
A computer with the sensor and the Gazepoint Control software must be set up and open, a manual calibration is needed for each
new person after which accurate data can be fed to a csv file. <br>
Once the main process is done and the GUI is exited, the following classes are called in the background chronologically: <br>
* FileCleaner from `cleaning_data.py`
* CognitiveLoad from `cognitive_load.py`
* Exportvisuals from `export_visuals.py` <br>
---
Dictionary:
===
**disparity** = pupil disparity <br>
**bkmin** = number of blinks in the past 60 seconds <br>
**lpp** left pupil size 3 seconds averaged <br>
**rpp** = right pupil size 3 seconds averaged <br>
**l_ica** = number of peaks for the left pupil per second for the past 5 seconds <br>
**r_ica** = number of peaks for the right pupil per second for the past 5 seconds <br>