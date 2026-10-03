"""Compile Core.cs against the real DLL and check the buffer contract.

ui/winui/vec4ipa_ui.csproj cannot be built with the .NET SDK alone -- the
AppxPackage PRI targets live in Visual Studio -- so the managed half of the
WinUI wrapper had no way to be verified while it still truncated every scheme
wider than the compiled 16 axes.

Core.cs itself has no WinUI dependency: it is P/Invoke plus marshalling, so it
compiles against a plain net9.0 console project. That is enough to load both
schemes through the real DLL and assert the round trip, which is exactly the
property the truncation broke:

  * NDim reports the loaded scheme's width, not 16
  * ForwardRaw returns rows of that width
  * the two derived axes survive the call (before the fix they were zero-filled
    or dropped, and nothing said so)

Run: python tools/test_winui_core.py
"""

import io
import re
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
WRAP = os.path.join(ROOT, 'ui', 'winui', 'core_wrap.c')
CORE = os.path.join(ROOT, 'ui', 'winui', 'Core.cs')

PROG = r'''
using System;
using System.Linq;
using Vec4ipaUI;

class P
{
    static int Main(string[] argv)
    {
        try
        {
            Core.SetArgs(argv);
            Console.WriteLine("ndim=" + Core.NDim);
            var names = Core.DimNames;
            Console.WriteLine("names=" + names.Length);
            Console.WriteLine("lastname=" + names[names.Length - 1]);
            var rows = Core.ForwardRaw("sa");
            if (rows == null) { Console.WriteLine("PARSE_FAIL"); return 2; }
            Console.WriteLine("rows=" + rows.Length);
            Console.WriteLine("rowlen=" + rows[0].Length);
            // Print every coordinate of every segment so this can be compared
            // against the CLI. Asserting "the last axis is non-zero" is not
            // enough: a mis-strided wrapper fills the tail with ANOTHER
            // segment's coordinates, which are also non-zero. Only a
            // value-for-value comparison against vec4ipa catches that.
            foreach (var row in rows)
                Console.WriteLine("VEC " + string.Join(" ",
                    row.Select(v => v.ToString("R", System.Globalization.CultureInfo.InvariantCulture))));
            int last = Core.NDim - 1;
            Console.WriteLine("lastval=" + rows[0][last].ToString("F4"));
            foreach (var want in new[] { "constriction_pos", "constriction_gap" })
                Console.WriteLine("has_" + want + "=" + Array.IndexOf(names, want));
            return 0;
        }
        catch (Exception e)
        {
            Console.WriteLine("EXCEPTION: " + e.GetType().Name + ": " + e.Message);
            return 3;
        }
    }
}
'''
CSPROJ = r'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <AssemblyName>coreprobe</AssemblyName>
    <RootNamespace>CoreProbe</RootNamespace>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <NoWarn>CS8509</NoWarn>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Program.cs" />
    <Compile Include="Core.cs" />
  </ItemGroup>
</Project>
'''


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    dll = os.path.join(os.path.dirname(WRAP), 'ipa2vec_core.dll')
    with tempfile.TemporaryDirectory() as td:
        b = sh(['gcc', '-shared', '-O2', '-std=c11', '-Wno-unused-function',
                '-Wno-unused-variable', '-Wno-format-truncation',
                '-I', os.path.join(ROOT, 'src'), '-I', os.path.dirname(WRAP),
                '-o', dll, WRAP], ROOT)
        if b.returncode != 0:
            print('core_wrap.c did not build:\n%s' % b.stderr[-1200:])
            return 1

        io.open(os.path.join(td, 'Program.cs'), 'w', encoding='utf-8').write(PROG)
        io.open(os.path.join(td, 'Core.cs'), 'w', encoding='utf-8').write(
            io.open(CORE, encoding='utf-8').read())
        io.open(os.path.join(td, 'coreprobe.csproj'), 'w',
                encoding='utf-8').write(CSPROJ)

        r = sh(['dotnet', 'build', '-c', 'Release', '-v', 'quiet',
                '-o', os.path.join(td, 'out')], td)
        if r.returncode != 0:
            print('Core.cs did not compile:\n%s' % (r.stdout + r.stderr)[-2500:])
            return 1
        print('Core.cs compiles against the real DLL')

        exe = os.path.join(td, 'out', 'coreprobe.exe')
        if not os.path.exists(exe):
            exe = os.path.join(td, 'out', 'coreprobe')

        fails = []
        for scheme, want_nd, want_derived in (
                ('spec_next.scheme', 16, False),
                ('tongue.scheme', 18, True)):
            r = subprocess.run([exe, '-D', os.path.join(DATA, scheme)],
                               cwd=os.path.dirname(dll), capture_output=True,
                               text=True)
            if r.returncode != 0:
                fails.append('%s: probe exited %d\n%s'
                             % (scheme, r.returncode, r.stderr[-500:]))
                continue
            out = r.stdout.strip()
            vecs = []
            for line in out.splitlines():
                if line.startswith('VEC '):
                    vecs.append([float(x) for x in line[4:].split()])
            print('\n%s\n  %s' % (scheme, out.replace('\n', '\n  ')))
            kv = dict(line.split('=', 1) for line in out.splitlines()
                      if '=' in line and not line.startswith('VEC '))
            if int(kv['ndim']) != want_nd:
                fails.append('%s: NDim is %s, expected %d'
                             % (scheme, kv['ndim'], want_nd))
            if int(kv['rowlen']) != want_nd:
                fails.append('%s: row length %s, expected %d'
                             % (scheme, kv['rowlen'], want_nd))
            if int(kv['names']) != want_nd:
                fails.append('%s: DimNames has %s, expected %d'
                             % (scheme, kv['names'], want_nd))
            if want_derived:
                for a in ('constriction_pos', 'constriction_gap'):
                    if int(kv['has_' + a]) < 0:
                        fails.append('%s: %s missing from DimNames'
                                     % (scheme, a))

            # Cross-check against the CLI. This is what catches a mis-strided
            # wrapper: the tail would hold another segment's coordinates, and
            # no per-axis assertion can tell those from the right ones.
            cli = subprocess.run(
                [os.path.join(ROOT, 'vec4ipa.exe' if os.name == 'nt'
                              else 'vec4ipa'),
                 '-D', os.path.join(DATA, scheme), 'sa'],
                capture_output=True, text=True).stdout
            cli_rows = []
            for line in cli.splitlines():
                m = re.match(r'^\[\d+\]\s+\(([^)]*)\)', line)
                if m:
                    cli_rows.append([float(x) for x in m.group(1).split(',')])
            if len(cli_rows) != len(vecs):
                fails.append('%s: CLI gave %d segments, wrapper %d'
                             % (scheme, len(cli_rows), len(vecs)))
            else:
                for si, (a, b) in enumerate(zip(cli_rows, vecs)):
                    if len(a) != len(b):
                        fails.append('%s: segment %d width %d vs CLI %d'
                                     % (scheme, si, len(b), len(a)))
                        continue
                    for i, (x, y) in enumerate(zip(a, b)):
                        if abs(x - y) > 5e-4:
                            fails.append('%s: segment %d axis %d (%s): '
                                         'wrapper %.4f vs CLI %.4f'
                                         % (scheme, si, i,
                                            kv.get('lastname', '?'), y, x))
                            break

        if fails:
            print('\nFAIL')
            for f in fails:
                print('  - %s' % f)
            return 1
        print('\nPASS: the managed side and the wrapper agree on the loaded '
              "scheme's width, and the derived axes survive.")
        return 0


if __name__ == '__main__':
    sys.exit(main())