using System;
using System.Runtime.InteropServices;
using System.Text;

namespace IPA2VectorUI
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
        private static extern int ipa2v_kb_vowels(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern int ipa2v_kb_mods(
            [MarshalAs(UnmanagedType.LPUTF8Str)] StringBuilder out_, int outsz);

        [DllImport("ipa2vec_core.dll", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr ipa2v_version();

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
            var parts = vectorText.Split(new[] { ',', ' ', '\t' },
                StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != NDIM)
                return "bad vector: need 16 comma-separated values";
            var v = new double[NDIM];
            for (int i = 0; i < NDIM; i++)
            {
                if (!double.TryParse(parts[i], System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out v[i]))
                    return "bad vector: numbers expected";
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
        public static string[] KeyboardVowels() => KbList(ipa2v_kb_vowels);
        public static string[] KeyboardMods() => KbList(ipa2v_kb_mods);

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
    }
}
