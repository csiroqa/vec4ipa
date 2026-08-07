using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace Vec4ipaUI
{
    /// <summary>P/Invoke bindings for ipa2vec_core.dll (MinGW, built from
    /// ui/winui/core_wrap.c + src/ipa2vec_core.h).</summary>
    internal static class Core
    {
        public const int NDIM = 16;
        public const int MAX_TOKS = 512;
        public const int MAX_KBTEXT = 65536;

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_forward(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string str,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder err, int errsz,
            [Out] double[] vecs, [Out] int[] airstream, IntPtr names);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_reverse(
            [In] double[] v, int width,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_query(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string sym,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_cons(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_cons_np(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_vowels(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_mods(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_tones(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr ipa2v_version();

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr ipa2v_docs();

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_set_args(int n, string[] argv);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_modules(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_table(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_stats(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_weights(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        /// <summary>Apply CLI-style settings (school modules, --width).</summary>
        public static void SetArgs(string[] args) => ipa2v_set_args(args.Length, args);

        public static string[] Modules()
        {
            var sb = new StringBuilder(4096);
            ipa2v_modules(sb, 4096);
            return sb.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries);
        }

        public static string Table()
        {
            var sb = new StringBuilder(131072);
            ipa2v_table(sb, 131072);
            return sb.ToString();
        }

        public static string Stats()
        {
            var sb = new StringBuilder(2048);
            ipa2v_stats(sb, 2048);
            return sb.ToString();
        }

        public static string Weights()
        {
            var sb = new StringBuilder(8192);
            ipa2v_weights(sb, 8192);
            return sb.ToString();
        }

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_load_metric(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string path);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_weights_effective(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_modules_full(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_distance(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string a,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string b,
            out double d);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_ir(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string str,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_json(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string str,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_ir_export(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string str,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string base_,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder err, int errsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_dim_names(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_vowel_positions(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_cons_pos(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_mod_tiers(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        /// <summary>--metric FILE: returns null on success, error text otherwise.</summary>
        public static string? LoadMetric(string path)
            => ipa2v_load_metric(path) == 0 ? null : $"failed to load: {path}";

        public static string WeightsEffective()
        {
            var sb = new StringBuilder(8192);
            ipa2v_weights_effective(sb, 8192);
            return sb.ToString();
        }

        public static string ModulesFull()
        {
            var sb = new StringBuilder(131072);
            ipa2v_modules_full(sb, 131072);
            return sb.ToString();
        }

        public static string? Distance(string a, string b)
        {
            if (ipa2v_distance(a, b, out double d) == 0)
                return $"{d:F4}";
            return "need exactly one segment per argument";
        }

        public static string Ir(string str)
        {
            var sb = new StringBuilder(65536);
            ipa2v_ir(str, sb, 65536);
            return sb.ToString();
        }

        public static string Json(string str)
        {
            var sb = new StringBuilder(65536);
            ipa2v_json(str, sb, 65536);
            return sb.ToString();
        }

        /// <summary>-x: export layer files; returns null on success or error text.</summary>
        public static string? IrExport(string str, string baseName)
        {
            var err = new StringBuilder(256);
            return ipa2v_ir_export(str, baseName, err, 256) == 0
                ? null : err.ToString();
        }

        private static string[]? _dimNames;

        public static string[] DimNames
        {
            get
            {
                if (_dimNames == null)
                {
                    var sb = new StringBuilder(1024);
                    ipa2v_dim_names(sb, 1024);
                    _dimNames = sb.ToString().Split('\n',
                        StringSplitOptions.RemoveEmptyEntries);
                }
                return _dimNames;
            }
        }

        /// <summary>Raw segment vectors (each NDIM long) for an IPA string.</summary>
        public static double[][]? ForwardRaw(string ipa)
        {
            var err = new StringBuilder(256);
            var vecs = new double[NDIM * MAX_TOKS];
            var air = new int[MAX_TOKS];
            int n = ipa2v_forward(ipa, err, 256, vecs, air, IntPtr.Zero);
            if (n < 0) return null;
            var rows = new double[n][];
            for (int s = 0; s < n; s++)
            {
                rows[s] = new double[NDIM];
                Array.Copy(vecs, s * NDIM, rows[s], 0, NDIM);
            }
            return rows;
        }

        /// <summary>Named-feature rendering: tt_pos=0.55, ...</summary>
        public static string? ForwardNamed(string ipa)
        {
            var rows = ForwardRaw(ipa);
            if (rows == null) return null;
            var names = DimNames;
            var sb = new StringBuilder();
            for (int s = 0; s < rows.Length; s++)
            {
                sb.Append($"[{s}] (");
                for (int i = 0; i < NDIM; i++)
                    sb.Append(i == 0 ? $"{names[i]}={rows[s][i]:F4}"
                                     : $", {names[i]}={rows[s][i]:F4}");
                sb.AppendLine(")");
            }
            return sb.ToString();
        }

        /// <summary>Vowel keyboard positions: sym -> (row, col).</summary>
        public static Dictionary<string, (int Row, int Col)> VowelPositions()
        {
            var sb = new StringBuilder(4096);
            ipa2v_vowel_positions(sb, 4096);
            var map = new Dictionary<string, (int, int)>();
            foreach (var line in sb.ToString().Split('\n',
                         StringSplitOptions.RemoveEmptyEntries))
            {
                var p = line.Split('\t');
                if (p.Length == 3 && int.TryParse(p[1], out var r) &&
                    int.TryParse(p[2], out var c))
                    map[p[0]] = (r, c);
            }
            return map;
        }

        /// <summary>Consonant place of articulation: sym -> tt_pos (0 front .. 1 back).</summary>
        public static Dictionary<string, double> ConsPositions()
        {
            var sb = new StringBuilder(8192);
            ipa2v_kb_cons_pos(sb, 8192);
            var map = new Dictionary<string, double>();
            foreach (var line in sb.ToString().Split('\n',
                         StringSplitOptions.RemoveEmptyEntries))
            {
                var p = line.Split('\t');
                if (p.Length == 2 && double.TryParse(p[1],
                        System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture,
                        out var d))
                    map[p[0]] = d;
            }
            return map;
        }

        /// <summary>Modifier tiers: sym -> tier index.</summary>
        public static Dictionary<string, int> ModTiers()
        {
            var sb = new StringBuilder(8192);
            ipa2v_kb_mod_tiers(sb, 8192);
            var map = new Dictionary<string, int>();
            foreach (var line in sb.ToString().Split('\n',
                         StringSplitOptions.RemoveEmptyEntries))
            {
                var p = line.Split('\t');
                if (p.Length == 2 && int.TryParse(p[1], out var t))
                    map[p[0]] = t;
            }
            return map;
        }

        public static string? Forward(string ipa, out string? error)
        {
            error = null;
            var err = new StringBuilder(256);
            var vecs = new double[NDIM * MAX_TOKS];
            var air = new int[MAX_TOKS];
            int n = ipa2v_forward(ipa, err, 256, vecs, air, IntPtr.Zero);
            if (n < 0) { error = err.ToString(); return null; }
            var sb = new StringBuilder();
            for (int s = 0; s < n; s++)
            {
                sb.Append($"[{s}] (");
                for (int i = 0; i < NDIM; i++)
                    sb.Append(i == 0 ? $"{vecs[s * NDIM + i]:F4}"
                                     : $", {vecs[s * NDIM + i]:F4}");
                sb.AppendLine(")");
            }
            return sb.ToString();
        }

        public static string? Reverse(string vectorText, int width)
        {
            var parts = vectorText
                .Trim()
                .TrimStart('(', '[')
                .TrimEnd(')', ']')
                .Split(new[] { ',', ' ', '\t', ';' },
                    StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != NDIM)
                return "I need 16 comma-separated numbers (I found " +
                       parts.Length + ").\n"
                       + "Example: 0,0,0.55,1,0,0,0,0,0,0,0.9,0,0,0,0,1";
            var v = new double[NDIM];
            for (int i = 0; i < NDIM; i++)
            {
                if (!double.TryParse(parts[i], System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out v[i]))
                    return $"Value #{i + 1} ('{parts[i]}') is not a number.";
                if (!double.IsFinite(v[i]))
                    return $"Value #{i + 1} ('{parts[i]}') must be finite " +
                           "(no NaN or Infinity).";
            }
            var sb = new StringBuilder(512);
            ipa2v_reverse(v, width, sb, 512);
            return sb.ToString();
        }

        public static string Query(string sym)
        {
            var sb = new StringBuilder(512);
            ipa2v_query(sym, sb, 512);
            return sb.ToString();
        }

        public static string[] KeyboardCons() => KbList(ipa2v_kb_cons);
        public static string[] KeyboardConsNp() => KbList(ipa2v_kb_cons_np);
        public static string[] KeyboardVowels() => KbList(ipa2v_kb_vowels);
        public static string[] KeyboardMods() => KbList(ipa2v_kb_mods);
        public static string[] KeyboardTones() => KbList(ipa2v_kb_tones);

        private static string[] KbList(Func<StringBuilder, int, int> fn)
        {
            var sb = new StringBuilder(MAX_KBTEXT);
            fn(sb, MAX_KBTEXT);
            return sb.ToString().Split('\n',
                StringSplitOptions.RemoveEmptyEntries);
        }

        public static string Version
        {
            get
            {
                IntPtr p = ipa2v_version();
                return p == IntPtr.Zero ? "?" : Marshal.PtrToStringUTF8(p) ?? "?";
            }
        }

        public static string Docs
        {
            get
            {
                IntPtr p = ipa2v_docs();
                return p == IntPtr.Zero ? "(no documentation)" :
                    Marshal.PtrToStringUTF8(p) ?? "(no documentation)";
            }
        }
    }
}
