@echo off

:: Zhai Assistant Frontend Service Start Script

echo ========================================
echo        Zhai Assistant Frontend         
echo ========================================

:: Check Python environment
echo Checking Python environment...
python --version >nul 2>nul || (
    echo Error: Python not found. Please install Python 3.7+
    pause
    exit /b 1
)

:: Install dependencies
echo Installing required dependencies...
pip install fastapi uvicorn

:: Start API server
echo Starting backend API server...
echo Server will run on http://localhost:8000
echo API documentation: http://localhost:8000/docs
echo Press Ctrl+C to stop the server

:: Run uvicorn server
python api_server.py

:: Pause to view output
pause