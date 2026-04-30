@echo off
echo ==============================================
echo   Batch Reactor Edge AI - Control Script
echo ==============================================
echo.
echo Select an option:
echo 1) Start everything with Docker
echo 2) Stop everything
echo 3) Run Python Unit Tests
echo 4) Exit
echo.

set /p choice="Enter choice [1-4]: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto test
if "%choice%"=="4" goto end

:start
echo Starting Docker containers...
docker-compose up --build
goto end

:stop
echo Stopping Docker containers...
docker-compose down
goto end

:test
echo Running Python tests...
cd python
python test_anomaly_detector.py
cd ..
pause
goto end

:end
