@echo off
setlocal
cd /d "%~dp0"

call build.bat build --release
if errorlevel 1 exit /b 1

if exist dist rmdir /s /q dist
mkdir dist
mkdir dist\fonts
mkdir dist\Assets
mkdir dist\tools

copy /y "target\release\vec4ipa-ui.exe" "dist\" >nul
for %%f in (target\release\*.dll target\release\*.pri target\release\*.manifest) do (
    if exist "%%f" copy /y "%%f" "dist\" >nul
)
rem Windows App SDK ships localized MUI files and a Microsoft.UI.Xaml resource folder.
for /d %%d in (target\release\*) do (
    if /i not "%%~nxd"==".fingerprint" if /i not "%%~nxd"=="build" if /i not "%%~nxd"=="deps" if /i not "%%~nxd"=="examples" if /i not "%%~nxd"=="incremental" (
        xcopy /E /I /Y "%%d" "dist\%%~nxd" >nul
    )
)
copy /y "..\fonts\GentiumBookPlus-Regular.ttf" "dist\fonts\" >nul
copy /y "..\vec_ipa.ico" "dist\" >nul
copy /y "..\assets\final_ink.png" "dist\Assets\" >nul

set "TOOLS=..\.."
for %%t in (ipa2vec.exe vec2ipa.exe vec4ipa.exe) do (
    if not exist "%TOOLS%\%%t" (
        echo ERROR: missing bundled tool %TOOLS%\%%t
        exit /b 1
    )
    copy /y "%TOOLS%\%%t" "dist\tools\" >nul
)

echo.
echo Done: ui\rust\dist\vec4ipa-ui.exe
endlocal
