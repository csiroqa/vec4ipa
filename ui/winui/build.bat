@echo off
setlocal
rem Build the WinUI 3 front-end (ui/winui/) plus the core DLL.
rem
rem Requires: MinGW-w64 gcc  (core DLL)
rem            VS Build Tools 2022 (MSBuild) and .NET SDK 9 (app)
rem
rem   build.bat            publish self-contained app to dist\ (default)
rem   build.bat clean      remove build output

cd /d "%~dp0"

if /i "%~1"=="clean" (
    rmdir /s /q bin obj dist 2>nul
    del /q ..\ipa2vec_core.dll 2>nul
    exit /b 0
)

rem ---- locate MSBuild (VS Build Tools / Visual Studio) ----
set "MSBUILD="
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe" (
    set "MSBUILD=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
)
if not defined MSBUILD if exist "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe" (
    set "MSBUILD=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
)
if not defined MSBUILD if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" (
    for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.Component.MSBuild -find MSBuild\**\Bin\MSBuild.exe`) do (
        if not defined MSBUILD set "MSBUILD=%%i"
    )
)
if not defined MSBUILD (
    echo ERROR: MSBuild not found. Install VS Build Tools 2022 ^(MSBuild Tools workload^).
    exit /b 1
)

where gcc >nul 2>nul
if errorlevel 1 (
    echo ERROR: gcc not found. Install MinGW-w64.
    exit /b 1
)

echo [1/2] building ipa2vec_core.dll ...
gcc -O2 -std=c11 -Wno-unused-function -Wno-unused-variable ^
    -I..\..\src -shared -o ..\ipa2vec_core.dll core_wrap.c
if errorlevel 1 exit /b 1

echo [2/2] publishing WinUI 3 app ...
"%MSBUILD%" vec4ipa_ui.csproj /restore /p:Configuration=Release /p:Platform=x64 /p:PublishSingleFile=false /t:Publish /v:m
if errorlevel 1 exit /b 1

echo.
echo Done: dist\vec4ipa_ui.exe  (self-contained folder, no install needed)
endlocal
