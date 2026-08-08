@echo off
rem Build ui/vec4ipa_ui.exe (single-file full-featured GUI).
rem Requires MinGW-w64 (gcc + windres) in PATH.

cd /d "%~dp0"

windres app.rc -O coff -o app.res || exit /b 1

gcc -O2 -Wall -Wextra -std=c11 -Wno-unused-function -Wno-unused-variable ^
    -mwindows -municode -I..\src -o vec4ipa_ui.exe vec4ipa_ui.c app.res ^
    -lcomctl32 -lcomdlg32 -lshell32 -lole32 || exit /b 1

echo Built ui\vec4ipa_ui.exe
