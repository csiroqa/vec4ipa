using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Windowing;
using Microsoft.UI;
using Microsoft.UI.Input;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

namespace Vec4ipaUI
{
    public sealed partial class MainWindow : Window
    {
        private bool _drag;
        private double _dragStartX;
        private double _dragStartWidth;
        private AppWindow? _appWindow;
        private string _statePath =
            Path.Combine(Environment.GetFolderPath(
                Environment.SpecialFolder.ApplicationData),
                "vec4ipa", "window.ini");

        /* ---- layout / thresholds / Win32 constants ---- */
        private const int DefaultWinWidth = 1180;
        private const int DefaultWinHeight = 760;
        private const double DefaultSplitWidth = 560;
        private const double RestoreMinSplit = 360;
        private const double MinLeftWidth = 480;
        private const double MaxLeftWidth = 1400;
        private const double DragRectTop = 30;
        private const double DragRectRightGap = 200;
        private const double MagnetRadius = 6;
        private const int MinVisibleLeft = 200;
        private const int MinVisibleTop = 100;

        /* ---- keyboard / UI thresholds ---- */
        private const int KeyMinWidth = 44;
        private const int KeyMinHeight = 34;
        private const int MaxFavorites = 200;
        private const int MaxRecent = 60;
        private const int MaxHistory = 200;
        private const double HoverGlyphLarge = 30;
        private const double HoverGlyph = 24;

        /* ---- Win32 constants ---- */
        private const int GWL_EXSTYLE = -20;
        private const int WS_EX_TOPMOST = 0x8;
        private const int HwndNotopmost = -2;
        private const int HwndTopmost = -1;
        private const uint SwpNoSize = 0x0001;
        private const uint SwpNoMove = 0x0002;
        private const uint SwpNoActivate = 0x0010;
        private const int WhMouseLl = 14;
        private const int WmLButtonDown = 0x0201;
        private const uint InputKeyboard = 1;
        private const uint KeyeventfUnicode = 4;
        private const int SmXvirtualscreen = 76;
        private const int SmYvirtualscreen = 77;
        private const int SmCxvirtualscreen = 78;
        private const int SmCyvirtualscreen = 79;
        private const int GcsCompstr = 0x0008;

        /* the IPA glyph font (system-installed; also declared as a XAML
         * resource for the soft-keyboard input box) */
        private static readonly Microsoft.UI.Xaml.Media.FontFamily IpaFont =
            new("Gentium Book Plus");

        public MainWindow(string[] args)
        {
            _startupArgs = args;
            InitializeComponent();
            /* Fluent material: Mica backdrop on the window, with the XAML
             * content kept transparent so the material shows through.
             * Falls back to plain backgrounds on systems without it. */
            try
            {
                SystemBackdrop = new Microsoft.UI.Xaml.Media.MicaBackdrop();
            }
            catch (Exception ex) { LogExt("mica err " + ex.Message); }
            _fmtRows = new[] { FmtRow0, FmtRow1, FmtRow2, FmtRow3 };
            _fmtItems = new[] { FmtItem0, FmtItem1, FmtItem2, FmtItem3 };
            _fmtChecks = new[] { FmtCheck0, FmtCheck1, FmtCheck2, FmtCheck3 };
            Title = "vec4ipa Workbench";
            SetIcon();
            RestoreState();
            WireSplitGrip();
            WireCursorMagnet();
            WireWidthBtn();
            /* the magnet caches hwnd/DPI; a move onto a monitor with a
             * different scale invalidates it (SizeChanged fires on the
             * resulting rescale) */
            SizeChanged += (s, e) => _cursorDpiCached = false;
            BindEnterToButton(IpaInputRight, ConvertBtn, ConvertBtn_Click);
            IpaInputRight.TextChanged += (s, e) =>
            {
                /* keep it a single line: strip pasted newlines */
                if (IpaInputRight.Text.Contains('\n') ||
                    IpaInputRight.Text.Contains('\r'))
                {
                    string clean = IpaInputRight.Text
                        .Replace("\r", "").Replace("\n", " ");
                    _programmatic = true;
                    IpaInputRight.Text = clean;
                    IpaInputRight.SelectionStart = clean.Length;
                    _programmatic = false;
                }
                if (!_programmatic) _placeholder = false;
                UpdateButtons();
                ScrollRightInput();
            };
            VecInput.TextChanged += (s, e) => UpdateButtons();
            DistA.TextChanged += (s, e) => UpdateButtons();
            DistB.TextChanged += (s, e) => UpdateButtons();
            /* remember which text box has focus so the soft keyboard
             * types into it and keeps it focused */
            IpaInputRight.GotFocus += (s, e) => _focusedBox = IpaInputRight;
            VecInput.GotFocus += (s, e) => _focusedBox = VecInput;
            DistA.GotFocus += (s, e) => _focusedBox = DistA;
            DistB.GotFocus += (s, e) => _focusedBox = DistB;
            /* clicking a section header scrolls the keyboard to it */
            LblCons.Tapped += (s, e) => ScrollToSection(LblCons);
            LblNp.Tapped += (s, e) => ScrollToSection(LblNp);
            LblVow.Tapped += (s, e) => ScrollToSection(LblVow);
            LblDiac.Tapped += (s, e) => ScrollToSection(LblDiac);
            LblLet.Tapped += (s, e) => ScrollToSection(LblLet);
            LblTone.Tapped += (s, e) => ScrollToSection(LblTone);
            LblRec.Tapped += (s, e) => ScrollToSection(LblRec);
            BindEnterToButton(VecInput, ReverseBtn, ReverseBtn_Click);
            BindEnterToButton(DistA, DistBtn, DistBtn_Click);
            BindEnterToButton(DistB, DistBtn, DistBtn_Click);
            SetStatus("Ready - click keyboard buttons or type IPA");
            Closed += (s, e) =>
            {
                UninstallLLHook();
                SaveState();
                FlushExtLog();
            };
            ShowWelcome();
            UpdateButtons();
            /* force the selection-highlight layer to rebuild on every
             * change (the compositor otherwise keeps the old paint);
             * only the latest change is applied (drag-select bursts
             * would otherwise queue one rebuild per event) */
            OutputBox.SelectionChanged += (s, e) =>
            {
                try
                {
                    int token = ++_selRebuildToken;
                    DispatcherQueue.TryEnqueue(() =>
                    {
                        if (token != _selRebuildToken) return;
                        var c = OutputBox.SelectionHighlightColor;
                        OutputBox.SelectionHighlightColor =
                            new Microsoft.UI.Xaml.Media.SolidColorBrush(
                                Microsoft.UI.Colors.Transparent);
                        OutputBox.SelectionHighlightColor = c;
                    });
                }
                catch (Exception ex) { LogExt("selection rebuild err " + ex.Message); }
            };
            if (!InitCore())
                return;
            InitExternalTracking();
            /* --help / --export-tools dialogs need XamlRoot; run them
             * once the window is activated */
            Activated += async (s, e) =>
            {
                if (_argsPending)
                {
                    _argsPending = false;
                    await HandleArgs(_startupArgs);
                }
            };
        }

