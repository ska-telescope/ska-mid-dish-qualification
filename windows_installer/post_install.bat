@echo off
REM Enable delayed environment variable expansion
SETLOCAL

REM Get the user's home directory
set "userHome=%USERPROFILE%"

REM Define the source and target paths
set "sourcePath=%~dp0_internal\disq.ini"
set "targetPath=%userHome%\AppData\Local\SKAO\disq\disq.ini"

REM Check if the target ini file does not exist
if not exist "%targetPath%" (
    REM Create the target directory if it doesn't exist
    mkdir "%~dp0..\AppData\Local\SKAO\disq" 2>nul >nul

    REM Ensure the target directory exists
    if not exist "%userHome%\AppData\Local\SKAO\disq" (
        mkdir "%userHome%\AppData\Local\SKAO\disq"
    )

    REM Copy the ini file to the target location
    copy "%sourcePath%" "%targetPath%" /Y
)

REM End localization of environment changes
ENDLOCAL
