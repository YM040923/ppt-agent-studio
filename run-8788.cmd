@echo off
setlocal
set PPT_AGENT_PORT=8788
set PPT_AGENT_DATA_DIR=%~dp0data
cd /d %~dp0
python -m app.main
