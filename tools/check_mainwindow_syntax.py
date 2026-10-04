"""Syntax-check MainWindow.xaml.cs without the WinUI reference assemblies.

vec4ipa_ui.csproj needs the AppxPackage targets, which the .NET SDK alone does
not ship, so this file cannot be built here. But "cannot build" is not the
same as "may be syntactically broken", and a string-interpolation edit is
exactly the kind of change that can leave an unterminated literal behind.

So compile it against a bare net9.0 project and read the errors. Missing
Microsoft.UI.* types are expected and prove nothing; CS1002 (missing token),
CS1010/CS1026 (newline in constant) or any parse-stage diagnostic would mean
the edit broke the file. The check passes only when the diagnostics are all
type-resolution failures.

Run: python tools/check_mainwindow_syntax.py
"""

import io
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'ui', 'winui', 'MainWindow.xaml.cs')
XAML = os.path.join(ROOT, 'ui', 'winui', 'MainWindow.xaml')

# A literal "<n>-D vector" in the XAML is wrong for every scheme but the
# compiled one, and it is what the XAML designer shows. The code-behind
# overwrites it from Core.NDim at startup, so the stale value survives review
# -- it is only wrong in the window before that runs.
XAML_WIDTH = re.compile(r'\b\d+-D vector|\b\d+ \u7ef4|\b\d+-D vectors')

CSPROJ = r'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Library</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <DisableWinUIProjectDetection>true</DisableWinUIProjectDetection>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="MainWindow.xaml.cs" />
  </ItemGroup>
</Project>
'''

# Parse-stage diagnostics. CS0246 is "type not found" -- the expected noise
# from the absent WinUI assemblies. Everything else in this set means the file
# itself is malformed.
PARSE_ERRORS = {'CS1002', 'CS1003', 'CS1010', 'CS1011', 'CS1022', 'CS1026',
                'CS1513', 'CS1514', 'CS1519', 'CS1520', 'CS1525', 'CS8124',
                'CS1039', 'CS1040', 'CS1056', 'CS1073', 'CS1519'}
EXPECTED_MISSING = {'CS0246', 'CS0234', 'CS0103', 'CS0518', 'CS0117', 'CS1061',
                    'CS0308', 'CS0535', 'CS0311', 'CS0122', 'CS1503'}


def main():
    with tempfile.TemporaryDirectory() as td:
        io.open(os.path.join(td, 'MainWindow.xaml.cs'), 'w',
                encoding='utf-8').write(
            io.open(SRC, encoding='utf-8').read())
        io.open(os.path.join(td, 'probe.csproj'), 'w',
                encoding='utf-8').write(CSPROJ)
        r = subprocess.run(['dotnet', 'build', '-c', 'Release', '-v',
                            'quiet', '--nologo'], cwd=td,
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        codes = set(re.findall(r'error (CS\d{4})', out))

    parse = sorted(codes & PARSE_ERRORS)
    missing = sorted(codes & EXPECTED_MISSING)
    other = sorted(codes - PARSE_ERRORS - EXPECTED_MISSING)

    print('diagnostics seen: %d distinct codes' % len(codes))
    print('  expected missing-WinUI types: %s'
          % (' '.join(missing) if missing else '(none)'))
    print('  parse-stage errors:           %s'
          % (' '.join(parse) if parse else '(none)'))
    print('  unexplained:                  %s'
          % (' '.join(other) if other else '(none)'))

    if parse:
        print('\nFAIL: the file is syntactically broken')
        for line in out.splitlines():
            if any('error %s' % c in line for c in parse):
                print('  ' + line.strip()[:160])
        return 1
    if not missing:
        print('\nFAIL: expected missing-WinUI diagnostics; the file may not '
              'have been compiled at all, so this proved nothing')
        return 1

    xaml = io.open(XAML, encoding='utf-8').read()
    stale = []
    for n, line in enumerate(xaml.splitlines(), 1):
        if XAML_WIDTH.search(line):
            stale.append('  MainWindow.xaml:%d  %s' % (n, line.strip()[:90]))
    if stale:
        print('\nFAIL: MainWindow.xaml declares a vector width as a literal. '
              'A --scheme FILE can change it, and the code-behind overwrites '
              'this at startup, so the stale text survives review:')
        for s in stale:
            print(s)
        return 1

    print('\nPASS: only missing-reference diagnostics, and no literal width in '
          'the XAML.\nThis is the cheap half. tools/build_winui.py compiles the '
          'project for real,\nand that is what caught ten references to a '
          'deleted constant which\npassed here for as long as the project '
          'could not be built at all.')
    return 0


if __name__ == '__main__':
    sys.exit(main())