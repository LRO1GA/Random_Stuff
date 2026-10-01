@echo off
setlocal enabledelayedexpansion

echo Batch File to delete non-shipment files for OSS Scan....
:: Last update 06-09-26 - LRO1GA
timeout /t 1 >nul

:: 1. Fetching target folder at the beginning
set /p TARGET_DIR=Please Enter the local path to your SW or Repository Workspace : 
echo Preparing: %TARGET_DIR%
echo.

::List of folders to always be deleted
set "EXCLUDE_FOLDERS=tst stubs stub doc sim tmp"

echo =========================================================================
echo                       OSS Helper GUI
echo =========================================================================
echo Target: "%TARGET_DIR%"
echo =========================================================================
echo [1] Full Processing
echo [2] Start from Step 2  (Delete non .c/.h files)
echo [3] Start from Step 3  (Delete folders %EXCLUDE_FOLDERS%)
echo [4] Start from Step 4  (Delete Empty folders)
echo [5] Cancel
echo =========================================================================
choice /c 12345 /m "Choose an option:"

set "START_STEP=%errorlevel%"

if %START_STEP% equ 5 goto :cancel_operation

:: Fetch date and time in secure format (AAAA-MM-DD_HHMMSS) - wmic is removed on newer Windows, use PowerShell instead
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "dt=%%I"
set "YYYY=%dt:~0,4%"
set "MM=%dt:~4,2%"
set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%"
set "Min=%dt:~10,2%"
set "Sec=%dt:~12,2%"

:: Report name definition
set "REPORT_NAME=Summary_%YYYY%-%MM%-%DD%_%HH%%Min%%Sec%.txt"
set "TEMP_REPORT=%TEMP%\%REPORT_NAME%"

:: =========================================================================
:: System Protection Checks
:: =========================================================================
:: Error - Empty target directory
set "TARGET_DIR=%TARGET_DIR:"=%"
if "%TARGET_DIR%"=="" (
    echo [ERROR] Path TARGET_DIR is empty. Please enter a valid path.
    goto :cancel_operation
)

:: Error - Target directory does not exist
if not exist "%TARGET_DIR%" (
    echo [ERROR] Path TARGET_DIR does not exist: "%TARGET_DIR%"
    goto :cancel_operation
)
:: Normalize Target directory (If a relative path was introduced)
for %%I in ("%TARGET_DIR%") do set "TARGET_DIR=%%~fI"

::Ensure TARGET_DIR does not end in inverted slash 
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"

:: Sanity check 1: Block root folders from being processed (C:, D:)
if "%TARGET_DIR:~2%"=="" (
    echo [WARNING] You have provided a root path ^("%TARGET_DIR%"^).
    echo For System safety, the script cannot be executed in root folders, Please enter a valid path.
    goto :cancel_operation
)

:: Sanity check 2: Block critical folders from being processed
if /i "%TARGET_DIR%"=="%SystemRoot%" goto :protected_sys
if /i "%TARGET_DIR%"=="%SystemDrive%\Windows" goto :protected_sys
if /i "%TARGET_DIR%"=="%ProgramFiles%" goto :protected_sys
if /i "%TARGET_DIR%"=="%ProgramFiles(x86)%" goto :protected_sys
if /i "%TARGET_DIR%"=="%SystemDrive%\Users" goto :protected_sys

:: =========================================================================
:: Main Application - Prepare OSS Package in Legacy projects
:: =========================================================================
:: .bat source directory
set "SCRIPT_DIR=%~dp0"

:: Map a free drive letter to TARGET_DIR so deeply nested paths stay under the 260-char MAX_PATH limit
set "ORIGINAL_TARGET_DIR=%TARGET_DIR%"
set "SUBST_DRIVE="
for %%L in (Z Y X W V U T S R Q P O N M) do (
    if not defined SUBST_DRIVE if not exist "%%L:\" (
        subst %%L: "%TARGET_DIR%" >nul 2>&1
        if not errorlevel 1 set "SUBST_DRIVE=%%L:"
    )
)

if defined SUBST_DRIVE (
    echo Mapped "%TARGET_DIR%" to %SUBST_DRIVE% to avoid long-path errors.
    set "TARGET_DIR=%SUBST_DRIVE%"
) else (
    echo [WARNING] Could not map a free drive letter. Continuing with the full path - long path errors may still occur.
)
echo.

:: Jump to the selected step
if %START_STEP% equ 2 goto :step2
if %START_STEP% equ 3 goto :step3
if %START_STEP% equ 4 goto :step4

:: === File count at the beginning ===
echo Calculating total files...
set "INITIAL_COUNT=0"
for /f %%A in ('dir "%TARGET_DIR%" /b /s /a-d 2^>nul ^| find /c /v ""') do set "INITIAL_COUNT=%%A"
echo TOTAL FILES: %INITIAL_COUNT%
echo.

