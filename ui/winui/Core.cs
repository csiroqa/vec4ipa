using System;
using System.Collections.Generic;
using System.Linq;
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
        private static extern int ipa2v_forward_tone(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string str,
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder err, int errsz,
            [Out] double[] vecs, [Out] double[] tone, [Out] int[] tkind);

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

        /// <summary>Named-feature rendering: tongue_tip_pos=0.55, ...</summary>
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

        /// <summary>Consonant place of articulation: sym -> tongue_tip_pos (0 front .. 1 back).</summary>
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
            var tone = new double[9 * MAX_TOKS];
            var tkind = new int[3 * MAX_TOKS];
            int n = ipa2v_forward_tone(ipa, err, 256, vecs, tone, tkind);
            if (n < 0) { error = err.ToString(); return null; }
            var sb = new StringBuilder();
            for (int s = 0; s < n; s++)
            {
                sb.Append($"[{s}] (");
                for (int i = 0; i < NDIM; i++)
                    sb.Append(i == 0 ? $"{vecs[s * NDIM + i]:F4}"
                                     : $", {vecs[s * NDIM + i]:F4}");
                sb.Append(')');
                string t = ToneText(tone, tkind, s);
                if (t.Length > 0)
                    sb.Append("  tone: ").Append(t);
                sb.AppendLine();
            }
            return sb.ToString();
        }

        /* same rendering as the CLI print_tone: (v) / (v,v) / (v,v,v) for
         * tone[0]/[1], (u,g,c) for the 3-D tone[2] */
        private static string ToneText(double[] tone, int[] tkind, int s)
        {
            var sb = new StringBuilder();
            for (int g = 0; g < 3; g++)
            {
                if (tkind[s * 3 + g] == 0) continue;
                double t0 = tone[s * 9 + g * 3 + 0];
                double t1 = tone[s * 9 + g * 3 + 1];
                double t2 = tone[s * 9 + g * 3 + 2];
                if (double.IsNaN(t0)) continue;
                if (g == 2)
                {
                    sb.Append('(');
                    sb.Append(double.IsNaN(t0) ? "0" : t0.ToString("0.#"));
                    sb.Append(',');
                    sb.Append(double.IsNaN(t1) ? "0" : t1.ToString("0.#"));
                    sb.Append(',');
                    sb.Append(double.IsNaN(t2) ? "0" : t2.ToString("0.#"));
                    sb.Append(')');
                    continue;
                }
                bool b2 = double.IsNaN(t2);
                int nvals = b2 ? (Math.Abs(t0 - t1) < 1e-9 ? 1 : 2) : 3;
                sb.Append('(');
                for (int k = 0; k < nvals; k++)
                {
                    double v = tone[s * 9 + g * 3 + k];
                    sb.Append(k == 0 ? v.ToString("0.#")
                                     : $", {v.ToString("0.#")}");
                }
                sb.Append(')');
            }
            return sb.ToString();
        }

        /// <summary>Example vector repeated in the error hints.</summary>
        private const string VectorExample =
            "-0.45,0,0,0,1,0,0,0,0,0.9,0,0,0,0,0,1";

        /// <summary>Warning suffix in Chinese (UI display language for
        /// these messages is zh; do not localise into English).</summary>
        private const string ToneWarnPrefix = "  （警告：";
        private const string ToneWarnSuffix = "）";

        /// <summary>Chinese warning body (see ToneWarnPrefix).</summary>
        private const string NegativeToneWarn = "存在负数，忽略处理";

        public static string? Reverse(string vectorText, int width)
        {
            /* 1) "?" stands for an empty vector - normalise to () */
            string input = vectorText.Trim();
            string norm = System.Text.RegularExpressions.Regex.Replace(
                input, @"\?", "()");

            /* 2) extract every parenthesised group in order */
            var groups = new List<string>();
            string bare = System.Text.RegularExpressions.Regex.Replace(
                norm, @"\(([^()]*)\)", m =>
                {
                    groups.Add(m.Groups[1].Value.Trim());
                    return " ";
                });

            /* 3) if the leading 16 numbers are not wrapped in (),
             * wrap them implicitly as the first group */
            var bareNums = bare.Split(new[] { ',', ' ', '\t', ';' },
                StringSplitOptions.RemoveEmptyEntries);
            if (bareNums.Length > 0)
            {
                if (bareNums.Length != NDIM)
                    return $"I need 16 comma-separated numbers (I found " +
                           $"{bareNums.Length} outside the groups).\n" +
                           "Example: " + VectorExample;
                groups.Insert(0, string.Join(",", bareNums));
            }

            /* 4) parse in order: first group = main vector (16 numbers);
             * following groups fill tone slots 0/1/2 by position - empty
             * groups (() or ?) keep their slot but produce no symbols */
            double[]? v = null;
            double[][] toneSlots = new double[3][];
            int tonePos = 0;
            foreach (var g in groups)
            {
                var nums = new List<double>();
                foreach (var tok in g.Split(',',
                             StringSplitOptions.RemoveEmptyEntries))
                {
                    if (double.TryParse(tok,
                            System.Globalization.NumberStyles.Float,
                            System.Globalization.CultureInfo.InvariantCulture,
                            out var d))
                        nums.Add(d);
                }
                if (v == null && nums.Count == NDIM)
                {
                    v = nums.ToArray();
                    continue;
                }
                if (v == null && nums.Count > 3) continue;
                if (tonePos >= 3) break;
                if (nums.Count > 0 && nums.Count <= 3)
                {
                    toneSlots[tonePos] = nums.ToArray();
                    tonePos++;
                }
            }
            var (toneStr, toneWarn) = ToneSymbols(toneSlots);
            if (v == null)
            {
                if (groups.All(string.IsNullOrEmpty))
                    return "No vector given - type 16 comma-separated numbers,\n" +
                           "e.g. " + VectorExample;
                /* no main vector, but tone groups exist: echo the tones */
                if (toneStr.Length > 0)
                    return toneStr + (toneWarn.Length > 0
                        ? ToneWarnPrefix + toneWarn + ToneWarnSuffix : "");
                return "I need 16 comma-separated numbers.\n" +
                       "Example: " + VectorExample;
            }
            for (int i = 0; i < NDIM; i++)
                if (!double.IsFinite(v[i]))
                    return $"Value #{i + 1} must be finite (no NaN or Infinity).";

            var sb = new StringBuilder(512);
            ipa2v_reverse(v, width, sb, 512);
            string result = sb.ToString();
            if (toneStr.Length > 0)
            {
                /* append the tone symbols inside the rebuilt IPA:
                 * phonetic brackets [..] or narrowest (..) */
                char close = result.EndsWith("\u27E7")
                    ? '\u27E7' : ']';
                int idx = result.LastIndexOf(close);
                if (idx > 0 && result.EndsWith(close.ToString()))
                    result = result[..idx] + toneStr + close;
                else
                    result += "  tone: " + toneStr;
            }
            if (toneWarn.Length > 0)
                result += ToneWarnPrefix + toneWarn + ToneWarnSuffix;
            return result;
        }

        /* tone slots (by position) -> (IPA tone symbols, warning) */
        private static (string, string) ToneSymbols(double[][] slots)
        {
            const string L5 = "\u02E9\u02E8\u02E7\u02E6\u02E5"; // 1..5 -> ˩˨˧˦˥
            const string S5 = "\uA716\uA715\uA714\uA713\uA712"; // 1..5 -> ꜖꜕꜔꜓꜒
            const string D0 = "\u2070\u00B9\u00B2\u00B3\u2074\u2075" +
                              "\u2076\u2077\u2078\u2079";          // 0..9
            var sb = new StringBuilder();
            string warn = "";

            /* slot 0/1: any non-1..5 value (0 or >5) turns BOTH groups
             * into superscript digits joined with ⁻ (no ⁻ when the second
             * group is absent or skipped); values below -0.5 warn and
             * skip that group */
            double[]? g0 = slots.Length > 0 ? slots[0] : null;
            double[]? g1 = slots.Length > 1 ? slots[1] : null;
            bool neg0 = g0 != null && g0.Any(d => d < -0.5);
            bool neg1 = g1 != null && g1.Any(d => d < -0.5);
            if (neg0 || neg1) warn = NegativeToneWarn;
            List<int>? r0 = neg0 || g0 == null
                ? null : g0.Select(d => (int)Math.Round(d)).ToList();
            List<int>? r1 = neg1 || g1 == null
                ? null : g1.Select(d => (int)Math.Round(d)).ToList();
            bool sup = (r0 != null && r0.Any(v => v < 1 || v > 5)) ||
                       (r1 != null && r1.Any(v => v < 1 || v > 5));
            if (sup)
            {
                if (r0 != null)
                    foreach (var v in r0)
                        if (v >= 0 && v <= 9) sb.Append(D0[v]);
                if (r1 != null)
                {
                    sb.Append('\u207B');   /* ⁻ joins the two groups */
                    foreach (var v in r1)
                        if (v >= 0 && v <= 9) sb.Append(D0[v]);
                }
            }
            else
            {
                if (r0 != null)
                    foreach (var v in r0) sb.Append(L5[v - 1]);
                if (r1 != null)
                    foreach (var v in r1) sb.Append(S5[v - 1]);
            }

            /* slot 2: 3-D vector - negative values are legal (upstep,
             * downstep, falling, negative tone classes) */
            if (slots.Length > 2 && slots[2] != null && slots[2].Length >= 1)
            {
                double u = slots[2][0];
                if (u < 0) sb.Append('\uA71B'); else if (u > 0) sb.Append('\uA71C');
                if (slots[2].Length >= 2)
                {
                    double g = slots[2][1];
                    if (g > 0) sb.Append('\u2197'); else if (g < 0) sb.Append('\u2198');
                }
                if (slots[2].Length >= 3)
                {
                    int c = (int)Math.Round(slots[2][2]);
                    char cls = c switch
                    {
                        1 => '\uA700', -1 => '\uA701', 2 => '\uA702',
                        -2 => '\uA703', 3 => '\uA704', -3 => '\uA705',
                        4 => '\uA706', -4 => '\uA707', _ => '\0',
                    };
                    if (cls != '\0') sb.Append(cls);
                }
            }
            return (sb.ToString(), warn);
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
