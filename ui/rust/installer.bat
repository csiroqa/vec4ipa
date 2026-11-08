@echo off
setlocal
cd /d "%~dp0"

set "HEADER=..\..\src\ipa2vec_core.h"
if not exist "%HEADER%" (
    echo ERROR: cannot find %HEADER%
    exit /b 1
)

set "APPVERSION="
for /f "tokens=3" %%v in ('findstr /c:"#define IPA2VEC_VERSION" "%HEADER%"') do set "APPVERSION=%%~v"
if not defined APPVERSION (
    echo ERROR: cannot parse IPA2VEC_VERSION from %HEADER%
    exit /b 1
)

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo ERROR: Inno Setup 6 ISCC.exe not found
    echo Install Inno Setup 6 or set the path in this script.
    exit /b 1
)

call package.bat
if errorlevel 1 exit /b 1

if not exist installer mkdir installer

echo Building installer for version %APPVERSION%
"%ISCC%" /DAppVersion=%APPVERSION% installer.iss
if errorlevel 1 exit /b 1

echo.
echo Done: ui\rust\installer\vec4ipa-setup-%APPVERSION%.exe
endlocal
