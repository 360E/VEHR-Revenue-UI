@echo off
cd /d c:\VEHR
if not exist logs mkdir logs
.\.venv313\Scripts\python.exe -m scripts.era_extract.watcher >> logs\era_watcher.log 2>&1
