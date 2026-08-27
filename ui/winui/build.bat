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

echo [1/3] building the three CLI tools (embedded as resources / copied
echo        next to the app by the csproj) ...
where make >nul 2>nul
if not errorlevel 1 (
    pushd ..\..
    rem the Makefile targets carry the .exe suffix on Windows
    make ipa2vec.exe vec2ipa.exe vec4ipa.exe
    popd
    if errorlevel 1 exit /b 1
) else (
    for %%t in (ipa2vec vec2ipa vec4ipa) do (
        gcc -O2 -Wall -Wextra -std=c11 -Wno-unused-function -Wno-unused-variable ^
            -Wno-format-truncation -municode -o ..\..\%%t.exe ..\..\src\%%t_main.c
        if errorlevel 1 exit /b 1
    )
)

echo [2/3] building ipa2vec_core.dll ...
gcc -O2 -Wall -Wextra -std=c11 -Wno-unused-function -Wno-unused-variable ^
    -Wno-format-truncation -I..\..\src -shared -o ..\ipa2vec_core.dll core_wrap.c
if errorlevel 1 exit /b 1

echo [3/3] publishing WinUI 3 app ...
"%MSBUILD%" vec4ipa_ui.csproj /restore /p:Configuration=Release /p:Platform=x64 /p:PublishSingleFile=false /t:Publish /v:m
if errorlevel 1 exit /b 1

rem The MRT PriGen output lands in bin\ but publish does not copy the
rem application resources.pri (XAML/XBF lookup and the MRT Core app
rem initialisation need it next to the exe) - copy it explicitly.
copy /y "bin\x64\Release\net9.0-windows10.0.19041.0\win-x64\resources.pri" dist\resources.pri >nul 2>nul
if errorlevel 1 exit /b 1

echo.
echo Done: dist\vec4ipa_ui.exe  (self-contained folder, no install needed)
endlocal