:step2
:: 2. Erasing anything that's not .C or .H
set "LAST_DIR="
echo Deleting files...
timeout /t 3 >nul
for /r "%TARGET_DIR%" %%F in (*) do (
    :: Fetch current directory
    set "CURRENT_FILE_DIR=%%~dpF"

    :: Check if the directory has changed
    if not "!CURRENT_FILE_DIR!"=="!LAST_DIR!" (
        set "LAST_DIR=!CURRENT_FILE_DIR!"
        
        :: Clean and set the relative path to be printed in the console
        set "CLEAN_DIR=!CURRENT_FILE_DIR!"
        if "!CLEAN_DIR:~-1!"=="\" set "CLEAN_DIR=!CLEAN_DIR:~0,-1!"
        set "RELATIVE_DIR=!CLEAN_DIR:%TARGET_DIR%=\!"
        set "RELATIVE_DIR=!RELATIVE_DIR:\\=\!"
        
        if "!RELATIVE_DIR!"=="" (
            echo Currently in Root folder...
        ) else (
            echo Analyzing: .!RELATIVE_DIR!
        )
    )

    :: Erase all files except .c or .h silently
    if /i not "%%~xF"==".c" if /i not "%%~xF"==".h" (
        del /f /q "%%F" 2>nul
    )

)
::Erase the terminal for the next step
cls

:step3
:: 3. Removing unnecessary folders
echo.
echo Removing unnecessary folders ...
for /d /r "%TARGET_DIR%" %%D in (%EXCLUDE_FOLDERS%) do (
    if exist "%%D" (
        set "FULL_DIR=%%D"
        set "RELATIVE_DIR=!FULL_DIR:%TARGET_DIR%=\!"
        set "RELATIVE_DIR=!RELATIVE_DIR:\\=\!"
        
        echo Deleting: .!RELATIVE_DIR!
        rd /s /q "%%D" 2>nul
    )
)

:step4
:: 4. Erase remaining empty folders
echo Deleting remaining empty folders...
set "LAST_EMPTY_DIR="

:loop
set "FOUND_EMPTY=0"
for /f "delims=" %%d in ('dir /ad /b /s "%TARGET_DIR%" 2^>nul') do (
    dir /a /b "%%d" | findstr . >nul
    if errorlevel 1 (
        :: Get the relative path and print it when deleting a folder
        set "CURRENT_EMPTY_DIR=%%~dpd"
        
        if not "!CURRENT_EMPTY_DIR!"=="!LAST_EMPTY_DIR!" (
            set "LAST_EMPTY_DIR=!CURRENT_EMPTY_DIR!"
            
            set "CLEAN_DIR=!CURRENT_EMPTY_DIR!"
            if "!CLEAN_DIR:~-1!"=="\" set "CLEAN_DIR=!CLEAN_DIR:~0,-1!"
            set "RELATIVE_DIR=!CLEAN_DIR:%TARGET_DIR%=\!"
            set "RELATIVE_DIR=!RELATIVE_DIR:\\=\!"
            
            if "!RELATIVE_DIR!"=="" (
                echo Currently in Root folder...
            ) else (
                echo Deleting: .!RELATIVE_DIR!
            )
		)
		
		rd "%%d" 2^>nul
		set "FOUND_EMPTY=1"
	)
)

:: Go back to the loop if there is still an empty folder
if "!FOUND_EMPTY!"=="1" goto loop

::Erase the termninal for the next step
cls

:: 5. Report Generation
:: === File count at the end ===
echo.
echo Calculating remaining files...
set "FINAL_COUNT=0"
for /f %%A in ('dir "%TARGET_DIR%" /b /s /a-d 2^>nul ^| find /c /v ""') do set "FINAL_COUNT=%%A"
echo TOTAL FILES (.c y .h): %FINAL_COUNT%
timeout /t 3 >nul

echo.
echo Generating report...
echo === File === > "%TEMP_REPORT%"
echo Date: %date% %time% >> "%TEMP_REPORT%"
echo Source Folder: %ORIGINAL_TARGET_DIR% >> "%TEMP_REPORT%"
echo Starting files: %INITIAL_COUNT% >> "%TEMP_REPORT%"
echo Remaining files: %FINAL_COUNT% >> "%TEMP_REPORT%"
echo -------------------------------------------- >> "%TEMP_REPORT%"
echo. >> "%TEMP_REPORT%"
timeout /t 3 >nul

dir "%TARGET_DIR%" /b /s /a-d >> "%TEMP_REPORT%" 2>nul

:: 5. Moving the report
echo.
echo Moving the report into the scripts location...
move /y "%TEMP_REPORT%" "%SCRIPT_DIR%%REPORT_NAME%" >nul

:: Remove the temporary drive mapping now that processing is finished
if defined SUBST_DRIVE subst %SUBST_DRIVE% /d >nul 2>&1

echo Report "%REPORT_NAME%" is in: %SCRIPT_DIR%
echo All Done!

pause
goto :eof

:: =========================================================================
:: Exit routines
:: =========================================================================
:protected_sys
echo [BLOCKED] The path provided is protected:
echo "%TARGET_DIR%"
echo Process stopped to prevent damages to the system.
pause
goto :eof

:cancel_operation
echo.
echo [CANCELLED] Operation stopped by user or invalid path.
pause
goto :eof