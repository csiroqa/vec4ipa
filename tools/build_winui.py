"""Build the WinUI front-end for real, and prove it can fail.

This was a documented blocker: vec4ipa_ui.csproj needs the AppxPackage PRI
targets, which `dotnet build` cannot reach, so the C# half of the WinUI
wrapper had never been compiled here -- and the gap hid a real defect.
`Core.NDIM` was deleted when the buffer contract became runtime, only
Core.cs was searched, and ten references in MainWindow.xaml.cs were left
behind. They compiled fine here for as long as the build could not run, and
the real compiler failed on the first attempt.

Which is the argument for this check existing at all: the syntax-only check
(check_mainwindow_syntax.py) compiles the file with the WinUI references
deliberately absent, so a missing member is not a parse-stage error. Both
guards passed while the project did not compile.

Run: python tools/build_winui.py [--skip-if-unavailable]

MSBuild comes from Visual Studio Build Tools; `dotnet build` cannot load
Microsoft.Build.Packaging.Pri.Tasks.dll, which ships with MSBuild and not
with the .NET SDK.
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, 'ui', 'winui', 'vec4ipa_ui.csproj')

CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\amd64\MSBuild.exe',
    r'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\amd64\MSBuild.exe',
    r'C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\amd64\MSBuild.exe',
]


def find_msbuild():
    for c in CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-if-unavailable', action='store_true')
    args = ap.parse_args()

    msb = find_msbuild()
    if not msb:
        msg = ('no Visual Studio MSBuild found; the WinUI project cannot be '
               'built (dotnet build cannot load the PRI tasks)')
        if args.skip_if_unavailable:
            print('SKIP: %s' % msg)
            return 0
        print(msg)
        return 1

    r = subprocess.run([msb, os.path.basename(PROJ),
                        '-p:Configuration=Release', '-p:Platform=x64',
                        '-v:minimal', '-m'],
                       cwd=os.path.dirname(PROJ), capture_output=True,
                       text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
    if r.returncode != 0:
        print('WinUI build FAILED')
        for ln in tail:
            print('  ' + ln)
        return 1
    print('WinUI built: %s' % [l for l in tail if '->' in l][-1].strip())
    return 0


if __name__ == '__main__':
    sys.exit(main())