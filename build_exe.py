from PyInstaller.__main__ import run
from datetime import datetime

# creates the EXE distributable file

starting_time = datetime.now()

script = 'main.py'
args = [script, '--onefile', '-n Gazepoint', '--distpath=EXE/', '--hidden-import=pyodbc']

console = input('add a cmd console? y/n\n> ')
if console != 'y':
    args.append('--noconsole')

run(args)

print(f'--== BUILT EXE time elapsed {datetime.now() - starting_time} ==--')