        /* Enter in a text box triggers the button next to it (only when
         * the button is enabled and no IME composition is in progress -
         * Enter commits candidate text and must not fire the button) */
        private void BindEnterToButton(UIElement box, Button btn,
            RoutedEventHandler handler)
        {
            box.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter &&
                    btn.IsEnabled && !ImeComposing())
                {
                    handler(box, e);
                    e.Handled = true;
                }
            };
        }

        /* true while an IME is composing text in the focused control
         * (Enter would otherwise commit the candidate and hit the
         * button at the same time) */
        private bool ImeComposing()
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                IntPtr imc = ImmGetContext(hwnd);
                if (imc == IntPtr.Zero) return false;
                try
                {
                    /* ImmGetContext on a WinUI 3 window returns the
                     * thread's default IMC, which is unreliable under
                     * TSF; an IME that is not open cannot compose, so
                     * the open status is the cheapest extra guard */
                    if (!ImmGetOpenStatus(imc)) return false;
                    return ImmGetCompositionString(imc, GcsCompstr,
                        IntPtr.Zero, 0) > 0;
                }
                finally { ImmReleaseContext(hwnd, imc); }
            }
            catch { return false; }
        }

        [System.Runtime.InteropServices.DllImport("imm32.dll")]
        [return: System.Runtime.InteropServices.MarshalAs(
            System.Runtime.InteropServices.UnmanagedType.Bool)]
        private static extern bool ImmGetOpenStatus(IntPtr hIMC);

        [System.Runtime.InteropServices.DllImport("imm32.dll")]
        private static extern IntPtr ImmGetContext(IntPtr hWnd);

        [System.Runtime.InteropServices.DllImport("imm32.dll")]
        private static extern bool ImmReleaseContext(IntPtr hWnd,
            IntPtr hIMC);

        [System.Runtime.InteropServices.DllImport("imm32.dll")]
        private static extern int ImmGetCompositionString(IntPtr hIMC,
            int dwIndex, IntPtr lpBuf, int dwBufLen);

        /* pickers need an owner HWND or they fail on WinUI 3 desktop */
        private void InitializePicker(object picker)
        {
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
        }

        private async System.Threading.Tasks.Task<Windows.Storage.StorageFile?>
            PickFileAsync(params string[] fileTypes)
        {
            var picker = new Windows.Storage.Pickers.FileOpenPicker();
            InitializePicker(picker);
            foreach (var t in fileTypes) picker.FileTypeFilter.Add(t);
            return await picker.PickSingleFileAsync();
        }

        private async System.Threading.Tasks.Task<Windows.Storage.StorageFile?>
            PickSaveFileAsync(string suggestedName, string label,
                params string[] fileTypes)
        {
            var picker = new Windows.Storage.Pickers.FileSavePicker();
            InitializePicker(picker);
            picker.SuggestedFileName = suggestedName;
            picker.FileTypeChoices.Add(label, new List<string>(fileTypes));
            return await picker.PickSaveFileAsync();
        }

        private async System.Threading.Tasks.Task<Windows.Storage.StorageFolder?>
            PickFolderAsync()
        {
            var picker = new Windows.Storage.Pickers.FolderPicker();
            InitializePicker(picker);
            picker.FileTypeFilter.Add("*");
            return await picker.PickSingleFolderAsync();
        }

        /* shared clipboard helper: true on success */
        private static bool CopyToClipboard(string text)
        {
            try
            {
                var dp = new Windows.ApplicationModel.DataTransfer.DataPackage();
                dp.SetText(text);
                Windows.ApplicationModel.DataTransfer.Clipboard.SetContent(dp);
                return true;
            }
            catch { return false; }
        }

        /* returns false when ipa2vec_core.dll is missing (UI stays up
         * with a clear status message and the core-dependent controls
         * disabled instead of crashing on the first P/Invoke) */
        private bool InitCore()
        {
            try
            {
                string ver = Core.Version;
                BuildKeyboard();
                _coreOk = true;
                UpdateButtons();
                _argsPending = true;
                StatusText.Text = $"core {ver} - width {(int)WidthSlider.Value}";
                return true;
            }
            catch (System.DllNotFoundException)
            {
                DisableCoreMenus();
                StatusText.Text = "ipa2vec_core.dll not found next to the app - " +
                                  "features are disabled";
                return false;
            }
            catch (System.EntryPointNotFoundException)
            {
                DisableCoreMenus();
                StatusText.Text = "ipa2vec_core.dll is outdated or damaged - " +
                                  "features are disabled";
                return false;
            }
        }

        /* everything that ends up calling into the core is disabled */
        private void DisableCoreMenus()
        {
            FileBtn.IsEnabled = false;
            ViewBtn.IsEnabled = false;
            HelpBtn.IsEnabled = false;
            LoopBtn.IsEnabled = false;
            ExtToggle.IsEnabled = false;
        }

        private void UpdateButtons()
        {
            ConvertBtn.IsEnabled = _coreOk && IpaInputRight.Text.Length > 0;
            ReverseBtn.IsEnabled = _coreOk && VecInput.Text.Trim().Length > 0;
            DistBtn.IsEnabled = _coreOk && DistA.Text.Length > 0 &&
                                 DistB.Text.Length > 0;
        }

        private void ShowWelcome()
        {
            string welcome = _zh
                ? "欢迎使用 vec4ipa 工作台\n" +
                  "---------------------------------\n\n" +
                  "1. 在下方输入或点击 IPA 字符串（或在 文件 > 示例 中选择）。\n" +
                  "2. 点击 转换 - 每个音段变成 16 维向量。\n" +
                  "3. 粘贴向量并按 反向 拟合回 IPA，\n" +
                  "   选择转录宽度（0-4）。\n\n" +
                  "提示：悬停键盘按键可查看名称，双击查看详情；\n" +
                  "用过的符号会收集在 最近使用 页。\n\n" +
                   "示例：t\u02b0a（送气爆发音 + 开元音）\n"
                : "Welcome to vec4ipa Workbench\n" +
                  "---------------------------------\n\n" +
                  "1. Type or click an IPA string below (or pick an example\n" +
                  "   from File > Examples).\n" +
                  "2. Press Convert - each segment becomes a 16-D vector.\n" +
                  "3. Paste a vector and press Reverse to fit IPA back,\n" +
                  "   choosing the transcription width (0-4).\n\n" +
                  "Tip: hover a keyboard key for its name, double-click for\n" +
                  "details; symbols you use are collected on the Recent tab.\n\n" +
                   "Example to try:  t\u02b0a  (aspirated plosive + open vowel)\n";
            OutputSet(welcome);
            _programmatic = true;
            IpaInputRight.Text = "t\u02b0a";
            _programmatic = false;
            _placeholder = true;
            _history.Add(("Welcome", welcome));
        }

        private void SetStatus(string text) => StatusText.Text = text;

        /* ---- window state persistence (size / position / splitter) ---- */
        private void SaveState()
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(_statePath)!);
                int x = 0, y = 0, w = DefaultWinWidth, h = DefaultWinHeight;
                if (_appWindow != null)
                {
                    var pos = _appWindow.Position;
                    var size = _appWindow.Size;
                    x = pos.X; y = pos.Y;
                    w = size.Width; h = size.Height;
                }
                /* invariant formatting: the file may be read on a machine
                 * with a different number format; UTF-8 without BOM */
                string split = LeftCol.Width.Value.ToString(
                    System.Globalization.CultureInfo.InvariantCulture);
                File.WriteAllText(_statePath,
                    $"x={x}\ny={y}\nw={w}\nh={h}\nsplit={split}\n",
                    new System.Text.UTF8Encoding(false));
            }
            catch (Exception ex)
            {
                LogExt("save state err " + ex.Message);
            }
        }

        private void RestoreState()
        {
            try
            {
                if (!File.Exists(_statePath)) { Resize(); return; }
                int x = 0, y = 0, w = DefaultWinWidth, h = DefaultWinHeight;
                double split = DefaultSplitWidth;
                var inv = System.Globalization.CultureInfo.InvariantCulture;
                foreach (var line in File.ReadAllLines(_statePath))
                {
                    var p = line.Split('=');
                    if (p.Length != 2) continue;
                    if (p[0] == "x" && int.TryParse(p[1], out var v)) x = v;
                    else if (p[0] == "y" && int.TryParse(p[1], out v)) y = v;
                    else if (p[0] == "w" && int.TryParse(p[1], out v)) w = v;
                    else if (p[0] == "h" && int.TryParse(p[1], out v)) h = v;
                    else if (p[0] == "split" && double.TryParse(p[1],
                        System.Globalization.NumberStyles.Float, inv,
                        out var d))
                        split = d;
                }
                if (split < RestoreMinSplit) split = RestoreMinSplit;
                if (split > MaxLeftWidth) split = MaxLeftWidth;
                LeftCol.Width = new GridLength(split);
                /* the saved position may be from a different monitor
                 * layout; clamp so the title bar stays reachable */
                int vx = GetSystemMetrics(SmXvirtualscreen);
                int vy = GetSystemMetrics(SmYvirtualscreen);
                int vw = GetSystemMetrics(SmCxvirtualscreen);
                int vh = GetSystemMetrics(SmCyvirtualscreen);
                if (vw > 0 && vh > 0)
                {
                    int maxX = vx + vw - MinVisibleLeft;
                    if (maxX < vx) maxX = vx;
                    if (x < vx) x = vx; else if (x > maxX) x = maxX;
                    int maxY = vy + vh - MinVisibleTop;
                    if (maxY < vy) maxY = vy;
                    if (y < vy) y = vy; else if (y > maxY) y = maxY;
                }
                _appWindow = GetAppWindow();
                try
                {
                    _appWindow.MoveAndResize(new Windows.Graphics.RectInt32
                    {
                        X = x, Y = y,
                        Width = w > 0 ? w : DefaultWinWidth,
                        Height = h > 0 ? h : DefaultWinHeight,
                    });
                }
                catch
                {
                    _appWindow.Resize(new Windows.Graphics.SizeInt32(
                        DefaultWinWidth, DefaultWinHeight));
                }
            }
            catch (Exception ex)
            {
                LogExt("restore state err " + ex.Message);
                Resize();
            }
        }

        private void Resize()
        {
            try
            {
                _appWindow = GetAppWindow();
                _appWindow.Resize(new Windows.Graphics.SizeInt32(
                    DefaultWinWidth, DefaultWinHeight));
            }
            catch (Exception ex) { LogExt("resize err " + ex.Message); }
        }

        /* shared hwnd -> AppWindow boilerplate */
        private AppWindow GetAppWindow()
        {
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            var windowId = Win32Interop.GetWindowIdFromWindow(hwnd);
            return AppWindow.GetFromWindowId(windowId);
        }

        private void SetIcon()
        {
            try
            {
                var appWindow = GetAppWindow();
                string dir = Path.GetDirectoryName(
                    Environment.ProcessPath ?? "") ?? "";
                string icon = Path.Combine(dir, "vec_ipa.ico");
                if (File.Exists(icon))
                {
                    appWindow.SetIcon(icon);
                    TitleIcon.Source = new Microsoft.UI.Xaml.Media.Imaging.BitmapImage(
                        new Uri(icon));
                }
                _appWindow = appWindow;
                SetupTitleBar(appWindow);
            }
            catch (Exception ex) { LogExt("set icon err " + ex.Message); }
        }

        /* custom title bar: content extends into the caption area; the
         * title row is the drag region. The system min/max/close buttons
         * stay untouched (snap layouts, Win+Up/Down and maximize all
         * keep their native behaviour) and the always-on-top button is a
         * XAML button right next to them. */
        private void SetupTitleBar(AppWindow appWindow)
        {
            try
            {
                appWindow.TitleBar.ExtendsContentIntoTitleBar = true;
                ApplyDragRect(appWindow);
                ApplyTitleBarTheme(appWindow);
                WireWindowButtons(appWindow);
                /* drag rects must be re-applied once the window is shown
                 * and whenever it is resized (physical px follow size) */
                Activated += (s, e) => ApplyDragRect(appWindow);
                SizeChanged += (s, e) => ApplyDragRect(appWindow);
            }
            catch (Exception ex) { LogExt("title bar setup err " + ex.Message); }
        }

        /* always on top toggle (the only custom window button) */
        private void WireWindowButtons(AppWindow appWindow)
        {
            try
            {
                PinBtn.Click += (s, e) =>
                {
                    var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                    bool top = IsTopmost();
                    SetWindowPos(hwnd, top
                            ? new IntPtr(HwndNotopmost)  /* HWND_NOTOPMOST */
                            : new IntPtr(HwndTopmost),   /* HWND_TOPMOST */
                        0, 0, 0, 0,
                        SwpNoSize | SwpNoMove | SwpNoActivate);
                    RefreshPinVisual();
                    SetStatus(top
                        ? (_zh ? "取消置顶" : "always on top off")
                        : (_zh ? "窗口已置顶" : "window pinned on top"));
                };
                RefreshPinVisual();
            }
            catch (Exception ex) { LogExt("window buttons err " + ex.Message); }
        }

        private void RefreshPinVisual()
        {
            try
            {
                bool top = IsTopmost();
                PinBtn.Content = top ? "\uE77A" : "\uE718";
                bool dark = _themeName == "Dark";
                var accent = (Microsoft.UI.Xaml.Media.Brush?)(
                    Application.Current.Resources["AccentFillColorDefaultBrush"]
                        ?? new Microsoft.UI.Xaml.Media.SolidColorBrush(
                            Windows.UI.Color.FromArgb(255, 0, 120, 215)));
                PinBtn.Foreground = top ? accent
                    : new Microsoft.UI.Xaml.Media.SolidColorBrush(
                        Windows.UI.Color.FromArgb(255, (byte)(dark ? 240 : 20),
                            (byte)(dark ? 240 : 20), (byte)(dark ? 240 : 20)));
                PinBtn.Background = top
                    ? new Microsoft.UI.Xaml.Media.SolidColorBrush(
                        Windows.UI.Color.FromArgb(38, 127, 127, 127))
                    : new Microsoft.UI.Xaml.Media.SolidColorBrush(
                        Microsoft.UI.Colors.Transparent);
            }
            catch (Exception ex) { LogExt("pin visual err " + ex.Message); }
        }

        private bool IsTopmost()
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                return (GetWindowLongPtr(hwnd, GWL_EXSTYLE).ToInt64() &
                        WS_EX_TOPMOST) != 0;
            }
            catch { return false; }
        }

        /* DIP scale of the window (physical px = DIP * scale) */
        private double DpiScale()
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                double scale = GetDpiForWindow(hwnd);
                if (scale == 0) scale = 96;
                scale /= 96.0;
                if (scale < 1.0) scale = 1.0;
                return scale;
            }
            catch { return 1.0; }
        }

        private long _lastDragRectTick;

        /* resize fires per pixel; re-apply the drag rect at most every
         * 100 ms (the size difference in between is imperceptible) */
        private void ApplyDragRect(AppWindow appWindow)
        {
            try
            {
                long now = Environment.TickCount64;
                if (now - _lastDragRectTick < 100) return;
                _lastDragRectTick = now;
                double scale = DpiScale();
                int physW = appWindow.Size.Width;   /* physical px */
                if (physW <= 0) physW = (int)(DefaultWinWidth * scale);
                int dragW = physW - (int)(DragRectRightGap * scale);
                if (dragW < 100) dragW = 100;
                int dragH = (int)(DragRectTop * scale);
                appWindow.TitleBar.SetDragRectangles(new[]
                {
                    new Windows.Graphics.RectInt32(0, 0, dragW, dragH),
                });
            }
            catch (Exception ex) { LogExt("drag rect err " + ex.Message); }
        }

        private void ApplyTitleBarTheme(AppWindow appWindow)
        {
            try
            {
                var c = _themeName == "Light"
                    ? Windows.UI.Color.FromArgb(255, 0, 0, 0)
                    : _themeName == "Dark"
                        ? Windows.UI.Color.FromArgb(255, 255, 255, 255)
                        : (Windows.UI.Color?)null;
                var tb = appWindow.TitleBar;
                if (c.HasValue)
                {
                    tb.ButtonForegroundColor = c.Value;
                    tb.ButtonHoverForegroundColor = c.Value;
                }
                else
                {
                    tb.ButtonForegroundColor = null;
                    tb.ButtonHoverForegroundColor = null;
                }
                tb.ButtonBackgroundColor = Microsoft.UI.Colors.Transparent;
                tb.ButtonHoverBackgroundColor =
                    Windows.UI.Color.FromArgb(32, 127, 127, 127);
            }
            catch (Exception ex) { LogExt("title bar theme err " + ex.Message); }
        }

        /* ---- command-line arguments (CLI-compatible) ---- */
        private async Task HandleArgs(string[] args)
        {
            try
            {
            string? input = null, query = null, vec = null, exportDir = null;
            string? theme = null;
            bool reverse = false, showHelp = false;
            var errs = new List<string>();
            var rest = new List<string>();
            for (int i = 1; i < args.Length; i++)
            {
                string a = args[i];
                if (a == "--help" || a == "-h") showHelp = true;
                else if (a == "--width" || a == "--narrowness")
                {
                    if (i + 1 >= args.Length) { errs.Add(a + " needs a value (0-4)"); }
                    else
                    {
                        string w = args[++i];
                        if (w.Length == 1 && w[0] >= '0' && w[0] <= '4')
                            WidthSlider.Value = w[0] - '0';
                    }
                }
                else if (a == "--theme")
                {
                    if (i + 1 >= args.Length) { errs.Add("--theme needs a value"); }
                    else theme = args[++i];
                }
                else if (a == "-q" || a == "--query")
                {
                    if (i + 1 >= args.Length) { errs.Add(a + " needs a value"); }
                    else query = args[++i];
                }
                else if (a == "-r" || a == "--reverse")
                {
                    if (i + 1 >= args.Length) { errs.Add(a + " needs a value"); }
                    else { vec = args[++i]; reverse = true; }
                }
                else if (a == "--export-tools")
                {
                    if (i + 1 >= args.Length) { errs.Add("--export-tools needs a directory"); }
                    else exportDir = args[++i];
                }
                else if (a.StartsWith("-") && a != "--")
                    rest.Add(a);
                else if (input == null) input = a;
            }
            if (errs.Count > 0)
                SetStatus("argument error: " + string.Join("; ", errs));
            Core.SetArgs(rest.ToArray());

            if (theme != null)
            {
                string t = theme;
                DispatcherQueue.TryEnqueue(() => ApplyTheme(t));
            }

            if (showHelp)
            {
                var dlg = new ContentDialog
                {
                    XamlRoot = Content.XamlRoot,
                    Title = "vec4ipa Workbench - usage",
                    Content =
                        "vec4ipa_ui [OPTIONS] [IPA-STRING]\n\n" +
                        "  --narrowness 0-4    reverse-fit narrowness (default 3; alias --width)\n" +
                        "  -q, --query SYM     query one symbol on startup\n" +
                        "  -r, --reverse VEC   16-D vector -> IPA on startup\n" +
                        "  --export-tools DIR  write the bundled CLI tools to DIR\n" +
                        "  -h, --help          this help\n" +
                        "  --school flags      (--americanist, --sinologist, ...)\n" +
                        "IPA-STRING            forward IPA -> vectors on startup",
                    CloseButtonText = "OK",
                };
                await dlg.ShowAsync();
            }
            if (exportDir != null)
            {
                var (ok, missing) = ExportToolsTo(exportDir);
                var m = new ContentDialog
                {
                    XamlRoot = Content.XamlRoot,
                    Title = "Export tools",
                    Content = $"Exported {ok} of 3 tools to:\n{exportDir}\n" +
                              (missing > 0
                                  ? $"{missing} tool(s) not bundled in this build."
                                  : "All three CLI tools are ready to use."),
                    CloseButtonText = "OK",
                };
                await m.ShowAsync();
            }
            if (query != null)
            {
                AppendOutput($"=== Query: {query} ===\n" + QuerySymbol(query));
            }
            if (reverse && vec != null)
            {
                VecInput.Text = vec;
                ReverseBtn_Click(this, new RoutedEventArgs());
            }
            else if (input != null)
            {
                IpaInputRight.Text = input;
                ConvertBtn_Click(this, new RoutedEventArgs());
            }
            }
            catch (Exception ex)
            {
                LogExt("startup args failed: " + ex.Message);
                SetStatus("startup arguments failed: " + ex.Message);
            }
        }

        /* ---- Settings dialog: theme / language / feature names / modules ---- */

        private readonly Dictionary<string, bool> _moduleOn = new();
        private string _themeName = "System";
        private string[] _startupArgs = Array.Empty<string>();
        private bool _argsPending;
        private bool _coreOk;            // ipa2vec_core.dll loaded and probed
        private int _selRebuildToken;    // latest selection-rebuild request
        private TextBox? _focusedBox; // soft-keyboard target (last focused box)
        private TextBox? _kbPressedBox; // box focused when a key was pressed
        private bool _slideMode;         // glide-typing across keys
        private bool _slid;              // glide typed (skip the final Click)
        private bool _externalMode;      // SendInput into the foreground window
        private IntPtr _extTarget = IntPtr.Zero; // the external window to type into

        /* remember which window the user switched to while this app
         * loses activation (the global-input target) */
        private void InitExternalTracking()
        {
            Activated += (s, e) =>
            {
                try
                {
                    if (e.WindowActivationState ==
                        Microsoft.UI.Xaml.WindowActivationState.Deactivated)
                        _extTarget = GetForegroundWindow();
                }
                catch (Exception ex)
                {
                    LogExt("ext tracking err " + ex.Message);
                }
            };
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd,
            out uint lpdwProcessId);

        [System.Runtime.InteropServices.DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool AttachThreadInput(uint idAttach,
            uint idAttachTo, bool fAttach);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        /* restore activation to the external window (bypasses the
         * foreground lock via AttachThreadInput) */
        private static void RestoreForeground(IntPtr target)
        {
            if (target == IntPtr.Zero) return;
            try
            {
                uint cur = GetCurrentThreadId();
                uint tgt = GetWindowThreadProcessId(target, out _);
                bool attached = AttachThreadInput(cur, tgt, true);
                bool ok = SetForegroundWindow(target);
                if (attached) AttachThreadInput(cur, tgt, false);
                LogExt($"restore fg hwnd={target} attach={attached} setfg={ok} " +
                       $"now={GetForegroundWindow()}");
            }
            catch (Exception ex) { LogExt("restore fg err " + ex.Message); }
        }

        /* hot-path logs (kb.log / ext.log): buffered in memory, written
         * at most once per second and never on the UI thread (pointer
         * events fire far more often than that); rotated past 1 MB */
        private static class ThrottledLog
        {
            private const double FlushMs = 1000;
            private const int MaxBuffer = 200;
            private static readonly List<string> ExtBuffer = new();
            private static DateTime ExtLastFlush = DateTime.MinValue;
            private static string? _lastKbLine;
            private static DateTime _kbLastFlush = DateTime.MinValue;
            private static readonly object WriteLock = new();
            private static Task? _extWrite;
            private static Task? _kbWrite;

            private static string Path(string name) =>
                System.IO.Path.Combine(System.IO.Path.GetTempPath(),
                    "vec4ipa", name);

            public static void Ext(string msg)
            {
                ExtBuffer.Add($"{DateTime.Now:HH:mm:ss.fff}: {msg}");
                if (ExtBuffer.Count > MaxBuffer) ExtBuffer.RemoveAt(0);
                var now = DateTime.Now;
                if ((now - ExtLastFlush).TotalMilliseconds < FlushMs) return;
                ExtLastFlush = now;
                if (ExtBuffer.Count == 0) return;
                string[] lines = ExtBuffer.ToArray();
                ExtBuffer.Clear();
                var file = Path("ext.log");
                _extWrite = Task.Run(() =>
                {
                    lock (WriteLock)
                    {
                        try
                        {
                            LogFiles.RotateIfLarge(file);
                            File.AppendAllLines(file, lines);
                        }
                        catch { }
                    }
                });
            }

            /* only the latest key event is kept (single-line file) */
            public static void Kb(string line)
            {
                _lastKbLine = line;
                var now = DateTime.Now;
                if ((now - _kbLastFlush).TotalMilliseconds < FlushMs) return;
                _kbLastFlush = now;
                if (_lastKbLine == null) return;
                string content = _lastKbLine + "\n";
                _lastKbLine = null;
                var file = Path("kb.log");
                _kbWrite = Task.Run(() =>
                {
                    lock (WriteLock)
                    {
                        try { File.WriteAllText(file, content); }
                        catch { }
                    }
                });
            }

            /* called on exit: block so the last lines land on disk */
            public static void FlushExtSync()
            {
                /* in-flight background writes first, then whatever is
                 * still buffered (order preserved: the background tasks
                 * captured older lines) */
                try { _kbWrite?.Wait(2000); } catch { }
                try { _extWrite?.Wait(2000); } catch { }
                if (ExtBuffer.Count == 0) return;
                string[] lines = ExtBuffer.ToArray();
                ExtBuffer.Clear();
                var file = Path("ext.log");
                lock (WriteLock)
                {
                    try
                    {
                        LogFiles.RotateIfLarge(file);
                        File.AppendAllLines(file, lines);
                    }
                    catch { }
                }
            }
        }

        private static void LogExt(string msg) => ThrottledLog.Ext(msg);

        private static void FlushExtLog() => ThrottledLog.FlushExtSync();

        /* external input: a global low-level mouse hook. A click on the
         * soft keyboard while the external app is focused would otherwise
         * first activate this window (WinUI swallows the press and steals
         * focus); the hook sees the press before activation, types the
         * symbol into the still-focused external app and swallows the
         * click so this window never activates. */
        private LowLevelMouseProc? _llProc;
        private IntPtr _llHook = IntPtr.Zero;

        private delegate IntPtr LowLevelMouseProc(int nCode, IntPtr wParam,
            IntPtr lParam);

        [System.Runtime.InteropServices.StructLayout(
            System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct MSLLHOOKSTRUCT
        {
            public POINT32 pt;
            public uint mouseData;
            public uint flags;
            public uint time;
            public System.IntPtr dwExtraInfo;
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr SetWindowsHookEx(int idHook,
            LowLevelMouseProc lpfn, IntPtr hMod, uint dwThreadId);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool UnhookWindowsHookEx(IntPtr hhk);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode,
            IntPtr wParam, IntPtr lParam);

        [System.Runtime.InteropServices.DllImport("kernel32.dll")]
        private static extern IntPtr GetModuleHandle(string? lpModuleName);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

        [System.Runtime.InteropServices.StructLayout(
            System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        private void InstallLLHook()
        {
            try
            {
                if (_llHook != IntPtr.Zero) return;
                _llProc = MouseHookProc;
                _llHook = SetWindowsHookEx(WhMouseLl, _llProc,
                    GetModuleHandle(null), 0);
                LogExt("ll hook " + (_llHook != IntPtr.Zero
                    ? "installed" : "FAILED"));
            }
            catch (Exception ex) { LogExt("ll hook err " + ex.Message); }
        }

        private void UninstallLLHook()
        {
            try
            {
                if (_llHook != IntPtr.Zero)
                {
                    UnhookWindowsHookEx(_llHook);
                    _llHook = IntPtr.Zero;
                    LogExt("ll hook removed");
                }
            }
            catch (Exception ex) { LogExt("ll unhook err " + ex.Message); }
        }

        private IntPtr MouseHookProc(int nCode, IntPtr wParam, IntPtr lParam)
        {
            try
            {
                if (nCode >= 0 && _externalMode &&
                    (int)wParam == WmLButtonDown /* WM_LBUTTONDOWN */)
                {
                    var info = (MSLLHOOKSTRUCT)System.Runtime.InteropServices
                        .Marshal.PtrToStructure(lParam,
                            typeof(MSLLHOOKSTRUCT))!;
                    var hwnd = WinRT.Interop.WindowNative
                        .GetWindowHandle(this);
                    /* only intercept presses inside this window */
                    var pt = info.pt;
                    ScreenToClient(hwnd, ref pt);
                    GetClientRect(hwnd, out var rc);
                    if (pt.X >= 0 && pt.Y >= 0 &&
                        pt.X < rc.Right && pt.Y < rc.Bottom)
                    {
                        string? sym = FindSymbolAtPoint(pt.X, pt.Y);
                        if (sym != null)
                        {
                            LogExt($"ll down '{sym}' fg={GetForegroundWindow()}");
                            ExtType(sym);
                            return new IntPtr(1); /* swallow: no activation */
                        }
                    }
                }
            }
            catch (Exception ex) { LogExt("ll hook proc err " + ex.Message); }
            return CallNextHookEx(_llHook, nCode, wParam, lParam);
        }

        private void ExtToggle_Changed(object sender, RoutedEventArgs e)
        {
            _externalMode = ExtToggle.IsChecked == true;
            LogExt($"toggle sender={sender.GetType().Name} " +
                   $"checked={ExtToggle.IsChecked}");
            if (_externalMode)
            {
                /* make sure the type-into target is a real, other window */
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                if (_extTarget == IntPtr.Zero || _extTarget == hwnd)
                {
                    var fg = GetForegroundWindow();
                    _extTarget = fg != hwnd ? fg : IntPtr.Zero;
                }
                InstallLLHook();
            }
            else
                UninstallLLHook();
            SetStatus(_externalMode
                ? (_zh ? "外部输入开启 - 软键盘输入到当前前台窗口"
                       : "external input ON - soft keyboard types into the focused window")
                : (_zh ? "外部输入关闭" : "external input OFF"));
        }

        private string? FindSymbolAtPoint(int xPhys, int yPhys)
        {
            try
            {
                double scale = DpiScale();
                double x = xPhys / scale;
                double y = yPhys / scale;
                var root = Content.XamlRoot.Content as UIElement;
                if (root == null || _kbButtons.Count == 0) return null;
                foreach (var (sym, btn) in _kbButtons)
                {
                    if (btn.ActualWidth <= 0) continue;
                    var t = btn.TransformToVisual(root);
                    var pt = t.TransformPoint(new Windows.Foundation.Point(0, 0));
                    if (x >= pt.X && x <= pt.X + btn.ActualWidth &&
                        y >= pt.Y && y <= pt.Y + btn.ActualHeight)
                        return sym;
                }
            }
            catch (Exception ex) { LogExt("find sym err " + ex.Message); }
            return null;
        }

        /* type a symbol into the external (foreground) window */
        private void ExtType(string sym)
        {
            try
            {
                string clean = sym.Contains('\u25CC') && sym.Length > 1
                    ? sym.Replace("\u25CC", "") : sym;
                if (_extTarget != IntPtr.Zero)
                    RestoreForeground(_extTarget);
                SendTextToForeground(clean);
            }
            catch (Exception ex) { LogExt("ext type err " + ex.Message); }
        }

        /* send UTF-16 text to the foreground window via SendInput */
        [System.Runtime.InteropServices.StructLayout(
            System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct KEYBDINPUT
        {
            public ushort wVk;
            public ushort wScan;
            public uint dwFlags;
            public uint time;
            public System.IntPtr dwExtraInfo;
        }

        [System.Runtime.InteropServices.StructLayout(
            System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct INPUT
        {
            public uint type;
            public KEYBDINPUT ki;
            /* INPUT is a union: the real size is 28 bytes (MOUSEINPUT is
             * the largest member); SendInput rejects smaller cbSize */
            public uint padding;
        }

        [System.Runtime.InteropServices.DllImport("user32.dll",
            SetLastError = true)]
        private static extern uint SendInput(uint nInputs, INPUT[] pInputs,
            int cbSize);

        private static void SendTextToForeground(string text)
        {
            uint sent = 0;
            foreach (char c in text)
            {
                var input = new INPUT
                {
                    type = InputKeyboard, // INPUT_KEYBOARD
                    ki = new KEYBDINPUT
                    {
                        wVk = 0,
                        wScan = c,
                        dwFlags = KeyeventfUnicode, // KEYEVENTF_UNICODE
                        dwExtraInfo = System.IntPtr.Zero,
                    },
                };
                sent += SendInput(1, new[] { input },
                    System.Runtime.InteropServices.Marshal.SizeOf(input));
            }
            LogExt($"SendInput '{text}' chars={text.Length} sent={sent} " +
                   $"fg={GetForegroundWindow()}");
        }

        private async void Settings_Click(object sender, RoutedEventArgs e)
        {
            try
            {
            /* theme */
            var themeRadio = new RadioButtons
            {
                Header = _zh ? "主题" : "Theme",
            };
            themeRadio.Items.Add(_zh ? "跟随系统" : "System");
            themeRadio.Items.Add("Light");
            themeRadio.Items.Add("Dark");
            themeRadio.SelectedIndex = _themeName == "Light" ? 1
                                      : _themeName == "Dark" ? 2 : 0;

            /* feature names */
            var featSwitch = new ToggleSwitch
            {
                Header = _zh ? "向量输出显示特征名（place, body, …）"
                             : "Vector output shows feature names (place, body, ...)",
                IsOn = _featureNames,
            };

            /* language */
            var langRadio = new RadioButtons
            {
                Header = _zh ? "语言" : "Language",
            };
            langRadio.Items.Add("English");
            langRadio.Items.Add("中文");
            langRadio.SelectedIndex = _zh ? 1 : 0;

            /* school modules */
            var modsPanel = new StackPanel { Spacing = 2 };
            var modBoxes = new Dictionary<string, CheckBox>();
            foreach (var name in Core.Modules())
            {
                var cb = new CheckBox
                {
                    Content = "--" + name,
                    IsChecked = _moduleOn.TryGetValue(name, out var on)
                        && on,
                    FontSize = 13,
                };
                modBoxes[name] = cb;
                modsPanel.Children.Add(cb);
            }

            var metricText = new TextBlock
            {
                Text = _zh ? "度量：编译内置默认值（metric16.json v10）"
                           : "Metric: compiled-in defaults (metric16.json v10)",
                FontSize = 13,
                Margin = new Thickness(0, 4, 0, 0),
            };
            var loadMetricBtn = new Button
            {
                Content = _zh ? "加载 metric.json..." : "Load metric.json...",
                HorizontalAlignment = HorizontalAlignment.Left,
            };

            var content = new ScrollViewer
            {
                MaxHeight = 460,
                Content = new StackPanel { Spacing = 10, Children =
                {
                    themeRadio, featSwitch, langRadio,
                    new TextBlock { Text = _zh ? "学校模块" : "School modules", FontWeight =
                        Microsoft.UI.Text.FontWeights.SemiBold },
                    modsPanel,
                    loadMetricBtn,
                    metricText,
                } },
            };

            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = _zh ? "设置" : "Settings",
                Content = content,
                PrimaryButtonText = _zh ? "确定" : "OK",
                CloseButtonText = _zh ? "取消" : "Cancel",
            };
            loadMetricBtn.Click += async (s2, e2) =>
            {
                try
                {
                    var file = await PickFileAsync(".json");
                    if (file == null) return;
                    string? err = Core.LoadMetric(file.Path);
                    metricText.Text = err == null
                        ? "Metric: " + file.Name + " (loaded)"
                        : "Metric load failed: " + file.Name;
                }
                catch (Exception ex)
                {
                    LogExt("load metric err " + ex.Message);
                    metricText.Text = "Metric load failed: " + ex.Message;
                }
            };

            if (await dlg.ShowAsync() != ContentDialogResult.Primary)
                return;

            /* apply */
            string theme = themeRadio.SelectedItem as string ?? _themeName;
            _themeName = theme;
            ApplyTheme(theme);
            _featureNames = featSwitch.IsOn;
            string lang = langRadio.SelectedItem as string
                          ?? (_zh ? "中文" : "English");
            ApplyLang(lang == "中文");
            foreach (var (name, cb) in modBoxes)
            {
                bool on = cb.IsChecked == true;
                bool was = _moduleOn.TryGetValue(name, out var w) && w;
                if (on != was)
                {
                    _moduleOn[name] = on;
                    if (on)
                    {
                        Core.SetArgs(new[] { "--" + name });
                        SetStatus("module enabled: " + name);
                    }
                    else
                    {
                        SetStatus("note: modules cannot be disabled at runtime");
                    }
                }
            }
            }
            catch (Exception ex)
            {
                LogExt("settings err " + ex.Message);
                SetStatus("settings failed: " + ex.Message);
            }
        }

        private void ApplyLang(bool zh)
        {
            _zh = zh;
            var lbls = new[]
            {
                (LblVec, zh ? "16 维向量（逗号分隔）→ 反向拟合："
                             : "16-D vector (comma separated) → reverse fit:"),
                (LblDist, zh ? "两个符号之间的距离：" : "Distance between two symbols:"),
                (LblOut, zh ? "输出：" : "Output:"),
                (LblCons, zh ? "辅音" : "Consonants"),
                (LblNp, zh ? "非肺部气流" : "Non-pulmonic"),
                (LblVow, zh ? "元音" : "Vowels"),
                (LblDiac, zh ? "附加符号" : "Diacritics"),
                (LblLet, zh ? "修饰字母" : "Letters"),
                (LblTone, zh ? "声调" : "Tones"),
                (LblRec, zh ? "最近使用" : "Recent"),
            };
            foreach (var (ctl, text) in lbls)
                ctl.Text = text;
            ConvertBtn.Content = zh ? "转换" : "Convert";
            ReverseBtn.Content = zh ? "反向" : "Reverse";
            DistBtn.Content = zh ? "距离" : "Distance";
            FileBtn.Content = zh ? "文件" : "File";
            ViewBtn.Content = zh ? "视图" : "View";
            HelpBtn.Content = zh ? "帮助" : "Help";
            LoopBtn.Content = zh ? "回环" : "Loop";
            ToolTipService.SetToolTip(SplitGrip, zh
                ? "左键单击：收起左栏；右键单击：收起右栏"
                : "Left click: collapse left pane; right click: collapse right pane");
            ExtToggle.Content = zh ? "外部" : "Ext";
            ToolTipService.SetToolTip(ExtToggle, zh
                ? "外部输入：软键盘输入到其他应用的当前窗口"
                : "Global input: type into the focused window of other apps");
            ToolTipService.SetToolTip(WidthBtn, zh
                ? $"窄度 {WidthSlider.Value:0} - 长按展开"
                : $"narrowness {WidthSlider.Value:0} - hold to expand");
            WidthPopLabel.Text = zh ? "窄度" : "narrowness";
            WidthPopHint.Text = zh ? "0 最宽 · 4 最窄" : "0 broadest · 4 narrowest";
            WidthPopPill.Width = zh ? 46 : 78;
            int wv = Math.Clamp((int)Math.Round(WidthSlider.Value), 0, 4);
            WidthBtnLabel.Text = (zh ? LevelNamesZh : CompactNamesEn)[wv];

            var menus = new (Microsoft.UI.Xaml.Controls.MenuFlyoutItemBase Ctl, string Text)[]
            {
                (MExamples, zh ? "示例" : "Examples"),
                (MOpen, zh ? "打开文件并转换..." : "Open file and convert..."),
                (MExportCmd, zh ? "导出命令行..." : "Export command lines..."),
                (MExportTools, zh ? "导出工具（ipa2vec/vec2ipa/vec4ipa）..." : "Export tools (ipa2vec/vec2ipa/vec4ipa)..."),
                (MExit, zh ? "退出" : "Exit"),
                (MTable, zh ? "基段表" : "Base table"),
                (MModules, zh ? "模块详情" : "Module details"),
                (MStats, zh ? "统计" : "Statistics"),
                (MWeights, zh ? "度量权重" : "Metric weights"),
                (MVectorEditor, zh ? "向量编辑器..." : "Vector editor..."),
                (MHistory, zh ? "历史..." : "History..."),
                (MExportCsv, zh ? "导出表格为 CSV..." : "Export table as CSV..."),
                (MSaveIr, zh ? "保存 IR 文件（layer1/layer2）..." : "Save IR files (layer1/layer2)..."),
                (MSaveOutput, zh ? "输出另存为..." : "Save output as..."),
                (MSettings, zh ? "设置..." : "Settings..."),
                (MDocs, zh ? "文档" : "Documentation"),
                (MAbout, zh ? "关于" : "About"),
            };
            foreach (var (ctl, text) in menus)
            {
                if (ctl is MenuFlyoutItem mi) mi.Text = text;
                else if (ctl is MenuFlyoutSubItem si) si.Text = text;
            }
            FilterBox.PlaceholderText = zh ? "筛选符号（名称或符号）…" : "filter symbols (name or symbol)…";
            LblFav.Text = zh ? "收藏" : "Favorites";
            DistA.PlaceholderText = zh ? "符号 A" : "symbol A";
            DistB.PlaceholderText = zh ? "符号 B" : "symbol B";
            Title = zh ? "vec4ipa 工作台" : "vec4ipa Workbench";
            FmtBtnLabel.Text = (zh ? FmtNamesZh : FmtNamesEn)[_fmtIndex];
            ToolTipService.SetToolTip(FmtBtn, (zh ? FmtNamesZh : FmtNamesEn)
                [_fmtIndex] + (zh ? " - 长按选择格式" : " - hold to pick format"));
            CopyBtn.Content = zh ? "复制" : "Copy";
            ClearBtn.Content = zh ? "清除" : "Clear";
        }

        private void ViewTable_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput("=== Base table ===\n" + Core.Table());
            SetStatus("base table shown");
        }

        private void ViewStats_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput("=== Statistics ===\n" + Core.Stats());
            SetStatus("statistics shown");
        }

        private void ViewWeights_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput("=== Metric weights (effective) ===\n" + Core.WeightsEffective());
            SetStatus("effective metric weights shown");
        }

        private void ViewModules_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput("=== Module details ===\n" + Core.ModulesFull());
            SetStatus("module details shown");
        }

        private async void SaveIr_Click(object sender, RoutedEventArgs e)
        {
            if (IpaInputRight.Text.Length == 0)
            {
                SetStatus("nothing to export - type an IPA string first");
                return;
            }
            if (Core.ForwardRaw(IpaInputRight.Text) == null)
            {
                SetStatus("IR export failed: the input does not parse");
                return;
            }
            var file = await PickSaveFileAsync("ipa-ir", "IR base", ".layer1");
            if (file == null) return;
            string baseName = file.Path.EndsWith(".layer1")
                ? file.Path[..^7] : file.Path;
            string? err = Core.IrExport(IpaInputRight.Text, baseName);
            if (err != null) SetStatus("IR export failed: " + err);
            else
            {
                SetStatus("IR written to " + baseName + ".layer1/.layer2");
                AppendOutput($"=== IR exported: {baseName}.layer1/.layer2 ===");
            }
        }

        private void DistBtn_Click(object sender, RoutedEventArgs e)
        {
            string a = DistA.Text, b = DistB.Text;
            var va = Core.ForwardRaw(a);
            var vb = Core.ForwardRaw(b);
            var sb = new System.Text.StringBuilder();
            if (va == null || vb == null || va.Length != 1 || vb.Length != 1)
            {
                sb.AppendLine("need exactly one segment per symbol");
            }
            else
            {
                var names = Core.DimNames;
                sb.AppendLine($"{a} vs {b}:");
                for (int i = 0; i < Core.NDIM; i++)
                    sb.AppendLine($"  {names[i]}\t{va[0][i]:F4}\t{vb[0][i]:F4}\tdiff\t{vb[0][i] - va[0][i]:F4}");
                sb.AppendLine("  weighted distance: " + Core.Distance(a, b));
            }
            AppendOutput($"=== Compare {a} ~ {b} ===\n" +
                         sb.ToString().TrimEnd());
            SetStatus("comparison shown");
        }

        private async void SaveOutput_Click(object sender, RoutedEventArgs e)
        {
            var file = await PickSaveFileAsync("ipa2vec-output.txt",
                "Text file", ".txt");
            if (file == null) return;
            try
            {
                await Windows.Storage.FileIO.WriteTextAsync(file, OutputText());
                SetStatus("output saved: " + file.Path);
            }
            catch (Exception ex)
            {
                SetStatus("save failed: " + ex.Message);
            }
        }

        private void ClearOutput_Click(object sender, RoutedEventArgs e)
        {
            OutputSet("");
            SetStatus("output cleared");
        }

        private void CopyOutput_Click(object sender, RoutedEventArgs e)
        {
            SetStatus(CopyToClipboard(OutputText())
                ? "output copied to clipboard" : "copy failed");
        }

        private async void OpenFileConvert_Click(object sender, RoutedEventArgs e)
        {
            var file = await PickFileAsync(".txt");
            if (file == null) return;
            try
            {
                string text = await Windows.Storage.FileIO.ReadTextAsync(file);
                var sb = new System.Text.StringBuilder();
                sb.AppendLine($"=== File: {file.Name} ===");
                foreach (var raw in text.Split('\n',
                             StringSplitOptions.RemoveEmptyEntries))
                {
                    string line = raw.Trim();
                    if (line.Length == 0 || line.StartsWith("#")) continue;
                    sb.AppendLine("--- " + line + " ---");
                    var r = Core.Forward(line, out _);
                    sb.AppendLine(r ?? "parse error");
                }
                AppendOutput(sb.ToString().TrimEnd());
                SetStatus("converted " + file.Name);
            }
            catch (Exception ex)
            {
                SetStatus("open failed: " + ex.Message);
            }
        }

        private async void VectorEditor_Click(object sender, RoutedEventArgs e)
        {
            var names = Core.DimNames;
            var boxes = new NumberBox[Core.NDIM];
            var grid = new Grid { ColumnSpacing = 6, RowSpacing = 4 };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(110) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            for (int i = 0; i < Core.NDIM; i++)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                var lbl = new TextBlock { Text = names[i], FontSize = 13,
                    VerticalAlignment = VerticalAlignment.Center };
                var box = new NumberBox
                {
                    Value = 0,
                    Minimum = -1,
                    Maximum = 1,
                    SmallChange = 0.05,
                    Width = 100,
                    FontSize = 13,
                };
                boxes[i] = box;
                Grid.SetRow(lbl, i); Grid.SetColumn(lbl, 0);
                Grid.SetRow(box, i); Grid.SetColumn(box, 1);
                grid.Children.Add(lbl);
                grid.Children.Add(box);
            }
            var preview = new TextBlock
            {
                FontSize = 16,
                FontFamily = IpaFont,
                TextWrapping = TextWrapping.Wrap,
                Text = "/?/",
            };
            Grid.SetRow(preview, 0);
            Grid.SetColumn(preview, 2);
            Grid.SetRowSpan(preview, Core.NDIM);
            grid.Children.Add(preview);

            void UpdatePreview()
            {
                var v = new double[Core.NDIM];
                for (int i = 0; i < Core.NDIM; i++)
                    v[i] = boxes[i].Value;
                var vec = string.Join(",", Array.ConvertAll(v,
                    x => x.ToString("F4")));
                preview.Text = Core.Reverse(vec, 3) ?? "/?/";
            }

            /* live preview only after 200 ms without further edits */
            int previewToken = 0;
            void SchedulePreview()
            {
                int t = ++previewToken;
                DispatcherQueue.TryEnqueue(async () =>
                {
                    await System.Threading.Tasks.Task.Delay(200);
                    if (t != previewToken) return;
                    UpdatePreview();
                });
            }
            foreach (var box in boxes)
                box.ValueChanged += (s, e2) => SchedulePreview();

            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "Vector editor (live reverse preview)",
                Content = new ScrollViewer
                {
                    MaxHeight = 480,
                    Content = grid,
                },
                PrimaryButtonText = "Use in reverse box",
                CloseButtonText = "Close",
            };
            dlg.PrimaryButtonClick += (s, e2) =>
            {
                var v = new double[Core.NDIM];
                for (int i = 0; i < Core.NDIM; i++)
                    v[i] = boxes[i].Value;
                VecInput.Text = string.Join(",", Array.ConvertAll(v,
                    x => x.ToString("F4")));
            };
            await dlg.ShowAsync();
        }

        private async void History_Click(object sender, RoutedEventArgs e)
        {
            if (_history.Count == 0)
            {
                SetStatus("no history yet");
                return;
            }
            var list = new ListView
            {
                Height = 360,
                SelectionMode = ListViewSelectionMode.Single,
            };
            foreach (var h in _history)
                list.Items.Add(h.Title);
            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "History",
                Content = list,
                PrimaryButtonText = "Show",
                CloseButtonText = "Close",
            };
            dlg.PrimaryButtonClick += (s, e2) =>
            {
                if (list.SelectedIndex >= 0 &&
                    list.SelectedIndex < _history.Count)
                    AppendOutput("=== History: " +
                                 _history[list.SelectedIndex].Title +
                                 " ===\n" + _history[list.SelectedIndex].Body);
            };
            await dlg.ShowAsync();
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetWindowPos(IntPtr hWnd,
            IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern int GetSystemMetrics(int nIndex);

        [System.Runtime.InteropServices.StructLayout(
            System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct POINT32 { public int X; public int Y; }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool GetCursorPos(out POINT32 lpPoint);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern short GetAsyncKeyState(int vKey);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetCursorPos(int X, int Y);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool ScreenToClient(IntPtr hWnd,
            ref POINT32 lpPoint);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool ClientToScreen(IntPtr hWnd,
            ref POINT32 lpPoint);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern uint GetDpiForWindow(IntPtr hwnd);

        private void ApplyTheme(string name)
        {
            _themeName = name;
            try
            {
                var root = Content.XamlRoot?.Content as FrameworkElement;
                if (root == null) return;
                ElementTheme theme;
                switch (name)
                {
                    case "Light": theme = ElementTheme.Light; break;
                    case "Dark": theme = ElementTheme.Dark; break;
                    default: theme = ElementTheme.Default; break;
                }
                root.RequestedTheme = theme;
                /* the Mica backdrop follows the window theme, so the XAML
                 * containers stay transparent (no explicit backgrounds);
                 * force a re-layout so theme brushes repaint */
                root.InvalidateMeasure();
                root.InvalidateArrange();
                root.UpdateLayout();
                if (_appWindow != null)
                    ApplyTitleBarTheme(_appWindow);
                SetStatus("theme: " + name.ToLowerInvariant());
            }
            catch (Exception ex) { LogExt("apply theme err " + ex.Message); }
        }

        private void Loop_Click(object sender, RoutedEventArgs e)
        {
            string ipa = IpaInputRight.Text;
            if (string.IsNullOrWhiteSpace(ipa))
            {
                AppendOutput("=== IPA -> vectors ===\n" +
                             "Nothing to convert - type or click an IPA symbol first.");
                return;
            }
            var rows = Core.ForwardWithTone(ipa, out var ferr);
            if (rows.Length == 0)
            {
                AppendOutput("=== Loop ===\nparse error" +
                             (ferr != null ? ": " + ferr : ""));
                return;
            }
            int width = (int)WidthSlider.Value;
            if (width < 0) width = 3;
            var sb = new System.Text.StringBuilder();
            for (int s = 0; s < rows.Length; s++)
            {
                var (vec, annot) = rows[s];
                sb.AppendLine($"[{s}] vector: ({vec})");
                /* the 16-dim vector carries no tone; pass the annotation
                 * so the fit re-emits it (p̋ -> [p˥]) */
                sb.AppendLine($"    fit:   {Core.Reverse(vec + annot, width)}");
            }
            AppendOutput("=== IPA -> vector -> IPA (loop) ===\n" +
                         sb.ToString().TrimEnd());
            SetStatus("loop done");
        }

        private async void ExportCsv_Click(object sender, RoutedEventArgs e)
        {
            var file = await PickSaveFileAsync("ipa2vec-table.csv",
                "CSV", ".csv");
            if (file == null) return;
            try
            {
                /* quote every cell: vectors contain commas */
                var sb = new System.Text.StringBuilder();
                foreach (var raw in Core.Table().Split('\n'))
                {
                    var cells = raw.Split('\t');
                    for (int i = 0; i < cells.Length; i++)
                    {
                        if (i > 0) sb.Append(',');
                        sb.Append('"').Append(cells[i].Replace("\"", "\"\"")).Append('"');
                    }
                    sb.AppendLine();
                }
                await Windows.Storage.FileIO.WriteTextAsync(file, sb.ToString());
                SetStatus("CSV saved: " + file.Path);
            }
            catch (Exception ex)
            {
                SetStatus("CSV save failed: " + ex.Message);
            }
        }

        private bool _zh;

        private bool _leftCollapsed;
        private bool _rightCollapsed;
        private double _savedLeftWidth = 560;
        private bool _gripMoved;   /* the press turned into a drag */

        /* the grip button's template handles PointerPressed internally
         * (marked as handled), so the splitter needs the events with
         * handledEventsToo to start dragging from the button itself */
        private void WireSplitGrip()
        {
            try
            {
                SplitGrip.AddHandler(UIElement.PointerPressedEvent,
                    new PointerEventHandler(Splitter_Pressed), true);
                SplitGrip.AddHandler(UIElement.PointerMovedEvent,
                    new PointerEventHandler(Splitter_Moved), true);
                SplitGrip.AddHandler(UIElement.PointerReleasedEvent,
                    new PointerEventHandler(Splitter_Released), true);
                SplitGrip.AddHandler(UIElement.PointerCanceledEvent,
                    new PointerEventHandler(Splitter_Released), true);
                SplitGrip.AddHandler(UIElement.PointerCaptureLostEvent,
                    new PointerEventHandler(Splitter_Released), true);
            }
            catch (Exception ex) { LogExt("split grip wire err " + ex.Message); }
        }

        private void Splitter_Pressed(object sender, PointerRoutedEventArgs e)
        {
            var pt = e.GetCurrentPoint(SplitHit);
            if (pt.Properties.IsRightButtonPressed)
            {
                _drag = false;  /* right press: collapse right (RightTapped) */
                return;
            }
            _drag = true;
            _gripMoved = false;
            _dragStartX = e.GetCurrentPoint(null).Position.X;
            /* dragging out of a collapsed pane restores both panes */
            if (_leftCollapsed)
            {
                _leftCollapsed = false;
                LeftCol.Width = new GridLength(480);
            }
            if (_rightCollapsed)
            {
                _rightCollapsed = false;
                RightCol.Width = new GridLength(1, GridUnitType.Star);
            }
            _dragStartWidth = LeftCol.ActualWidth;
            /* the cursor snaps onto the divider line itself so the drag
             * has no offset (pressing anywhere in the 12px hit strip) */
            SnapCursorToLine();
            SplitHit.CapturePointer(e.Pointer);
            SetResizeCursor(true);
            e.Handled = true;
        }

        private void Splitter_Moved(object sender, PointerRoutedEventArgs e)
        {
            if (!_drag) return;
            double dx = e.GetCurrentPoint(null).Position.X - _dragStartX;
            if (Math.Abs(dx) > 4) _gripMoved = true;
            double w = _dragStartWidth + dx;
            if (w < 480) w = 480;
            if (w > 1400) w = 1400;
            if (w >= 480)
            {
                _leftCollapsed = false;
                LeftCol.Width = new GridLength(w);
            }
        }

        /* pull the cursor onto the divider line (same x as the line) */
        private void SnapCursorToLine()
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                GetCursorPos(out var cur);
                double scale = DpiScale();
                var pt = new POINT32
                {
                    X = (int)((LeftCol.ActualWidth + 6) * scale),
                    Y = cur.Y,
                };
                ClientToScreen(hwnd, ref pt);
                SetCursorPos(pt.X, pt.Y);
            }
            catch (Exception ex) { LogExt("snap cursor err " + ex.Message); }
        }

        private void Splitter_Released(object sender, PointerRoutedEventArgs e)
        {
            if (!_drag) return;
            _drag = false;
            SetResizeCursor(false);
            SplitHit.ReleasePointerCapture(e.Pointer);
        }

        private InputSystemCursor? _resizeCursor;

        private void SetResizeCursor(bool on)
        {
            try
            {
                if (on)
                {
                    _resizeCursor ??= InputSystemCursor.Create(
                        InputSystemCursorShape.SizeWestEast);
                    SplitHit.SetPointerCursor(_resizeCursor);
                }
                else
                {
                    SplitHit.SetPointerCursor(null);
                }
            }
            catch (Exception ex) { LogExt("resize cursor err " + ex.Message); }
        }

        /* the divider shows a resize cursor (and nothing else) */
        private void SplitHit_PointerEntered(object sender,
            PointerRoutedEventArgs e)
        {
            SetResizeCursor(true);
        }

        private void SplitHit_PointerExited(object sender,
            PointerRoutedEventArgs e)
        {
            if (!_drag) SetResizeCursor(false);
        }

        private bool _snapped;   /* the cursor is stuck to the divider */
        private int _lastCursorX;
        private long _lastMoveTick;
        private IntPtr _cursorHwnd = IntPtr.Zero;
        private double _cursorScale;
        private bool _cursorDpiCached;
        private long _lastCursorMoveTick;

        /* magnetic line: while the pointer glides past the divider it is
         * pulled onto the line itself and held there (slow moves keep
         * being pulled back, a fast flick escapes); skipped while
         * dragging, in external mode or while Ctrl is held; moves are
         * throttled to 16 ms and the hwnd/DPI are cached (the hot path
         * used to issue 4 P/Invokes per mouse move) */
        private void WireCursorMagnet()
        {
            try
            {
                if (Content is Grid root)
                    root.AddHandler(UIElement.PointerMovedEvent,
                        new PointerEventHandler(CursorMagnet_Moved), true);
            }
            catch (Exception ex) { LogExt("cursor magnet wire err " + ex.Message); }
        }

        private void CursorMagnet_Moved(object sender,
            PointerRoutedEventArgs e)
        {
            try
            {
                if (_drag || _externalMode || _widthOpen) return;
                long now = Environment.TickCount64;
                if (now - _lastCursorMoveTick < 16) return;
                _lastCursorMoveTick = now;
                if ((GetAsyncKeyState(0x11 /* VK_CONTROL */) & 0x8000) != 0)
                    return;
                var hwnd = _cursorHwnd;
                double scale;
                if (!_cursorDpiCached)
                {
                    hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                    scale = GetDpiForWindow(hwnd);
                    if (scale == 0) scale = 96;
                    scale /= 96.0;
                    if (scale < 1.0) scale = 1.0;
                    _cursorHwnd = hwnd;
                    _cursorScale = scale;
                    _cursorDpiCached = true;
                }
                else scale = _cursorScale;
                GetCursorPos(out var cur);
                ScreenToClient(hwnd, ref cur);
                double lineX = LeftCol.ActualWidth + 6;   /* DIP */
                int lineXPhys = (int)(lineX * scale);
                double dist = Math.Abs(cur.X / scale - lineX);
                double dt = Math.Max((now - _lastMoveTick) / 1000.0, 1e-3);
                _lastMoveTick = now;
                if (_snapped)
                {
                    /* escape when the pointer moves faster than
                     * 6 DIP per 60fps frame (i.e. 360 DIP/s), scaled by
                     * the actual DPI and measured frame interval */
                    double escapePhys = 6 * scale * 60;   /* px/s */
                    double speedPhys = Math.Abs(cur.X - _lastCursorX) / dt;
                    if (speedPhys > escapePhys)
                    {
                        _snapped = false;
                    }
                    else if (Math.Abs(cur.X - lineXPhys) > 1)
                    {
                        var pt = new POINT32 { X = lineXPhys, Y = cur.Y };
                        ClientToScreen(hwnd, ref pt);
                        SetCursorPos(pt.X, pt.Y);
                        _lastCursorX = lineXPhys;
                        return;
                    }
                }
                else if (dist < MagnetRadius)
                {
                    _snapped = true;
                    var pt = new POINT32 { X = lineXPhys, Y = cur.Y };
                    ClientToScreen(hwnd, ref pt);
                    SetCursorPos(pt.X, pt.Y);
                    _lastCursorX = lineXPhys;
                    return;
                }
                _lastCursorX = cur.X;
            }
            catch (Exception ex) { LogExt("magnet err " + ex.Message); }
        }

        /* collapse / restore one pane; the other always stretches */
        private void SetPaneCollapsed(bool left, bool collapse)
        {
            if (collapse)
            {
                _savedLeftWidth = LeftCol.ActualWidth > 0
                    ? LeftCol.ActualWidth : _savedLeftWidth;
                if (left)
                {
                    _leftCollapsed = true;
                    LeftCol.Width = new GridLength(0);
                    RightCol.Width = new GridLength(1, GridUnitType.Star);
                }
                else
                {
                    _rightCollapsed = true;
                    RightCol.Width = new GridLength(0);
                    LeftCol.Width = new GridLength(1, GridUnitType.Star);
                }
            }
            else if (left)
            {
                _leftCollapsed = false;
                LeftCol.Width = new GridLength(_savedLeftWidth);
                RightCol.Width = new GridLength(1, GridUnitType.Star);
            }
            else
            {
                _rightCollapsed = false;
                RightCol.Width = new GridLength(1, GridUnitType.Star);
                LeftCol.Width = new GridLength(_savedLeftWidth);
            }
        }

        /* left click on the grip: collapse the left pane, expand right */
        private void SplitGrip_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_gripMoved) return;   /* a drag is not a click */
                SetPaneCollapsed(true, !_leftCollapsed);
            }
            catch (Exception ex) { LogExt("grip click err " + ex.Message); }
        }

        /* left double click on the divider itself: reset both panes to
         * the default widths */
        private void SplitHit_DoubleTapped(object sender,
            DoubleTappedRoutedEventArgs e)
        {
            try
            {
                _leftCollapsed = false;
                _rightCollapsed = false;
                _savedLeftWidth = DefaultSplitWidth;
                LeftCol.Width = new GridLength(DefaultSplitWidth);
                RightCol.Width = new GridLength(1, GridUnitType.Star);
                e.Handled = true;
            }
            catch (Exception ex) { LogExt("split dbl-tap err " + ex.Message); }
        }

        /* right click: collapse the right pane and expand the left */
        private void SplitGrip_RightTapped(object sender,
            RightTappedRoutedEventArgs e)
        {
            try
            {
                SetPaneCollapsed(false, !_rightCollapsed);
                e.Handled = true;
            }
            catch (Exception ex) { LogExt("grip right-tap err " + ex.Message); }
        }

        private readonly List<string> _allCons = new();
        private readonly List<string> _allNp = new();
        private readonly List<string> _allVow = new();
        private readonly List<string> _allDiac = new();
        private readonly List<string> _allLet = new();
        private readonly List<string> _allTone = new();
        private readonly List<string> _favorites = new();
        private string _favPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "vec4ipa", "favorites.txt");

        /* manner weight from the symbol's info text, for an intuitive
         * plosive -> affricate -> fricative -> nasal -> lateral -> tap ->
         * trill -> approximant order (IPA chart rows) */
        private static int MannerWeight(string info)
        {
            if (info.Contains(".pls")) return 0;
            if (info.Contains(".afc")) return 1;
            if (info.Contains(".frc")) return 2;
            if (info.Contains(".nas")) return 3;
            if (info.Contains(".lat")) return 4;
            if (info.Contains(".tap") || info.Contains(".flp")) return 5;
            if (info.Contains(".trl")) return 6;
            if (info.Contains(".appr") || info.Contains(".apx")) return 7;
            return 8;
        }

        /* non-pulmonic: group by airstream type first */
        private static int AirstreamWeight(string info)
        {
            if (info.Contains("egressive")) return 0;   /* ejectives */
            if (info.Contains("ingressive")) return 1;  /* implosives */
            if (info.Contains("lingual")) return 2;     /* clicks */
            if (info.Contains("percussive")) return 3;
            return 4;
        }

        private void BuildKeyboard()
        {
            try { _favorites.AddRange(File.ReadAllLines(_favPath)); }
            catch (Exception ex) { LogExt("favorites read err " + ex.Message); }
            /* dedupe and cap */
            var seen = new HashSet<string>();
            _favorites.RemoveAll(s => !seen.Add(s));
            if (_favorites.Count > MaxFavorites)
                _favorites.RemoveRange(MaxFavorites,
                    _favorites.Count - MaxFavorites);

            var consPos = Core.ConsPositions();
            double Pos(string s) =>
                consPos.TryGetValue(s, out var d) ? d : 0.5;

            _allCons.Clear();
            _allCons.AddRange(Core.KeyboardCons()
                .OrderBy(s => MannerWeight(Info(s)))
                .ThenBy(Pos));
            _allCons.AddRange(TieComposites);
            _allNp.Clear();
            /* non-pulmonic: airstream class comes from the DLL (derived
             * from the vector, not the table's distance-model field) */
            var npClass = Core.KeyboardConsNp();
            _allNp.AddRange(npClass.Keys
                .OrderBy(s => npClass[s])
                .ThenBy(s => MannerWeight(Info(s)))
                .ThenBy(Pos));

            var pos = Core.VowelPositions();
            _allVow.Clear();
            _allVow.AddRange(Core.KeyboardVowels().OrderBy(s =>
            {
                (int Row, int Col) p = pos.TryGetValue(s, out var v)
                    ? v : (0, 0);
                return p.Row * 100 + p.Col;
            }));

            var tiers = Core.ModTiers();
            int Tier(string s) => tiers.TryGetValue(s, out var t) ? t : 6;
            _allDiac.Clear();
            _allDiac.AddRange(Core.KeyboardMods()
                .Where(IsCombiningModifier).OrderBy(Tier));
            _allDiac.Add("\u25CC");   /* dotted-circle placeholder key */
            _allLet.Clear();
            _allLet.AddRange(Core.KeyboardMods()
                .Where(m => !IsCombiningModifier(m)).OrderBy(Tier));
            _allTone.Clear();
            _allTone.AddRange(Core.KeyboardTones());

            RebuildKeyboard("");
        }

        private string Info(string sym)
        {
            if (!_symInfo.TryGetValue(sym, out var info))
            {
                info = QuerySymbol(sym);
                _symInfo[sym] = info;
            }
            return info;
        }

        /* rebuild every section applying the current filter */
        private void RebuildKeyboard(string filter)
        {
            _kbButtons.Clear();
            /* recent keys are rebuilt from scratch below; drop buttons
             * of filtered-out symbols so no stale button stays mapped
             * (a removed symbol re-typed would otherwise hit it) */
            _recentBtns.Clear();
            var placed = new HashSet<string>();
            bool Matches(string sym)
            {
                if (filter.Length == 0) return true;
                if (sym.Contains(filter)) return true;
                var info = Info(sym);
                if (info.Contains(filter, StringComparison.OrdinalIgnoreCase))
                    return true;
                /* Chinese UI: also match the translated feature names */
                if (_zh && TranslateTerms(info).Contains(filter))
                    return true;
                return false;
            }
            ConsKeys.Items.Clear();
            NpKeys.Items.Clear();
            VowKeys.Items.Clear();
            DiacKeys.Items.Clear();
            LetterKeys.Items.Clear();
            ToneKeys.Items.Clear();
            FavKeys.Items.Clear();
            RecentKeys.Items.Clear();

            foreach (var s in _allCons.Where(Matches))
            {
                placed.Add(s);
                ConsKeys.Items.Add(MakeKey(s));
            }
            if (ConsKeys.Items.Count == 0) ConsKeys.Items.Add(new TextBlock
            {
                Text = "(no matches)", Foreground =
                    new Microsoft.UI.Xaml.Media.SolidColorBrush(
                        Microsoft.UI.Colors.Gray), Margin = new Thickness(4, 2, 0, 2),
            });
            foreach (var s in _allNp.Where(Matches))
            {
                placed.Add(s);
                NpKeys.Items.Add(MakeKey(s));
            }
            foreach (var s in _allVow.Where(Matches))
            {
                placed.Add(s);
                VowKeys.Items.Add(MakeKey(s));
            }
            foreach (var s in _allDiac.Where(Matches))
            {
                placed.Add(s);
                DiacKeys.Items.Add(MakeKey(s, fontSize: 20));
            }
            foreach (var s in _allLet.Where(Matches))
            {
                placed.Add(s);
                LetterKeys.Items.Add(MakeKey(s, fontSize: 16));
            }
            foreach (var s in _allTone.Where(Matches))
            {
                placed.Add(s);
                ToneKeys.Items.Add(MakeKey(s));
            }

            LblFav.Visibility = _favorites.Count > 0
                ? Visibility.Visible : Visibility.Collapsed;
            if (_favorites.Count > 0)
                foreach (var s in _favorites.Where(Matches))
                {
                    placed.Add(s);
                    FavKeys.Items.Add(MakeKey(s));
                }
            foreach (var s in _recent.Where(Matches))
            {
                /* a symbol already visible in a section needs no second
                 * key (it would double up in _kbButtons hit-testing) */
                if (!placed.Add(s)) continue;
                var btn = MakeKey(s);
                _recentBtns[s] = btn;
                RecentKeys.Items.Add(btn);
            }
        }

        private int _filterToken;

        /* every keystroke rebuilds the whole keyboard (hundreds of
         * P/Invokes); debounce so only the final filter is applied */
        private void FilterBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            int token = ++_filterToken;
            DispatcherQueue.TryEnqueue(async () =>
            {
                await System.Threading.Tasks.Task.Delay(200);
                if (token != _filterToken) return;
                RebuildKeyboard(FilterBox.Text.Trim());
            });
        }

        private void LblFav_Tapped(object sender, TappedRoutedEventArgs e)
        {
            ScrollToSection(LblFav);
        }

        /* ---- hover preview (in-window overlay, never swallows clicks) ---- */

        private Canvas? _hoverCanvas;
        private int _hoverToken;

        private void ScheduleHover(Button btn, string sym)
        {
            int token = ++_hoverToken;
            DispatcherQueue.TryEnqueue(async () =>
            {
                await System.Threading.Tasks.Task.Delay(50);
                if (token != _hoverToken || !btn.IsPointerOver) return;
                ShowHover(btn, sym);
            });
        }

        private void CancelHover()
        {
            _hoverToken++;
            HideHoverPreview();
        }

        /* the preview is a plain child of the root grid: a real popup is
         * its own HWND and swallows the mouse even with IsHitTestVisible
         * false, which broke clicking under it (e.g. external mode) */
        private Canvas EnsureHoverCanvas()
        {
            if (_hoverCanvas != null) return _hoverCanvas;
            if (Content is Grid root)
            {
                _hoverCanvas = new Canvas { IsHitTestVisible = false };
                root.Children.Add(_hoverCanvas);
            }
            return _hoverCanvas!;
        }

        private void ShowHover(Button btn, string sym)
        {
            try
            {
                /* split the query text into: name (line 2) and
                 * airstream / tier (line 3), e.g. k' / vel.ejt / egressive
                 * or ◌̤ / breathy / tier=2 */
                string raw = _symInfo[sym];
                string air = "";
                string name;
                if (raw.StartsWith("modifier:"))
                {
                    var parts = raw.Split(new[] { "  " },
                        StringSplitOptions.RemoveEmptyEntries);
                    name = parts.Length > 1 ? parts[1].Trim()
                                            : raw.Replace("modifier: ", "").Trim();
                    air = parts.Length > 2 ? parts[2].Trim() : "";
                }
                else
                {
                    var m = System.Text.RegularExpressions.Regex.Match(
                        raw, @"\(([^()]+)\)");
                    if (m.Success)
                        air = m.Groups[1].Value;
                    name = System.Text.RegularExpressions.Regex.Replace(
                        raw, @"\([^()]*\)", "");
                    name = System.Text.RegularExpressions.Regex.Replace(
                        name, @"^(?:extIPA )?base: /[^/]*/\s*", "");
                    name = System.Text.RegularExpressions.Regex.Replace(
                        name, @"^(?:modifier|alias):\s*", "");
                    name = name.Trim();
                }
                if (_zh)
                {
                    name = TranslateTerms(name);
                    air = TranslateTerms(air);
                }
                var canvas = EnsureHoverCanvas();
                if (canvas == null) return;
                canvas.Children.Clear();
                /* follow the actual (effective) theme */
                bool dark = (Content.XamlRoot.Content as FrameworkElement)
                    ?.ActualTheme == ElementTheme.Dark;
                var stack = new StackPanel { Spacing = 4 };
                var border = new Border
                {
                    MaxWidth = 480,
                    Padding = new Thickness(10, 6, 10, 6),
                    CornerRadius = new CornerRadius(6),
                    Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(
                        Microsoft.UI.ColorHelper.FromArgb(
                            245, (byte)(dark ? 40 : 245),
                            (byte)(dark ? 40 : 245),
                            (byte)(dark ? 40 : 245))),
                    Child = stack,
                };
                var fg = new Microsoft.UI.Xaml.Media.SolidColorBrush(
                    Microsoft.UI.ColorHelper.FromArgb(
                        255, (byte)(dark ? 240 : 20),
                        (byte)(dark ? 240 : 20),
                        (byte)(dark ? 240 : 20)));
                stack.Children.Add(new TextBlock
                {
                    Text = sym,
                    /* combining diacritics need a larger glyph */
                    FontSize = IsCombiningModifier(sym) ? HoverGlyphLarge
                                                        : HoverGlyph,
                    Foreground = fg,
                    FontFamily = IpaFont,
                });
                stack.Children.Add(new TextBlock
                {
                    Text = name,
                    FontSize = 13,
                    Foreground = fg,
                    TextWrapping = TextWrapping.Wrap,
                    MaxWidth = 420,
                });
                stack.Children.Add(new TextBlock
                {
                    Text = air,
                    FontSize = 13,
                    Foreground = fg,
                    TextWrapping = TextWrapping.Wrap,
                    MaxWidth = 420,
                });
                canvas.Children.Add(border);

                var transform = btn.TransformToVisual(
                    Content.XamlRoot.Content as UIElement);
                var pt = transform.TransformPoint(
                    new Windows.Foundation.Point(0, 0));
                double h = btn.ActualHeight;
                Canvas.SetLeft(border, Math.Max(0, pt.X - 8));
                Canvas.SetTop(border, Math.Max(0, pt.Y - h - 46));
            }
            catch (Exception ex) { LogExt("hover err " + ex.Message); }
        }

        private void HideHoverPreview()
        {
            if (_hoverCanvas != null) _hoverCanvas.Children.Clear();
        }

        /* right-click symbol details: the glyph on top (large, Gentium),
         * the translated term name, then the vector and the aligned
         * feature=value table */
        private async void ShowSymbolDetail(string sym)
        {
            bool fav = _favorites.Contains(sym);
            string info = _zh ? TranslateTerms(_symInfo[sym]) : _symInfo[sym];
            /* drop the vector line from the query text; we rebuild it
             * aligned below */
            info = string.Join("\n", info.Split('\n')
                .Where(l => !l.TrimStart().StartsWith("(")));
            var glyph = new TextBlock
            {
                Text = sym,
                FontSize = 24,
                FontFamily = IpaFont,
                TextWrapping = TextWrapping.Wrap,
            };
            var terms = new TextBlock
            {
                Text = info,
                FontSize = 14,
                TextWrapping = TextWrapping.Wrap,
            };
            var body = new StackPanel { Spacing = 8, Children = { glyph, terms } };

            /* vector + tab-aligned feature = value table */
            string tableText = "";
            var rows = Core.ForwardRaw(sym);
            if (rows != null && rows.Length > 0)
            {
                var v = rows[0];
                var names = Core.DimNames;
                var sb = new System.Text.StringBuilder();
                sb.Append("(");
                for (int i = 0; i < Core.NDIM; i++)
                    sb.Append(i == 0 ? $"{v[i]:F4}" : $", {v[i]:F4}");
                sb.AppendLine(")");
                for (int i = 0; i < Core.NDIM; i++)
                    sb.AppendLine($"{names[i]}\t{v[i]:F4}");
                tableText = sb.ToString();
                body.Children.Add(new ScrollViewer
                {
                    MaxHeight = 220,
                    HorizontalScrollBarVisibility =
                        Microsoft.UI.Xaml.Controls.ScrollBarVisibility.Auto,
                    VerticalScrollBarVisibility =
                        Microsoft.UI.Xaml.Controls.ScrollBarVisibility.Auto,
                    Content = new TextBlock
                    {
                        Text = tableText,
                        FontSize = 13,
                        FontFamily = new Microsoft.UI.Xaml.Media.FontFamily(
                            "Consolas"),
                        TextWrapping = TextWrapping.NoWrap,
                    },
                });
            }

            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = _zh ? $"符号 {sym}" : $"Symbol {sym}",
                Content = body,
                PrimaryButtonText = fav
                    ? (_zh ? "从收藏移除" : "Remove from favorites")
                    : (_zh ? "加入收藏" : "Add to favorites"),
                SecondaryButtonText = _zh ? "复制" : "Copy",
                CloseButtonText = _zh ? "确定" : "OK",
            };
            string copyText = sym + "\n" + info +
                              (tableText.Length > 0 ? "\n" + tableText : "");
            dlg.SecondaryButtonClick += (s2, e2) =>
            {
                CopyToClipboard(copyText);
            };
            dlg.PrimaryButtonClick += (s2, e2) => ToggleFavorite(sym);
            await dlg.ShowAsync();
        }

        private void ToggleFavorite(string sym)
        {
            if (_favorites.Contains(sym))
                _favorites.Remove(sym);
            else
                _favorites.Add(sym);
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(_favPath)!);
                File.WriteAllLines(_favPath, _favorites);
            }
            catch (Exception ex) { LogExt("favorites write err " + ex.Message); }
            RebuildKeyboard(FilterBox.Text.Trim());
        }

        private static readonly string[] TieComposites =
        {
            "t͡ʃ", "d͡ʒ", "t͡s", "d͡z", "t͡ɕ", "d͡ʑ",
            "ʈ͡ʂ", "ɖ͡ʐ", "k͡p", "ɡ͡b", "k͡x", "q͡χ", "ŋ͡m",
        };

        private readonly Dictionary<string, string> _symInfo = new();
        private readonly List<(string Sym, Button Btn)> _kbButtons = new();
        private readonly List<string> _recent = new();
        private readonly Dictionary<string, Button> _recentBtns = new();
        private readonly List<(string Title, string Body)> _history = new();
        private bool _featureNames;
        private bool _placeholder;   // IPA input still holds the welcome example
        private bool _programmatic;  // text changes made by code (not the user)

        /* query a symbol; a dotted-circle prefix (◌) is stripped so the
         * display never shows the "dotted circle (placeholder)" entry */
        /* IPA feature abbreviations -> Chinese (for tooltips/details) */
        private static readonly Dictionary<string, string> TermMap =
            new()
            {
                { "vl", "清" }, { "vd", "浊" }, { "asp", "送气" },
                { "blab", "双唇" }, { "bil", "双唇" }, { "lab", "唇" },
                { "lab.dnt", "唇齿" }, { "lab.vel", "唇–软腭" },
                { "lab.pal", "唇–硬腭" }, { "lbd", "唇齿" },
                { "dnt", "齿" }, { "den", "齿" },
                { "alv", "龈" }, { "rfl", "卷舌" }, { "alvpal", "龈–腭" },
                { "pst", "龈后" }, { "pal", "腭" }, { "vel", "软腭" },
                { "uvu", "小舌" }, { "pha", "咽" }, { "epl", "会厌" },
                { "phr", "咽" }, { "epi", "会厌" }, { "glo", "喉" },
                { "glt", "喉" },
                { "pls", "爆发音" }, { "nas", "鼻" }, { "frc", "擦音" },
                { "appr", "近音" }, { "apx", "近音" },
                { "lat", "边音" }, { "tap", "拍音" }, { "flp", "闪音" },
                { "trl", "颤音" }, { "trill", "颤音" },
                { "afc", "塞擦音" }, { "afr", "塞擦音" },
                { "per", "敲击" },
                { "vwl", "元音" }, { "cls", "高" }, { "ncls", "次高" },
                { "cmid", "半高" }, { "omid", "半开" }, { "nopn", "次开" },
                { "mid", "中" }, { "opn", "开" },
                { "unr", "不圆唇" }, { "rnd", "圆唇" },
                { "cnt", "央" }, { "cent", "央" },
                { "fr", "前" }, { "front", "前" },
                { "bk", "后" }, { "back", "后" },
                { "rhot", "r 色彩" }, { "ej", "喷" }, { "ejt", "喷音" },
                { "clk", "啧音" }, { "imp", "内爆音" },
                { "pulmonic", "肺部气流" }, { "glottalic egressive", "喷音" },
                { "glottalic ingressive", "内爆音" }, { "lingual", "啧音" },
                { "percussive", "敲击音" },
                /* modifier-detail framework words */
                { "modifier: ", "修饰符：" },
                { "extIPA base: ", "extIPA 基段：" },
                { "base: ", "基段：" },
                { "alias: ", "别名：" },
                { "dotted circle", "点圆圈" }, { "placeholder", "占位符" },
                { "tier=", "层级=" },
                { "[sets airstream]", "[设置气流]" },
                { "[inference]", "[推断]" },
                /* superscript / subscript letters */
                { "sup_rhot_ʢ", "r 色彩上标ʢ" }, { "sup_rhot_ʕ", "r 色彩上标ʕ" },
                { "sup_rhot_ʁ", "r 色彩上标ʁ" }, { "sup_rhot_r", "r 色彩上标r" },
                { "sup_e", "上标e" }, { "sup_u", "上标u" },
                { "sup_O", "上标O" }, { "sup_U", "上标U" },
                { "sup_W", "上标W" }, { "sup_eps", "上标ɛ" },
                { "sup_d", "上标d" }, { "sup_B", "上标B" },
                { "sup_P", "上标P" }, { "sup_N", "上标N" },
                { "sup_A", "上标A" },
                { "sub_i", "下标i" }, { "sub_r", "下标r" },
                { "bidental", "双齿" }, { "velophar", "咽软腭" },
                /* tone names */
                { "tone_5", "最高" }, { "tone_4", "高" },
                { "tone_3", "中" }, { "tone_2", "低" }, { "tone_1", "最低" },
                { "tone_high", "高平" }, { "tone_low", "低平" },
                { "tone_fall", "降调" }, { "tone_rise", "升调" },
                { "tone_extralow", "特低" }, { "tone_lowfall", "低降" },
                { "tone_lowrise", "低升" }, { "tone_highv", "高" },
                { "tone_lowv", "低" },
                { "pitch_0", "音高0" }, { "pitch_1", "音高1" },
                { "pitch_2", "音高2" }, { "pitch_3", "音高3" },
                { "pitch_4", "音高4" }, { "pitch_5", "音高5" },
                { "pitch_6", "音高6" }, { "pitch_7", "音高7" },
                { "pitch_8", "音高8" }, { "pitch_9", "音高9" },
                { "pitch_highrise", "高升" }, { "pitch_highfall", "高降" },
                { "pitch_lowrise", "低升" },
                { "pitch_risefall", "升降" }, { "pitch_fallrise", "降升" },
                { "sandhi_5", "变调5" }, { "sandhi_4", "变调4" },
                { "sandhi_3", "变调3" }, { "sandhi_2", "变调2" },
                { "sandhi_1", "变调1" },
                { "class1", "阴平" }, { "class2", "阳平" },
                { "class3", "阴上" }, { "class4", "阳上" },
                { "class5", "阴去" }, { "class6", "阳去" },
                { "class7", "阴入" }, { "class8", "阳入" },
                { "upstep", "升阶" }, { "downstep", "降阶" },
                { "global_up", "全局升" }, { "global_down", "全局降" },
                { "macron_tone", "长音调" }, { "sliding", "滑动" },
                /* common modifier names */
                { "short", "短" }, { "long", "长" },
                { "lengthened", "延长" }, { "gemination", "重叠" },
                { "half", "半长" }, { "unrel", "无闻除阻" },
                { "fric_release", "擦除阻" }, { "lat_release", "边除阻" },
                { "nasal_rel", "鼻除阻" }, { "nas_rel", "鼻化除阻" },
                { "adv", "前移" }, { "retr", "后移" },
                { "rtr", "舌根后缩" }, { "atr", "舌根前伸" },
                { "raised", "抬高" }, { "lowered", "降低" },
                { "centralized", "央化" }, { "midcent", "中央" },
                { "breathy", "气声" }, { "breathy_asp", "气声送气" },
                { "creaky", "嘎裂声" }, { "fortis", "强" },
                { "lenis", "弱" }, { "weak_asp", "弱送气" },
                { "whistled", "哨音" }, { "syl", "成音节" },
                { "nsyl", "不成音节" }, { "link", "连接" },
                { "tie", "连音线" }, { "stress_1", "主重音" },
                { "stress_2", "次重音" }, { "dark", "软腭化" },
                { "light", "清亮" },
                { "pal_hook", "腭化钩" }, { "pal_prime", "腭化撇" },
                { "lab_subw", "唇化下标w" }, { "labiodental", "唇齿" },
                { "linguolabial", "舌唇" }, { "dental", "齿" },
                { "alveolar", "龈" }, { "apical", "舌尖" },
                { "laminal", "舌叶" }, { "retroflex", "卷舌" },
                { "phar", "咽化" }, { "glottal_onset", "喉塞起始" },
                { "nas_click", "鼻啧音" },
                { "schwa_rel", "ə化" }, { "offglide", "滑音" },
                { "rnd_less", "少圆唇" }, { "rnd_more", "多圆唇" },
                { "lam", "舌叶" },
            };

        /* translate feature abbreviations in symbol details. Keys are
         * replaced only at token boundaries (not inside words), so e.g.
         * "fr" cannot corrupt "fric" and "lab" cannot corrupt "labial".
         * Longest keys first (omid before mid, labiodental before lab). */
        private static readonly KeyValuePair<string, string>[] TermSorted =
            TermMap.OrderByDescending(k => k.Key.Length).ToArray();

        private static string TranslateTerms(string text)
        {
            /* consonant names read 部位.清浊.方法 (vl.bil.pls -> bil.vl.pls),
             * never 清浊.部位.方法 */
            const string place = @"(?:blab|bil|lab\.dnt|lbd|lab|dnt|den|alv|alvpal|pst|rfl|pal|vel|uvu|pha|epl|glo|phr|epi|glt)";
            const string manner = @"(?:pls|nas|frc|apx|appr|lat|tap|flp|trl|afc|afr|per|clk|ejt|imp)";
            text = System.Text.RegularExpressions.Regex.Replace(text,
                @"\b(vl|vd)\.(" + place + @"(?:\.(?:" + place + @"))*)((?:\.(?:" + manner + @"))+)\b",
                "$2.$1$3");
            text = System.Text.RegularExpressions.Regex.Replace(text,
                @"\b(?<!\.)(" + place + @"(?:\.(?:" + place + @"))*)((?:\.(?:" + manner + @"))+)(\.(?:vl|vd))\b",
                "$1$3$2");
            foreach (var kv in TermSorted)
            {
                text = System.Text.RegularExpressions.Regex.Replace(
                    text,
                    @"(?<![\w])" + System.Text.RegularExpressions.Regex.Escape(kv.Key) +
                    @"(?![\w])",
                    kv.Value);
            }
            return text;
        }

        private static string QuerySymbol(string sym)
        {
            if (sym.Contains('\u25CC'))
                sym = sym.Replace("\u25CC", "");
            return Core.Query(sym);
        }

        private Button MakeKey(string sym, double fontSize = 14)
        {
            var btn = new Button
            {
                Content = sym,
                FontSize = fontSize,
                MinWidth = KeyMinWidth,
                MinHeight = KeyMinHeight,
                Padding = new Thickness(3, 2, 3, 2),
                Margin = new Thickness(2),
            };
            if (!_symInfo.ContainsKey(sym))
                _symInfo[sym] = QuerySymbol(sym);
            _kbButtons.Add((sym, btn));
            /* hover preview: glyph (24pt Gentium) over the term name,
             * shown after a short delay (system tooltips are too slow) */
            btn.PointerEntered += (s, e) => ScheduleHover(btn, sym);
            btn.PointerExited += (s, e) => CancelHover();
            btn.PointerPressed += (s, e) => CancelHover();
            /* left press starts glide mode; left release types via Click.
             * Gliding over neighbouring keys types while held down.
             * Right press shows the symbol details instead. */
            btn.PointerPressed += (s, e) =>
            {
                LogExt($"pressed sym='{sym}' external={_externalMode} " +
                       $"toggle={ExtToggle.IsChecked}");
                HideHoverPreview();
                try
                {
                    var pt = e.GetCurrentPoint(btn);
                    if (pt.Properties.IsRightButtonPressed)
                    {
                        _kbPressedBox = FocusManager.GetFocusedElement(
                            Content.XamlRoot) as TextBox;
                        ShowSymbolDetail(sym);
                        e.Handled = true;
                        return;
                    }
                    _kbPressedBox = FocusManager.GetFocusedElement(
                        Content.XamlRoot) as TextBox;
                }
                catch (Exception ex) { LogExt("key press err " + ex.Message); }
                if (_externalMode)
                {
                    /* global input: type immediately and swallow the
                     * press so this window never takes the focus */
                    AppendToInput(sym);
                    e.Handled = true;
                    return;
                }
                _slideMode = true;
                _slid = false;
            };
            btn.PointerEntered += (s, e) =>
            {
                LogExt($"entered sym='{sym}' external={_externalMode}");
                if (_slideMode)
                {
                    _slid = true;
                    AppendToInput(sym);
                }
            };
            btn.PointerReleased += (s, e) => _slideMode = false;
            btn.PointerCanceled += (s, e) => _slideMode = false;
            btn.PointerCaptureLost += (s, e) => _slideMode = false;
            btn.Click += (s, e) =>
            {
                if (!_slid && !_externalMode)
                    AppendToInput(sym);
                _slid = false;
            };
            return btn;
        }

        private void AppendToInput(string sym)
        {
            ThrottledLog.Kb($"{DateTime.Now:HH:mm:ss.fff}: append '{sym}' " +
                            $"pressed={_kbPressedBox?.GetType().Name ?? "null"} " +
                            $"focused={_focusedBox?.GetType().Name ?? "null"}");
            /* external mode: type into the foreground (other app) window;
             * first hand activation back to the external window so the
             * keystrokes land there and this app never keeps the focus */
            if (_externalMode)
            {
                string clean = sym.Contains('\u25CC') && sym.Length > 1
                    ? sym.Replace("\u25CC", "") : sym;
                if (_extTarget != IntPtr.Zero)
                    RestoreForeground(_extTarget);
                SendTextToForeground(clean);
                _kbPressedBox = null;
                return;
            }
            /* the soft keyboard types into the text box that currently
             * has focus (falling back to the IPA input); the filter box
             * never receives keyboard input - typing goes to the IPA box
             * while focus (and the caret) stays in the filter box */
            var source = _kbPressedBox ?? _focusedBox ?? IpaInputRight;
            var target = source == FilterBox ? IpaInputRight : source;
            _kbPressedBox = null;

            /* the welcome example ("tʰa") is a placeholder: the first
             * symbol the user picks replaces it instead of appending */
            if (target == IpaInputRight && _placeholder)
            {
                _programmatic = true;
                target.Text = "";
                _programmatic = false;
                _placeholder = false;
            }
            /* keyboard buttons show diacritics on a dotted circle (◌,
             * U+25CC) as a hint; strip the circle before inserting.
             * A lone ◌ (the placeholder key) is kept as-is. */
            if (sym.Length > 1 && sym.Contains('\u25CC'))
                sym = sym.Replace("\u25CC", "");
            /* combining modifiers (◌...) need a base symbol before them */
            if (target.Text.Length == 0 && IsCombiningModifier(sym))
            {
                SetStatus("start with a base symbol first (e.g. t, a), then add " + sym);
                return;
            }
            int pos = target.SelectionStart;
            _programmatic = true;
            target.Text = target.Text.Insert(pos, sym);
            target.SelectionStart = pos + sym.Length;
            _programmatic = false;
            /* keep focus in the box the user was editing (the filter box
             * keeps its caret even though the symbol went to the IPA box) */
            source.Focus(FocusState.Programmatic);
            if (target == IpaInputRight)
                ScrollRightInput();
            /* the removed recent button is dropped from the hit-test
             * list too, so _kbButtons stays bounded (it used to grow by
             * one Button per typed symbol) */
            if (_recentBtns.TryGetValue(sym, out var old))
            {
                RecentKeys.Items.Remove(old);
                _kbButtons.RemoveAll(x => x.Btn == old);
            }
            _recent.Remove(sym);
            _recent.Insert(0, sym);
            var btn = MakeKey(sym);
            _recentBtns[sym] = btn;
            RecentKeys.Items.Insert(0, btn);
            while (_recent.Count > MaxRecent)
            {
                string last = _recent[^1];
                _recent.RemoveAt(_recent.Count - 1);
                if (_recentBtns.Remove(last, out var b))
                {
                    RecentKeys.Items.Remove(b);
                    _kbButtons.RemoveAll(x => x.Btn == b);
                }
            }
        }

        private void Example_Click(object sender, RoutedEventArgs e)
        {
            var item = (MenuFlyoutItem)sender;
            IpaInputRight.Text = item.Tag as string ?? "";
            IpaInputRight.Focus(FocusState.Programmatic);
            ConvertBtn_Click(sender, e);
        }

        /* does the symbol start with U+25CC (dotted circle) or a
         * combining mark? those must follow a base segment */
        private static bool IsCombiningModifier(string sym)
        {
            if (sym.Length == 0) return false;
            int cp = char.ConvertToUtf32(sym, 0);
            return cp == 0x25CC || (cp >= 0x0300 && cp <= 0x036F) ||
                   cp == 0x1AB0 || (cp >= 0x1DC0 && cp <= 0x1DFF);
        }

        private void AddHistory(string title, string? body)
        {
            _history.Add((title, body ?? ""));
            while (_history.Count > MaxHistory)
                _history.RemoveAt(0);
        }

        private void ConvertBtn_Click(object sender, RoutedEventArgs e)
        {
            string ipa = IpaInputRight.Text;
            if (string.IsNullOrWhiteSpace(ipa))
            {
                AppendOutput("=== IPA -> vectors ===\n" +
                             "Nothing to convert - type or click an IPA symbol first.");
                return;
            }
            int fmt = _fmtIndex;
            string? result;
            switch (fmt)
            {
                case 1:
                    /* -q / --query: symbol lookup (single symbol) */
                    result = Core.Query(ipa);
                    AppendOutput($"=== Query: {ipa} ===\n" + result);
                    break;
                case 2:
                    /* -L / --layers (alias --ir): two-layer tier decomposition */
                    result = Core.Ir(ipa);
                    AppendOutput($"=== IPA -> layers ===\ninput: {ipa}\n" + result);
                    break;
                case 3:
                    result = Core.Json(ipa);
                    AppendOutput($"=== IPA -> JSON ===\ninput: {ipa}\n" + result);
                    break;
                default:
                    string? ferr = null;
                    result = _featureNames ? Core.ForwardNamed(ipa)
                                           : Core.Forward(ipa, out ferr);
                    if (result == null)
                    {
                        string hint = IsCombiningModifier(ipa)
                            ? "The string starts with a combining mark.\n" +
                              "Diacritics attach to the symbol before them -\n" +
                              "type the base first, e.g. 't\u0306' (t + short)."
                            : "Tip: put a space between syllables, e.g. 'ma ˥˩'.\n" +
                              "If a symbol shows a red warning in the console,\n" +
                              "enable its school module under View > Modules.";
                        AppendOutput("=== IPA -> vectors ===\n" +
                                     "Hmm, I could not parse: /" + ipa + "/\n" +
                                     (string.IsNullOrEmpty(ferr) ? "" : "core: " + ferr + "\n") +
                                     hint);
                        break;
                    }
                    AppendOutput(_featureNames
                        ? $"=== IPA -> vectors (feature names) ===\ninput: {ipa}\n" + result
                        : $"=== IPA -> vectors ===\ninput: {ipa}\n" + result);
                    break;
            }
            AddHistory("Convert: " + ipa, result);
            SetStatus("converted " + ipa.Length + " chars");
            IpaInputRight.Focus(FocusState.Programmatic);
        }

        /* Button marks pointer events handled, so the long-press gestures
         * must be wired with handledEventsToo. Note: PointerCanceled and
         * PointerCaptureLost are deliberately NOT wired to closing - the
         * popup covering the button can cancel the capture mid-hold (the
         * box under the cursor then takes over and the real release
         * closes it), and WinUI does not release mouse capture on button
         * up, so every press must end with an explicit release */
        private void WireWidthBtn()
        {
            try
            {
                WidthBtn.AddHandler(UIElement.PointerPressedEvent,
                    new PointerEventHandler(WidthBtn_PointerPressed), true);
                WidthBtn.AddHandler(UIElement.PointerMovedEvent,
                    new PointerEventHandler(WidthBtn_PointerMoved), true);
                WidthBtn.AddHandler(UIElement.PointerReleasedEvent,
                    new PointerEventHandler(WidthBtn_PointerReleased), true);
                FmtBtn.AddHandler(UIElement.PointerPressedEvent,
                    new PointerEventHandler(FmtBtn_PointerPressed), true);
                FmtBtn.AddHandler(UIElement.PointerMovedEvent,
                    new PointerEventHandler(FmtBtn_PointerMoved), true);
                FmtBtn.AddHandler(UIElement.PointerReleasedEvent,
                    new PointerEventHandler(FmtBtn_PointerReleased), true);
            }
            catch (Exception ex) { LogExt("wire width btn err " + ex.Message); }
        }

        /* ---- narrowness control: compact button; long-pressing it pops
         * up a virtual overlay box on a separate layer (the layout below
         * is never touched). The box is centred over the button, grows
         * out of it on open and shrinks back into it on release ----
         *
         * The thumb position is a continuous, non-linear function of the
         * cursor position: within each step the fractional position goes
         * through the S-curve g(t) = t^p / (t^p + (1-t)^p), so the thumb
         * is pulled strongly toward the ticks and rests at the midpoints.
         * No velocity is involved; the cursor itself is only moved along
         * Y, magnetically pulled onto the slider row when it gets near. */

        private const double WidthMagnetP = 3.0;   /* S-curve steepness */
        private const double WidthYBand = 34;      /* Y magnet radius (DIP) */
        private const double ElasticMax = 12.0;    /* overscroll cap (DIP) */
        private const double ElasticSoft = 30.0;   /* overscroll softness */

        /* elastic overscroll: 1 - 1/(1 + o/soft), asymptotic towards cap */
        private static double Elastic(double o) =>
            ElasticMax * (1.0 - 1.0 / (1.0 + o / ElasticSoft));

        private static readonly string[] LevelNamesEn =
            { "broadest", "broad", "medium", "narrow", "narrowest" };
        private static readonly string[] LevelNamesZh =
            { "最宽", "宽", "中", "窄", "最窄" };
        private static readonly string[] CompactNamesEn =
            { "b4-est", "broad", "medium", "narrow", "n5-est" };

        private DispatcherTimer? _widthHoldTimer;
        private bool _widthOpen;
        private UIElement? _widthPrevFocus;
        private Microsoft.UI.Xaml.Media.Animation.Storyboard? _widthAnim;

        private void WidthBtn_PointerPressed(object sender,
            PointerRoutedEventArgs e)
        {
            try { WidthBtn.CapturePointer(e.Pointer); }
            catch { }
            _widthHoldTimer?.Stop();
            _widthHoldTimer = new DispatcherTimer
            { Interval = TimeSpan.FromMilliseconds(400) };
            _widthHoldTimer.Tick += (s, a) =>
            {
                _widthHoldTimer?.Stop();
                OpenWidthPop();
            };
            _widthHoldTimer.Start();
        }

        private void WidthBtn_PointerMoved(object sender,
            PointerRoutedEventArgs e)
        {
            if (!_widthOpen) return;
            if (!e.GetCurrentPoint(WidthBtn).Properties.IsLeftButtonPressed)
                return;
            AdjustWidthFromPointer(e);
        }

        private void WidthPop_PointerPressed(object sender,
            PointerRoutedEventArgs e)
        {
            try { WidthPopBox.CapturePointer(e.Pointer); }
            catch { }
            AdjustWidthFromPointer(e);
        }

        private void WidthPop_PointerMoved(object sender,
            PointerRoutedEventArgs e)
        {
            if (!_widthOpen) return;
            if (!e.GetCurrentPoint(WidthPopBox).Properties.IsLeftButtonPressed)
                return;
            AdjustWidthFromPointer(e);
        }

        /* continuous non-linear thumb position from the cursor position,
         * plus a Y-axis magnet that pulls the cursor onto the slider row */
        private void AdjustWidthFromPointer(PointerRoutedEventArgs e)
        {
            if (WidthSlider.ActualWidth <= 0) return;
            var p = e.GetCurrentPoint(WidthSlider);
            double w = WidthSlider.ActualWidth;
            double f = Math.Clamp(p.Position.X / w, 0, 1);
            double v = f * 4.0;
            double disp;
            if (f <= 0) disp = 0;
            else if (f >= 1) disp = 4;
            else
            {
                int k = (int)Math.Floor(v);
                if (k > 3) k = 3;
                double t = v - k;
                double tn = Math.Pow(t, WidthMagnetP);
                double g = tn / (tn + Math.Pow(1 - t, WidthMagnetP));
                disp = k + g;
            }
            WidthSlider.Value = Math.Clamp(disp, 0, 4);

            /* elastic overscroll feedback: dragging beyond the track
             * shifts the whole box, compressed, and it returns smoothly */
            double x = p.Position.X;
            WidthPopShift.X = x > w ? Elastic(x - w)
                              : x < 0 ? -Elastic(-x) : 0.0;

            /* Y-axis magnet: near the slider row the cursor itself is
             * pulled onto it (X stays untouched) */
            double cy = p.Position.Y - WidthSlider.ActualHeight / 2;
            if (Math.Abs(cy) <= WidthYBand &&
                p.Position.X >= -WidthYBand &&
                p.Position.X <= w + WidthYBand)
                SnapCursorY(WidthSlider.ActualHeight / 2);
        }

        /* move the cursor's Y onto the slider row (screen coords; the
         * cursor's X is left untouched) */
        private void SnapCursorY(double yDip)
        {
            try
            {
                var root = Content.XamlRoot.Content as UIElement;
                if (root == null) return;
                var t = WidthSlider.TransformToVisual(root);
                var pt = t.TransformPoint(new Windows.Foundation.Point(0, 0));
                double scale = DpiScale();
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                GetCursorPos(out var cur);
                var ptClient = new POINT32
                {
                    X = 0,
                    Y = (int)((pt.Y + yDip) * scale),
                };
                ClientToScreen(hwnd, ref ptClient);
                SetCursorPos(cur.X, ptClient.Y);
            }
            catch (Exception ex) { LogExt("snap y err " + ex.Message); }
        }

        /* releasing anywhere commits the value and closes the box */
        private void WidthBtn_PointerReleased(object sender,
            PointerRoutedEventArgs e)
        {
            _widthHoldTimer?.Stop();
            try { WidthBtn.ReleasePointerCapture(e.Pointer); } catch { }
            CloseWidthPop();
        }

        private void WidthPop_PointerReleased(object sender,
            PointerRoutedEventArgs e)
        {
            try { WidthPopBox.ReleasePointerCapture(e.Pointer); } catch { }
            CloseWidthPop();
        }

        /* fallback: a release anywhere on the overlay layer closes it
         * (covers the case where pointer capture was lost) */
        private void WidthOverlay_PointerReleased(object sender,
            PointerRoutedEventArgs e)
        {
            CloseWidthPop();
        }

        private void OpenWidthPop()
        {
            if (_widthOpen) return;
            _widthOpen = true;
            _widthAnim?.Stop();
            _fmtAnim?.Stop();
            var root = Content.XamlRoot.Content as UIElement;
            if (root != null)
            {
                /* centre the box over the button it grows out of
                 * (coordinates relative to the overlay itself) */
                var t = WidthBtn.TransformToVisual(WidthOverlay);
                var pt = t.TransformPoint(new Windows.Foundation.Point(0, 0));
                double bx = pt.X + (WidthBtn.ActualWidth - WidthPopBox.Width) / 2;
                double by = pt.Y + (WidthBtn.ActualHeight - WidthPopBox.Height) / 2;
                WidthPopBox.Margin = new Thickness(bx, by, 0, 0);
            }
            WidthOverlay.Visibility = Visibility.Visible;
            WidthPopBox.Visibility = Visibility.Visible;
            WidthPopBox.Opacity = 0;
            FmtPopBox.Visibility = Visibility.Collapsed;
            _widthPrevFocus =
                FocusManager.GetFocusedElement(Content.XamlRoot) as UIElement;
            try { WidthPopBox.Focus(FocusState.Programmatic); } catch { }
            WidthPopScale.ScaleX = 0.3;
            WidthPopScale.ScaleY = 0.3;
            var openEase = new Microsoft.UI.Xaml.Media.Animation.CubicEase
            { EasingMode = Microsoft.UI.Xaml.Media.Animation.EasingMode.EaseOut };
            var bounce = new Microsoft.UI.Xaml.Media.Animation.BackEase
            { EasingMode = Microsoft.UI.Xaml.Media.Animation.EasingMode.EaseOut,
              Amplitude = 0.5 };
            var sb = new Microsoft.UI.Xaml.Media.Animation.Storyboard();
            sb.Children.Add(Anim(WidthPopBox, "Opacity", 0, 1, 180, openEase));
            sb.Children.Add(Anim(WidthPopScale, "ScaleX", 0.3, 1, 220, bounce));
            sb.Children.Add(Anim(WidthPopScale, "ScaleY", 0.3, 1, 220, bounce));
            _widthAnim = sb;
            sb.Begin();

            /* the initial thumb follows the cursor (still pressed over the
             * button), not the previously stored value; runs after the
             * box's first layout so the slider geometry is final */
            DispatcherQueue.TryEnqueue(() =>
            {
                try
                {
                    var root = Content.XamlRoot.Content as UIElement;
                    if (root == null || WidthSlider.ActualWidth <= 0) return;
                    var hwnd = WinRT.Interop.WindowNative
                        .GetWindowHandle(this);
                    GetCursorPos(out var cur);
                    ScreenToClient(hwnd, ref cur);
                    double scale = DpiScale();
                    var t = WidthSlider.TransformToVisual(root);
                    var pt = t.TransformPoint(
                        new Windows.Foundation.Point(0, 0));
                    double f = Math.Clamp(
                        (cur.X / scale - pt.X) / WidthSlider.ActualWidth,
                        0, 1);
                    WidthSlider.Value = Math.Clamp(f * 4.0, 0, 4);
                }
                catch (Exception ex) { LogExt("width init pos err " + ex.Message); }
            });
        }

        private void CloseWidthPop()
        {
            if (!_widthOpen) return;
            _widthOpen = false;
            WidthSlider.Value = Math.Round(WidthSlider.Value);
            _widthAnim?.Stop();
            var closeEase = new Microsoft.UI.Xaml.Media.Animation.CubicEase
            { EasingMode = Microsoft.UI.Xaml.Media.Animation.EasingMode.EaseIn };
            var sb = new Microsoft.UI.Xaml.Media.Animation.Storyboard();
            sb.Children.Add(Anim(WidthPopBox, "Opacity", 1, 0, 120, closeEase));
            sb.Children.Add(Anim(WidthPopScale, "ScaleX", 1, 0.3, 120, closeEase));
            sb.Children.Add(Anim(WidthPopScale, "ScaleY", 1, 0.3, 120, closeEase));
            sb.Completed += (s, a) =>
            {
                WidthOverlay.Visibility = Visibility.Collapsed;
                WidthPopBox.Opacity = 1;
                WidthPopScale.ScaleX = 1;
                WidthPopScale.ScaleY = 1;
            };
            _widthAnim = sb;
            sb.Begin();
            RestoreFocus(_widthPrevFocus, WidthBtn);
        }

        private static Microsoft.UI.Xaml.Media.Animation.DoubleAnimation
            Anim(DependencyObject target, string prop,
                 double from, double to, int ms,
                 Microsoft.UI.Xaml.Media.Animation.EasingFunctionBase ease)
        {
            var da = new Microsoft.UI.Xaml.Media.Animation.DoubleAnimation
            {
                From = from,
                To = to,
                Duration = new Duration(TimeSpan.FromMilliseconds(ms)),
                EasingFunction = ease,
            };
            Microsoft.UI.Xaml.Media.Animation.Storyboard.SetTarget(da, target);
            Microsoft.UI.Xaml.Media.Animation.Storyboard
                .SetTargetProperty(da, prop);
            return da;
        }

        /* the button's label, the popup level pill and the tooltip all
         * follow the value */
        private void WidthSlider_ValueChanged(object sender,
            Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
        {
            if (WidthBtnLabel == null) return;
            int v = (int)Math.Round(e.NewValue);
            v = Math.Clamp(v, 0, 4);
            WidthBtnLabel.Text = _zh ? LevelNamesZh[v] : CompactNamesEn[v];
            WidthPopVal.Text = (_zh ? LevelNamesZh : LevelNamesEn)[v];
            ToolTipService.SetToolTip(WidthBtn, _zh
                ? $"窄度 {v}（{(_zh ? LevelNamesZh : LevelNamesEn)[v]}）- 长按展开"
                : $"narrowness {v} ({(_zh ? LevelNamesZh : LevelNamesEn)[v]}) - hold to expand");
        }

        /* ---- format picker: long-pressing the format button pops up a
         * vertical slide-to-select list on the same overlay layer. The
         * selection is a continuous non-linear function of the cursor Y
         * (same S-curve as the narrowness picker); a highlight pill
         * slides over the rows and the selection commits on release.
         * Rendered from scratch (rows + pill), no Slider reused ---- */

        private static readonly string[] FmtNamesEn =
            { "vectors", "query", "layers", "JSON" };
        private static readonly string[] FmtNamesZh =
            { "向量", "查询", "层", "JSON" };

        private DispatcherTimer? _fmtHoldTimer;
        private bool _fmtOpen;
        private int _fmtIndex;
        private double _fmtDisp;
        private UIElement? _fmtPrevFocus;
        private Microsoft.UI.Xaml.Media.Animation.Storyboard? _fmtAnim;
        private TextBlock[] _fmtRows = Array.Empty<TextBlock>();
        private Border[] _fmtItems = Array.Empty<Border>();
        private TextBlock[] _fmtChecks = Array.Empty<TextBlock>();
        private int _fmtSelVis = -1;
        private Microsoft.UI.Xaml.Media.Brush? _fmtOnAccent;
        private Microsoft.UI.Xaml.Media.Brush? _fmtTextFill;
        private long _fmtMoveTick;
        private double _lastFmtRawY;
        private double _lastFmtForceDip;

        private void FmtBtn_PointerPressed(object sender,
            PointerRoutedEventArgs e)
        {
            try { FmtBtn.CapturePointer(e.Pointer); }
            catch { }
            _fmtHoldTimer?.Stop();
            _fmtHoldTimer = new DispatcherTimer
            { Interval = TimeSpan.FromMilliseconds(400) };
            _fmtHoldTimer.Tick += (s, a) =>
            {
                _fmtHoldTimer?.Stop();
                OpenFmtPop();
            };
            _fmtHoldTimer.Start();
        }

        private void FmtBtn_PointerMoved(object sender,
            PointerRoutedEventArgs e)
        {
            if (!_fmtOpen) return;
            if (!e.GetCurrentPoint(FmtBtn).Properties.IsLeftButtonPressed)
                return;
            AdjustFmtFromPointer(e);
        }

        private void FmtPop_PointerPressed(object sender,
            PointerRoutedEventArgs e)
        {
            try { FmtPopBox.CapturePointer(e.Pointer); }
            catch { }
            AdjustFmtFromPointer(e);
        }

        private void FmtPop_PointerMoved(object sender,
            PointerRoutedEventArgs e)
        {
            if (!_fmtOpen) return;
            if (!e.GetCurrentPoint(FmtPopBox).Properties.IsLeftButtonPressed)
                return;
            AdjustFmtFromPointer(e);
        }

        /* Selection follows the cursor directly - no filter, no chase
         * animation, so there is no lag:
         *  - the pill is CENTRED on the cursor (half a row subtracted);
         *  - the S-curve magnet (t^3/(t^3+(1-t)^3), a high-order curve)
         *    is the velocity profile itself: near a row centre the slope
         *    is ~0 (slow crawl into the snap), between rows it is steep
         *    (fast transit) - crisp 吸附 without sluggishness;
         *  - a cursor force field (attraction into the row centres,
         *    repulsion out of the very core) dents the real cursor so
         *    the rows feel tactile.
         * Hot path: no allocations, no resource lookups. */
        private const double FmtRowH = 43;
        private const double FmtTop = 1;

        private void AdjustFmtFromPointer(PointerRoutedEventArgs e)
        {
            if (FmtPopBox.ActualHeight <= 0) return;
            var p = e.GetCurrentPoint(FmtPopBox);
            double f = Math.Clamp(
                (p.Position.Y - FmtTop) / (FmtRowH * 4), 0, 1);
            double v = Math.Clamp(f * 4.0 - 0.5, 0, 3);
            int k = (int)Math.Floor(v);
            double t = v - k;
            double tn = t * t * t;
            double g = tn / (tn + (1 - t) * (1 - t) * (1 - t));
            double magV = k + g;                  /* magnetised, centred */
            _fmtDisp = magV;
            FmtPillTrans.Y = magV * FmtRowH;

            /* elastic overscroll feedback: dragging beyond the rows
             * shifts the whole box, compressed, and it returns smoothly */
            double yLocal = p.Position.Y - FmtTop;
            double limit = FmtRowH * 4;
            FmtPopShift.Y = yLocal > limit ? Elastic(yLocal - limit)
                          : yLocal < 0 ? -Elastic(-yLocal) : 0.0;

            /* pointer speed (raw: our own previous displacement is
             * subtracted, so the measurement cannot feed back) */
            long now = Environment.TickCount64;
            double dt = Math.Max((now - _fmtMoveTick) / 1000.0, 0.001);
            double rawY = p.Position.Y - _lastFmtForceDip;
            double speedDip = Math.Abs(rawY - _lastFmtRawY) / dt;
            _lastFmtRawY = rawY;
            _fmtMoveTick = now;
            double speedF = Math.Clamp((speedDip - 80.0) / 320.0, 0.0, 1.0);

            /* between rows the accent pill contracts, at the row centres
             * it is full size: the deformation follows the pill's
             * distance from the nearest row centre (0 at a centre,
             * 1 between rows), smoothed exponentially so the breathing
             * animates. The narrowness box is left untouched - its
             * width never changes. */
            double t2 = 2.0 * Math.Abs(_fmtDisp - Math.Round(_fmtDisp));
            double shrink = 0.15 * t2 * t2;
            double tgt = 1.0 - shrink;
            const double kS = 0.4;
            FmtPillBreath.ScaleX += (tgt - FmtPillBreath.ScaleX) * kS;
            FmtPillBreath.ScaleY += (tgt - FmtPillBreath.ScaleY) * kS;

            /* cursor force field (only inside the rows band): attract
             * into the row centres, repel out of the very core; the
             * cursor settles on a small ring around each centre.
             * Speed-gated: slow, deliberate moves pass through
             * unhindered - the field only dents fast flicks. */
            if (speedF > 0 && yLocal >= -10 && yLocal <= limit + 10)
            {
                double d = yLocal / FmtRowH - 0.5 - Math.Round(
                    yLocal / FmtRowH - 0.5);
                double ad = Math.Abs(d);
                const double zone = 0.20, core = 0.06;
                const double kA = 0.30, kR = 1.0;
                double dispDip;
                if (ad < core) dispDip = d * kR * FmtRowH;
                else if (ad < zone)
                    dispDip = -Math.Sign(d) * kA * ad * FmtRowH;
                else dispDip = 0;
                dispDip *= speedF;
                _lastFmtForceDip = dispDip;
                if (dispDip != 0) OffsetCursorY(dispDip);
            }
            else
            {
                _lastFmtForceDip = 0;
            }

            int sel = (int)Math.Round(magV);
            if (sel != _fmtSelVis) UpdateFmtSel(sel);
        }

        /* displace the real cursor along Y by deltaDip (screen coords) */
        private void OffsetCursorY(double deltaDip)
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                GetCursorPos(out var cur);
                double scale = DpiScale();
                int dy = (int)Math.Round(deltaDip * scale);
                if (dy == 0) return;
                SetCursorPos(cur.X, cur.Y + dy);
            }
            catch (Exception ex) { LogExt("cursor force err " + ex.Message); }
        }

        private void FmtBtn_PointerReleased(object sender,
            PointerRoutedEventArgs e)
        {
            _fmtHoldTimer?.Stop();
            try { FmtBtn.ReleasePointerCapture(e.Pointer); } catch { }
            CloseFmtPop();
        }

        private void FmtPop_PointerReleased(object sender,
            PointerRoutedEventArgs e)
        {
            try { FmtPopBox.ReleasePointerCapture(e.Pointer); } catch { }
            CloseFmtPop();
        }

        private void OpenFmtPop()
        {
            if (_fmtOpen) return;
            CloseWidthPop();          /* one popup at a time */
            _fmtOpen = true;
            _fmtAnim?.Stop();
            _widthAnim?.Stop();       /* its Completed would collapse the
                                         overlay mid-open */
            WidthOverlay.Visibility = Visibility.Visible;
            FmtPopBox.Visibility = Visibility.Visible;
            WidthPopBox.Visibility = Visibility.Collapsed;
            _fmtPrevFocus =
                FocusManager.GetFocusedElement(Content.XamlRoot) as UIElement;
            try { FmtPopBox.Focus(FocusState.Programmatic); } catch { }
            var root = Content.XamlRoot.Content as UIElement;
            if (root != null)
            {
                var t = FmtBtn.TransformToVisual(WidthOverlay);
                var pt = t.TransformPoint(new Windows.Foundation.Point(0, 0));
                double bx = Math.Max(0,
                    pt.X + (FmtBtn.ActualWidth - FmtPopBox.Width) / 2);
                double by = Math.Max(0,
                    pt.Y + (FmtBtn.ActualHeight - FmtPopBox.Height) / 2);
                FmtPopBox.Margin = new Thickness(bx, by, 0, 0);
            }
            _fmtSelVis = -1;
            FmtPillBreath.ScaleX = 1;
            FmtPillBreath.ScaleY = 1;
            FmtPillTrans.Y = _fmtIndex * FmtRowH;
            UpdateFmtSel(_fmtIndex);
            FmtPopBox.Opacity = 0;
            FmtPopScale.ScaleX = 0.3;
            FmtPopScale.ScaleY = 0.3;
            var openEase = new Microsoft.UI.Xaml.Media.Animation.CubicEase
            { EasingMode = Microsoft.UI.Xaml.Media.Animation.EasingMode.EaseOut };
            var bounce = new Microsoft.UI.Xaml.Media.Animation.BackEase
            { EasingMode = Microsoft.UI.Xaml.Media.Animation.EasingMode.EaseOut,
              Amplitude = 0.5 };
            var sb = new Microsoft.UI.Xaml.Media.Animation.Storyboard();
            sb.Children.Add(Anim(FmtPopBox, "Opacity", 0, 1, 180, openEase));
            sb.Children.Add(Anim(FmtPopScale, "ScaleX", 0.3, 1, 220, bounce));
            sb.Children.Add(Anim(FmtPopScale, "ScaleY", 0.3, 1, 220, bounce));
            _fmtAnim = sb;
            sb.Begin();

            /* the initial selection follows the cursor (still pressed
             * over the button), not the previously stored state; runs
             * after the box's first layout so its geometry is final */
            DispatcherQueue.TryEnqueue(() =>
            {
                try
                {
                    var root = Content.XamlRoot.Content as UIElement;
                    if (root == null) return;
                    var hwnd = WinRT.Interop.WindowNative
                        .GetWindowHandle(this);
                    GetCursorPos(out var cur);
                    ScreenToClient(hwnd, ref cur);
                    double scale = DpiScale();
                    var tf = FmtPopBox.TransformToVisual(root);
                    var pt = tf.TransformPoint(
                        new Windows.Foundation.Point(0, 0));
                    double f = Math.Clamp(
                        (cur.Y / scale - pt.Y - FmtTop) / (FmtRowH * 4),
                        0, 1);
                    double v = Math.Clamp(f * 4.0 - 0.5, 0, 3);
                    int k = (int)Math.Floor(v);
                    double ft = v - k;
                    double tn = ft * ft * ft;
                    double g = tn / (tn + (1 - ft) * (1 - ft) * (1 - ft));
                    double magV = k + g;
                    _fmtDisp = magV;
                    FmtPillTrans.Y = magV * FmtRowH;
                    _fmtMoveTick = Environment.TickCount64;
                    _lastFmtRawY = 0;
                    _lastFmtForceDip = 0;
                    int sel = (int)Math.Round(magV);
                    _fmtSelVis = -1;
                    UpdateFmtSel(sel);
                }
                catch (Exception ex) { LogExt("fmt init pos err " + ex.Message); }
            });
        }

        private void CloseFmtPop()
        {
            if (!_fmtOpen) return;
            _fmtOpen = false;
            _fmtIndex = Math.Clamp((int)Math.Round(_fmtDisp), 0, 3);
            FmtBtnLabel.Text = (_zh ? FmtNamesZh : FmtNamesEn)[_fmtIndex];
            ToolTipService.SetToolTip(FmtBtn, (_zh ? FmtNamesZh : FmtNamesEn)
                [_fmtIndex] + (_zh ? " - 长按选择格式" : " - hold to pick format"));
            _fmtAnim?.Stop();
            var closeEase = new Microsoft.UI.Xaml.Media.Animation.CubicEase
            { EasingMode = Microsoft.UI.Xaml.Media.Animation.EasingMode.EaseIn };
            var sb = new Microsoft.UI.Xaml.Media.Animation.Storyboard();
            sb.Children.Add(Anim(FmtPopBox, "Opacity", 1, 0, 120, closeEase));
            sb.Children.Add(Anim(FmtPopScale, "ScaleX", 1, 0.3, 120, closeEase));
            sb.Children.Add(Anim(FmtPopScale, "ScaleY", 1, 0.3, 120, closeEase));
            sb.Completed += (s, a) =>
            {
                WidthOverlay.Visibility = Visibility.Collapsed;
                FmtPopBox.Visibility = Visibility.Collapsed;
                FmtPopBox.Opacity = 1;
                FmtPopScale.ScaleX = 1;
                FmtPopScale.ScaleY = 1;
            };
            _fmtAnim = sb;
            sb.Begin();
            RestoreFocus(_fmtPrevFocus, FmtBtn);
        }

        /* give keyboard focus back to the element focused before the popup
         * opened; deferred so the button's own Click (raised after our
         * PointerReleased handler) does not steal it first */
        private void RestoreFocus(UIElement? prev, UIElement fallback)
        {
            DispatcherQueue.TryEnqueue(() =>
            {
                if (prev != null && prev.Focus(FocusState.Programmatic)) return;
                try { fallback.Focus(FocusState.Programmatic); } catch { }
            });
        }

        /* selection visuals: row text/check colors swap when the pill
         * reaches a new row (the pill itself tracks the cursor directly).
         * Brushes are cached - never resolved in the hot path */
        private void UpdateFmtSel(int sel)
        {
            var onAccent = _fmtOnAccent ??=
                Res("TextOnAccentFillColorPrimaryBrush");
            var textFill = _fmtTextFill ??=
                Res("TextFillColorPrimaryBrush");
            for (int i = 0; i < _fmtRows.Length; i++)
            {
                _fmtRows[i].Foreground = i == sel ? onAccent : textFill;
                _fmtChecks[i].Foreground = i == sel ? onAccent : textFill;
                _fmtChecks[i].Visibility =
                    i == sel ? Visibility.Visible : Visibility.Collapsed;
            }
            _fmtSelVis = sel;
        }

        private void UpdateFmtRows()
        {
            var names = _zh ? FmtNamesZh : FmtNamesEn;
            for (int i = 0; i < _fmtRows.Length; i++)
                _fmtRows[i].Text = names[i];
            UpdateFmtSel(_fmtIndex);
        }

        private static Microsoft.UI.Xaml.Media.Brush Res(string key) =>
            Microsoft.UI.Xaml.Application.Current.Resources[key]
                as Microsoft.UI.Xaml.Media.Brush
                ?? new Microsoft.UI.Xaml.Media.SolidColorBrush(
                    Microsoft.UI.Colors.Gray);

        private void ReverseBtn_Click(object sender, RoutedEventArgs e)
        {
            int width = (int)WidthSlider.Value;
            if (width < 0) width = 3;
            var lines = VecInput.Text.Split('\n',
                StringSplitOptions.RemoveEmptyEntries);
            var sb = new System.Text.StringBuilder();
            foreach (var line in lines)
            {
                var r = Core.Reverse(line.Trim(), width);
                sb.AppendLine($"vec: {line.Trim()}");
                if (r != null) sb.AppendLine(r);
            }
            string result = sb.ToString().TrimEnd();
            AppendOutput($"=== Vector -> IPA (width {width}) ===\n" + result);
            AddHistory("Reverse (width " + width + ")", result);
            SetStatus("reverse fit done (" + lines.Length + " vector(s))");
            VecInput.Focus(FocusState.Programmatic);
        }


        private void AppendOutput(string text)
        {
            var doc = OutputBox.Document;
            /* normalise line endings first so \r\n does not become a
             * blank line (RichEditBox paragraphs are \r-separated) */
            string norm = text.Replace("\r\n", "\n")
                              .Replace('\r', '\n')
                              .Replace("\n", "\r");
            /* always end the appended block with a paragraph break: the
             * document's trailing implicit paragraph makes the char check
             * below see '\r' even when the visible text has no newline,
             * so without this the next section would be glued to ours */
            if (!norm.EndsWith("\r")) norm += "\r";
            var endRange = doc.GetRange(0, int.MaxValue);
            int end = endRange.EndPosition;
            /* append at the very end; O(1) instead of re-setting the
             * whole document (GetText+SetText was O(n^2) over history) */
            if (end > 0)
            {
                endRange.StartPosition = end - 1;
                if (endRange.Character != '\r' && endRange.Character != '\n')
                    norm = "\r" + norm;
            }
            var sel = doc.Selection;
            sel.StartPosition = sel.EndPosition = end;
            sel.Text = norm;
            sel.StartPosition = sel.EndPosition = int.MaxValue;
            ScrollToEnd();
        }

        /* ---- RichEditBox helpers (OutputBox) ---- */

        private string OutputText()
        {
            OutputBox.Document.GetText(
                Microsoft.UI.Text.TextGetOptions.None, out string t);
            return (t ?? "").Replace("\r", "\n");
        }

        private void OutputSet(string text)
        {
            /* RichEditBox paragraphs are \r-separated; normalise all
             * line endings first so \r\n does not become a blank line */
            string norm = text.Replace("\r\n", "\n")
                              .Replace('\r', '\n')
                              .Replace("\n", "\r");
            OutputBox.Document.SetText(
                Microsoft.UI.Text.TextSetOptions.None, norm);
        }

        private void ScrollToSection(FrameworkElement header)
        {
            try
            {
                var scroll = KeyboardScroll;
                var transform = header.TransformToVisual(
                    (UIElement)scroll.Content);
                var pt = transform.TransformPoint(
                    new Windows.Foundation.Point(0, 0));
                scroll.ChangeView(null, Math.Max(0, pt.Y - 6), null);
            }
            catch (Exception ex) { LogExt("scroll to section err " + ex.Message); }
        }

        /* keep the caret visible when the input overflows horizontally */
        private void ScrollRightInput()
        {
            try
            {
                DispatcherQueue.TryEnqueue(() =>
                {
                    var sv = FindDescendant<ScrollViewer>(IpaInputRight);
                    if (sv != null && sv.ScrollableWidth > 0)
                        sv.ChangeView(sv.ScrollableWidth, null, null);
                });
            }
            catch (Exception ex) { LogExt("scroll input err " + ex.Message); }
        }

        /* scroll the readonly output to its end (find the inner ScrollViewer) */
        private void ScrollToEnd()
        {
            try
            {
                DispatcherQueue.TryEnqueue(() =>
                {
                    var sv = FindDescendant<ScrollViewer>(OutputBox);
                    if (sv != null)
                        sv.ChangeView(null, sv.ScrollableHeight, null);
                });
            }
            catch (Exception ex) { LogExt("scroll end err " + ex.Message); }
        }

        private static T? FindDescendant<T>(DependencyObject root)
            where T : DependencyObject
        {
            int n = Microsoft.UI.Xaml.Media.VisualTreeHelper.GetChildrenCount(root);
            for (int i = 0; i < n; i++)
            {
                var child = Microsoft.UI.Xaml.Media.VisualTreeHelper.GetChild(root, i);
                if (child is T t) return t;
                var found = FindDescendant<T>(child);
                if (found != null) return found;
            }
            return null;
        }

        /* ---- menu ---- */

        private void Exit_Click(object sender, RoutedEventArgs e)
        {
            Close();
        }

        private async void About_Click(object sender, RoutedEventArgs e)
        {
            var ver = System.Reflection.Assembly.GetExecutingAssembly()
                .GetName().Version?.ToString(3) ?? "?";
            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "About vec4ipa Workbench",
                Content = "Version " + ver + "\n"
                          + "Core: ipa2vec_core.dll " + Core.Version + "\n\n"
                          + "WinUI 3 workbench for the vec4ipa tool suite:\n"
                          + "IPA <-> 16-D articulatory vectors.\n"
                          + "https://github.com/csiroqa/vec4ipa",
                CloseButtonText = "OK",
            };
            await dlg.ShowAsync();
        }

        private async void Docs_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "Documentation",
                Content = new ScrollViewer
                {
                    MaxHeight = 480,
                    Content = new TextBlock
                    {
                        Text = Core.Docs,
                        TextWrapping = TextWrapping.Wrap,
                        FontFamily = new Microsoft.UI.Xaml.Media.FontFamily("Consolas"),
                        FontSize = 12,
                    },
                },
                CloseButtonText = "Close",
            };
            await dlg.ShowAsync();
        }

        private async void ExportCmd_Click(object sender, RoutedEventArgs e)
        {
            string dir = AppContext.BaseDirectory;
            string text =
                "# vec4ipa CLI commands\n" +
                $"# app directory: {dir}\n\n" +
                ":: ipa2vec - IPA -> 16-D vectors\n" +
                $"\"{Path.Combine(dir, "tools", "ipa2vec.exe")}\" --narrowness 3 -L \"\\\"\\u02c8t\\u02b0a\\\"\"\n\n" +
                ":: vec2ipa - 16-D vector -> IPA (SPEC-NEXT order:\n" +
                "::   place, body, lips_closed, lips_rounded, tip_shape,\n" +
                "::   tongue_root, vel_open, lateral_ratio, voiced,\n" +
                "::   glottal_aperture, glottal_tension, larynx_height,\n" +
                "::   duration, jet_focus, effective_oral_area, airflow)\n" +
                $"\"{Path.Combine(dir, "tools", "vec2ipa.exe")}\" --narrowness 3 " +
                "\"-0.45,0,0,0,1,0,0,0,0,0.4,0,0,0,0,0,1\"\n\n" +
                ":: vec4ipa - inventory / query / reverse\n" +
                $"\"{Path.Combine(dir, "tools", "vec4ipa.exe")}\" -q \\u02b0\n" +
                $"\"{Path.Combine(dir, "tools", "vec4ipa.exe")}\" --narrowness 3 -r " +
                "\"-0.45,0,0,0,1,0,0,0,0,0.4,0,0,0,0,0,1\"\n";
            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "Export command lines",
                Content = new StackPanel { Spacing = 8 },
                PrimaryButtonText = "Copy",
                CloseButtonText = "Close",
            };
            var box = new TextBox
            {
                Text = text,
                IsReadOnly = true,
                AcceptsReturn = true,
                TextWrapping = TextWrapping.NoWrap,
                FontFamily = new Microsoft.UI.Xaml.Media.FontFamily("Consolas"),
                FontSize = 12,
                Height = 260,
            };
            ScrollViewer.SetVerticalScrollBarVisibility(box,
                Microsoft.UI.Xaml.Controls.ScrollBarVisibility.Auto);
            ((StackPanel)dlg.Content).Children.Add(box);
            dlg.PrimaryButtonClick += (s, e2) => CopyToClipboard(box.Text);
            await dlg.ShowAsync();
        }

        /* copy the bundled CLI tools into a directory (shared by
         * --export-tools and the File menu) */
        private static (int Ok, int Missing) ExportToolsTo(string destDir)
        {
            int ok = 0, missing = 0;
            string src = Path.Combine(AppContext.BaseDirectory, "tools");
            foreach (var name in new[] { "ipa2vec.exe", "vec2ipa.exe", "vec4ipa.exe" })
            {
                string from = Path.Combine(src, name);
                if (!File.Exists(from)) { missing++; continue; }
                try
                {
                    File.Copy(from, Path.Combine(destDir, name), true);
                    ok++;
                }
                catch (Exception ex) { LogExt("export tool err " + ex.Message); }
            }
            return (ok, missing);
        }

        private async void ExportTools_Click(object sender, RoutedEventArgs e)
        {
            var folder = await PickFolderAsync();
            if (folder == null) return;
            var (ok, missing) = ExportToolsTo(folder.Path);
            var msg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "Export tools",
                Content = $"Exported {ok} of 3 tools to:\n{folder.Path}\n" +
                          (missing > 0
                              ? $"{missing} tool(s) not bundled in this build."
                              : "All three CLI tools are ready to use."),
                CloseButtonText = "OK",
            };
            await msg.ShowAsync();
        }
    }

/* exposes UIElement.ProtectedCursor (protected) so the splitter can
   show the west-east resize cursor (WinAppSDK 1.6 has no ContentIsland) */
public sealed class CursorGrid : Microsoft.UI.Xaml.Controls.Grid
{
    public void SetPointerCursor(Microsoft.UI.Input.InputCursor? cursor)
        => ProtectedCursor = cursor;
}

}
