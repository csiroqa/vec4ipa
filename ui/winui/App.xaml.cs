using Microsoft.UI.Xaml;
using System;
using System.IO;

namespace Vec4ipaUI
{
    /* small helpers shared by all diagnostic logs: files live in
     * %TEMP%\vec4ipa\ and are rotated once they grow past 1 MB
     * (the old file is renamed to .old, newest content is kept) */
    internal static class LogFiles
    {
        private const long MaxBytes = 1 << 20;

        public static void RotateIfLarge(string path)
        {
            try
            {
                var fi = new FileInfo(path);
                if (fi.Exists && fi.Length > MaxBytes)
                    File.Move(path, path + ".old", true);
            }
            catch { }
        }
    }

    public partial class App : Application
    {
        private Window? _window;

        /* diagnostic log lives in %TEMP%\vec4ipa\, never in the
         * app folder (keeps the dist/ output clean) */
        private static string LogDir()
        {
            string dir = Path.Combine(Path.GetTempPath(), "vec4ipa");
            try { Directory.CreateDirectory(dir); } catch { }
            return dir;
        }

        private static void Log(string msg)
        {
            try
            {
                string path = Path.Combine(LogDir(), "startup.log");
                LogFiles.RotateIfLarge(path);
                File.AppendAllText(path,
                    $"{DateTime.Now:HH:mm:ss.fff}: {msg}\n");
            }
            catch { }
        }

        private static void LogCrash(string text)
        {
            try
            {
                string path = Path.Combine(LogDir(), "crash.log");
                LogFiles.RotateIfLarge(path);
                File.AppendAllText(path, text);
            }
            catch { }
        }

        /* fatal exceptions cannot be recovered from; anything else is
         * logged and swallowed so the app keeps running */
        private static bool IsFatal(Exception ex) =>
            ex is OutOfMemoryException or AccessViolationException
                or StackOverflowException;

        public App()
        {
            Log("App ctor enter");
            UnhandledException += (s, e) =>
            {
                if (IsFatal(e.Exception)) return;
                LogCrash($"{DateTime.Now}: {e.Exception}\n");
                e.Handled = true;
                Log("unhandled (recovered): " + e.Exception.Message);
            };
            InitializeComponent();
            Log("App ctor done");
        }

        protected override void OnLaunched(Microsoft.UI.Xaml.LaunchActivatedEventArgs args)
        {
            Log("OnLaunched enter");
            try
            {
                _window = new MainWindow(Environment.GetCommandLineArgs());
                Log("MainWindow created");
                _window.Activate();
                Log("MainWindow activated");
            }
            catch (Exception ex)
            {
                Log($"EXCEPTION: {ex}");
                LogCrash($"{DateTime.Now}: {ex}\n{ex.StackTrace}\n");
            }
        }
    }
}
