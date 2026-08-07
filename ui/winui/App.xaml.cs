using Microsoft.UI.Xaml;
using System;
using System.IO;

namespace Vec4ipaUI
{
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
                File.AppendAllText(
                    Path.Combine(LogDir(), "startup.log"),
                    $"{DateTime.Now:HH:mm:ss.fff}: {msg}\n");
            }
            catch { }
        }

        public App()
        {
            Log("App ctor enter");
            UnhandledException += (s, e) =>
            {
                try
                {
                    File.AppendAllText(
                        Path.Combine(LogDir(), "crash.log"),
                        $"{DateTime.Now}: {e.Exception}\n");
                }
                catch { }
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
                try
                {
                    File.AppendAllText(
                        Path.Combine(LogDir(), "crash.log"),
                        $"{DateTime.Now}: {ex}\n{ex.StackTrace}\n");
                }
                catch { }
            }
        }
    }
}
