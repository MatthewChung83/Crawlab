@echo off
chcp 65001 > nul
cd /d D:\Crawlab
call venv\Scripts\activate.bat
python run_crawler.py %*
