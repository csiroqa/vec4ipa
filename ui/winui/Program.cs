using System;
using System.IO;
using Microsoft.UI.Xaml;

namespace Vec4ipaUI
{
    /* explicit entry point: lets Application.Start failures (which happen
     * BEFORE the App ctor's UnhandledException hook exists) be logged to
     * %TEMP%\vec4ipa\crash.log instead of dying silently */
    public static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                WinRT.ComWrappersSupport.InitializeComWrappers();
                Application.Start(p =>
                {
                    var context = new Microsoft.UI.Dispatching.DispatcherQueueSynchronizationContext(
                        Microsoft.UI.Dispatching.DispatcherQueue.GetForCurrentThread());
                    System.Threading.SynchronizationContext.SetSynchronizationContext(context);
                    new App();
                });
            }
            catch (Exception ex)
            {
                try
                {
                    string dir = Path.Combine(Path.GetTempPath(), "vec4ipa");
                    Directory.CreateDirectory(dir);
                    File.AppendAllText(Path.Combine(dir, "crash.log"),
                        $"{DateTime.Now}: PROGRAM-MAIN: {ex}\n{ex.StackTrace}\n");
                }
                catch { }
                throw;
            }
        }
    }
}
