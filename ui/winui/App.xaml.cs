using Microsoft.UI.Xaml;
using System;
using System.IO;

namespace IPA2VectorUI
{
    public partial class App : Application
    {
        private Window? _window;

        private static void Log(string msg)
        {
            try
            {
                File.AppendAllText(
                    Path.Combine(AppContext.BaseDirectory, "startup.log"),
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
                        Path.Combine(AppContext.BaseDirectory, "crash.log"),
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
                _window = new MainWindow();
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
                        Path.Combine(AppContext.BaseDirectory, "crash.log"),
                        $"{DateTime.Now}: {ex}\n{ex.StackTrace}\n");
                }
                catch { }
            }
        }
    }
}
