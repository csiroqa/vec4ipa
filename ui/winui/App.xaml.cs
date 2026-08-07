using Microsoft.UI.Xaml;
using System;
using System.IO;

namespace IPA2VectorUI
{
    public partial class App : Application
    {
        private Window? _window;

        public App()
        {
            UnhandledException += (s, e) =>
            {
                try
                {
                    File.WriteAllText(
                        Path.Combine(AppContext.BaseDirectory, "crash.log"),
                        $"{DateTime.Now}: {e.Exception}\n");
                }
                catch { }
            };
            InitializeComponent();
        }

        protected override void OnLaunched(Microsoft.UI.Xaml.LaunchActivatedEventArgs args)
        {
            try
            {
                _window = new MainWindow();
                _window.Activate();
            }
            catch (Exception ex)
            {
                try
                {
                    File.WriteAllText(
                        Path.Combine(AppContext.BaseDirectory, "crash.log"),
                        $"{DateTime.Now}: {ex}\n{ex.StackTrace}\n");
                }
                catch { }
                throw;
            }
        }
    }
}
