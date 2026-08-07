@echo off
rem Build the WinUI 3 front-end (ui/winui/) plus the core DLL.
rem Requires: MinGW gcc (core DLL), VS Build Tools 2022 MSBuild,
rem            .NET SDK 9.
rem
rem   build.bat            build Release x64
rem   build.bat clean      remove build output

cd /d "%~dp0"

if /i "%~1"=="clean" (
    rmdir /s /q bin obj 2>nul
    del /q ..\ipa2vec_core.dll 2>nul
    exit /b 0
)

echo [1/2] building ipa2vec_core.dll ...
gcc -O2 -std=c11 -Wno-unused-function -Wno-unused-variable ^
    -I..\..\src -shared -o ..\ipa2vec_core.dll core_wrap.c
if errorlevel 1 exit /b 1

echo [2/2] building WinUI 3 app ...
set MSBUILD="C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
%MSBUILD% ipa2vec_ui.csproj /restore /p:Configuration=Release /p:Platform=x64 /v:m
if errorlevel 1 exit /b 1

echo Done: bin\x64\Release\net9.0-windows10.0.19041.0\win-x64\ipa2vec_ui.exe
