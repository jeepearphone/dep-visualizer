@echo off
set "PYTHON=python"
if not defined VIRTUAL_ENV (
    where py >nul 2>nul && set "PYTHON=py -3"
)
if "%~1"=="test" (
    %PYTHON% -m unittest discover -s tests -v
) else (
    %PYTHON% -m src.main %*
)
exit /b %errorlevel%
