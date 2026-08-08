using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Windowing;
using Microsoft.UI;
using Microsoft.UI.Input;
using Windows.UI.Core;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

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

        public MainWindow() : this(Array.Empty<string>()) { }

        public MainWindow(string[] args)
        {
            _startupArgs = args;
            InitializeComponent();
            Title = "vec4ipa Workbench";
            SetIcon();
            RestoreState();
            BuildKeyboard();
            IpaInputRight.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    ConvertBtn_Click(s, e);
                    e.Handled = true;
                }
            };
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
            VecInput.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    ReverseBtn_Click(s, e);
                    e.Handled = true;
                }
            };
            DistA.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    DistBtn_Click(s, e);
                    e.Handled = true;
                }
            };
            DistB.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    DistBtn_Click(s, e);
                    e.Handled = true;
                }
            };
            SetStatus("Ready - click keyboard buttons or type IPA");
            Closed += (s, e) => SaveState();
            InitStatus();
            ShowWelcome();
            UpdateButtons();
            /* force the selection-highlight layer to rebuild on every
             * change (the compositor otherwise keeps the old paint) */
            OutputBox.SelectionChanged += (s, e) =>
            {
                try
                {
                    DispatcherQueue.TryEnqueue(() =>
                    {
                        var c = OutputBox.SelectionHighlightColor;
                        OutputBox.SelectionHighlightColor =
                            new Microsoft.UI.Xaml.Media.SolidColorBrush(
                                Microsoft.UI.Colors.Transparent);
                        OutputBox.SelectionHighlightColor = c;
                    });
                }
                catch { }
            };
            if (!InitCore())
                return;
            /* --help / --export-tools dialogs need XamlRoot; run them
             * once the window is activated */
            Activated += (s, e) =>
            {
                if (_argsPending)
                {
                    _argsPending = false;
                    HandleArgs(_startupArgs);
                }
            };
        }

        /* returns false when ipa2vec_core.dll is missing (UI stays up
         * with a clear status message instead of crashing) */
        private bool InitCore()
        {
            try
            {
                _ = Core.Version;
                BuildKeyboard();
                _argsPending = true;
                return true;
            }
            catch (System.DllNotFoundException)
            {
                StatusText.Text = "ipa2vec_core.dll not found next to the app - " +
                                  "features are disabled";
                return false;
            }
            catch (System.EntryPointNotFoundException)
            {
                StatusText.Text = "ipa2vec_core.dll is outdated or damaged - " +
                                  "features are disabled";
                return false;
            }
        }

        private void InitStatus()
        {
            string core = "core dll missing";
            try { core = "core " + Core.Version; } catch { }
            StatusText.Text = $"{core} - width {WidthCombo.SelectedIndex}";
            if (core == "core dll missing")
                StatusText.Text = "ipa2vec_core.dll not found next to the app - " +
                                  "features will not work";
        }

        private void UpdateButtons()
        {
            ConvertBtn.IsEnabled = IpaInputRight.Text.Length > 0;
            ReverseBtn.IsEnabled = VecInput.Text.Trim().Length > 0;
            DistBtn.IsEnabled = DistA.Text.Length > 0 && DistB.Text.Length > 0;
        }

        private void ShowWelcome()
        {
            string welcome =
                "Welcome to vec4ipa Workbench\n" +
                "---------------------------------\n\n" +
                "1. Type or click an IPA string below (or pick an example\n" +
                "   from File > Examples).\n" +
                "2. Press Convert - each segment becomes a 16-D vector.\n" +
                "3. Paste a vector and press Reverse to fit IPA back,\n" +
                "   choosing the transcription width (0-4).\n\n" +
                "Tip: hover a keyboard key for its name, double-click for\n" +
                "details; symbols you use are collected on the Recent tab.\n\n" +
                "Example to try:  t\u02b0a  (aspirated stop + open vowel)";
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
                int x = 0, y = 0, w = 1180, h = 760;
                if (_appWindow != null)
                {
                    var pos = _appWindow.Position;
                    var size = _appWindow.Size;
                    x = pos.X; y = pos.Y;
                    w = size.Width; h = size.Height;
                }
                File.WriteAllText(_statePath,
                    $"x={x}\ny={y}\nw={w}\nh={h}\nsplit={LeftCol.Width.Value}\n");
            }
            catch { }
        }

        private void RestoreState()
        {
            try
            {
                if (!File.Exists(_statePath)) { Resize(); return; }
                int x = 0, y = 0, w = 1180, h = 760;
                double split = 560;
                foreach (var line in File.ReadAllLines(_statePath))
                {
                    var p = line.Split('=');
                    if (p.Length != 2) continue;
                    if (p[0] == "x" && int.TryParse(p[1], out var v)) x = v;
                    else if (p[0] == "y" && int.TryParse(p[1], out v)) y = v;
                    else if (p[0] == "w" && int.TryParse(p[1], out v)) w = v;
                    else if (p[0] == "h" && int.TryParse(p[1], out v)) h = v;
                    else if (p[0] == "split" && double.TryParse(p[1], out var d))
                        split = d;
                }
                if (split < 360) split = 360;
                if (split > 1400) split = 1400;
                LeftCol.Width = new GridLength(split);
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                var windowId = Win32Interop.GetWindowIdFromWindow(hwnd);
                _appWindow = AppWindow.GetFromWindowId(windowId);
                try
                {
                    _appWindow.MoveAndResize(new Windows.Graphics.RectInt32
                    {
                        X = x, Y = y,
                        Width = w > 0 ? w : 1180,
                        Height = h > 0 ? h : 760,
                    });
                }
                catch
                {
                    _appWindow.Resize(new Windows.Graphics.SizeInt32(1180, 760));
                }
            }
            catch { Resize(); }
        }

        private void Resize()
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                var windowId = Win32Interop.GetWindowIdFromWindow(hwnd);
                _appWindow = AppWindow.GetFromWindowId(windowId);
                _appWindow.Resize(new Windows.Graphics.SizeInt32(1180, 760));
            }
            catch { }
        }

        private void SetIcon()
        {
            try
            {
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                var windowId = Win32Interop.GetWindowIdFromWindow(hwnd);
                var appWindow = AppWindow.GetFromWindowId(windowId);
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
            catch { }
        }

        /* custom title bar: content extends into the caption area; the
         * title row is the drag region (window buttons stay on the right) */
        private void SetupTitleBar(AppWindow appWindow)
        {
            try
            {
                appWindow.TitleBar.ExtendsContentIntoTitleBar = true;
                var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                double scale = GetDpiForWindow(hwnd) / 96.0;
                int dragW = (int)(600 * scale);
                int dragH = (int)(32 * scale);
                appWindow.TitleBar.SetDragRectangles(new[]
                {
                    new Windows.Graphics.RectInt32(0, 0, dragW, dragH),
                });
                ApplyTitleBarTheme(appWindow);
            }
            catch { }
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
            catch { }
        }

        /* ---- command-line arguments (CLI-compatible) ---- */
        private async void HandleArgs(string[] args)
        {
            string? input = null, query = null, vec = null, exportDir = null;
            string? theme = null;
            bool reverse = false, showHelp = false;
            var rest = new List<string>();
            for (int i = 1; i < args.Length; i++)
            {
                string a = args[i];
                if (a == "--help" || a == "-h") showHelp = true;
                else if (a == "--width" && i + 1 < args.Length)
                {
                    string w = args[++i];
                    if (w.Length == 1 && w[0] >= '0' && w[0] <= '4')
                        WidthCombo.SelectedIndex = w[0] - '0';
                }
                else if (a == "--theme" && i + 1 < args.Length)
                    theme = args[++i];
                else if (a == "-q" || a == "--query")
                {
                    if (i + 1 < args.Length) query = args[++i];
                }
                else if (a == "-r" || a == "--reverse")
                {
                    if (i + 1 < args.Length) { vec = args[++i]; reverse = true; }
                }
                else if (a == "--export-tools" && i + 1 < args.Length)
                    exportDir = args[++i];
                else if (a.StartsWith("-") && a != "--")
                    rest.Add(a);
                else if (input == null) input = a;
            }
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
                        "  --width 0-4         reverse-fit narrowness (default 3)\n" +
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
                int ok = 0, missing = 0;
                string src = Path.Combine(AppContext.BaseDirectory, "tools");
                foreach (var name in new[] { "ipa2vec.exe", "vec2ipa.exe", "vec4ipa.exe" })
                {
                    string from = Path.Combine(src, name);
                    if (!File.Exists(from)) { missing++; continue; }
                    try
                    {
                        File.Copy(from, Path.Combine(exportDir, name), true);
                        ok++;
                    }
                    catch { }
                }
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

        /* ---- Settings dialog: theme / language / feature names / modules ---- */

        private readonly Dictionary<string, bool> _moduleOn = new();
        private string _themeName = "System";
        private string[] _startupArgs = Array.Empty<string>();
        private bool _argsPending;
        private TextBox? _focusedBox; // soft-keyboard target (last focused box)
        private TextBox? _kbPressedBox; // box focused when a key was pressed
        private bool _slideMode;         // glide-typing across keys
        private bool _slid;              // glide typed (skip the final Click)

        private async void Settings_Click(object sender, RoutedEventArgs e)
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
                Header = _zh ? "向量输出显示特征名（tt_pos=0.55）"
                             : "Vector output shows feature names (tt_pos=0.55)",
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
                Text = _zh ? "度量：编译内置默认值（metric.json v4）"
                           : "Metric: compiled-in defaults (metric.json v4)",
                FontSize = 13,
                Margin = new Thickness(0, 4, 0, 0),
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
                    new Button
                    {
                        Content = _zh ? "加载 metric.json..." : "Load metric.json...",
                        HorizontalAlignment = HorizontalAlignment.Left,
                    },
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
            ((Button)((StackPanel)content.Content).Children[5]).Click +=
                async (s2, e2) =>
                {
                    var picker = new Windows.Storage.Pickers.FileOpenPicker();
                    var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
                    WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
                    picker.FileTypeFilter.Add(".json");
                    var file = await picker.PickSingleFileAsync();
                    if (file == null) return;
                    string? err = Core.LoadMetric(file.Path);
                    metricText.Text = err == null
                        ? "Metric: " + file.Name + " (loaded)"
                        : "Metric load failed: " + file.Name;
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

        private void ApplyLang(bool zh)
        {
            _zh = zh;
            var lbls = new[]
            {
                (LblIpa, zh ? "操作：" : "Actions:"),
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
            LblCons.Text = zh ? "辅音" : "Consonants";
            LblNp.Text = zh ? "非肺部气流" : "Non-pulmonic";
            LblVow.Text = zh ? "元音" : "Vowels";
            LblDiac.Text = zh ? "附加符号" : "Diacritics";
            LblLet.Text = zh ? "修饰字母" : "Letters";
            LblTone.Text = zh ? "声调" : "Tones";
            LblRec.Text = zh ? "最近使用" : "Recent";
            DistA.PlaceholderText = zh ? "符号 A" : "symbol A";
            DistB.PlaceholderText = zh ? "符号 B" : "symbol B";
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

        private async void LoadMetric_Click(object sender, RoutedEventArgs e)
        {
            var picker = new Windows.Storage.Pickers.FileOpenPicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.FileTypeFilter.Add(".json");
            var file = await picker.PickSingleFileAsync();
            if (file == null) return;
            string? err = Core.LoadMetric(file.Path);
            if (err != null)
            {
                SetStatus(err);
                AppendOutput("=== Load metric ===\n" + err);
            }
            else
            {
                SetStatus("metric loaded: " + file.Name);
                AppendOutput($"=== Metric loaded: {file.Name} ===\n" +
                             Core.WeightsEffective());
            }
        }

        private async void SaveIr_Click(object sender, RoutedEventArgs e)
        {
            if (IpaInputRight.Text.Length == 0)
            {
                SetStatus("nothing to export - type an IPA string first");
                return;
            }
            var picker = new Windows.Storage.Pickers.FileSavePicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.SuggestedFileName = "ipa-ir";
            picker.FileTypeChoices.Add("IR base", new List<string> { ".layer1" });
            var file = await picker.PickSaveFileAsync();
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
                    sb.AppendLine($"  {names[i],-22} {va[0][i],8:F4}  {vb[0][i],8:F4}  diff {vb[0][i] - va[0][i],+8:F4}");
                sb.AppendLine("  weighted distance: " + Core.Distance(a, b));
            }
            AppendOutput($"=== Compare {a} ~ {b} ===\n" +
                         sb.ToString().TrimEnd());
            SetStatus("comparison shown");
        }

        private async void SaveOutput_Click(object sender, RoutedEventArgs e)
        {
            var picker = new Windows.Storage.Pickers.FileSavePicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.SuggestedFileName = "ipa2vec-output.txt";
            picker.FileTypeChoices.Add("Text file", new List<string> { ".txt" });
            var file = await picker.PickSaveFileAsync();
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
            try
            {
                var dp = new Windows.ApplicationModel.DataTransfer.DataPackage();
                dp.SetText(OutputText());
                Windows.ApplicationModel.DataTransfer.Clipboard.SetContent(dp);
                SetStatus("output copied to clipboard");
            }
            catch { SetStatus("copy failed"); }
        }

        private async void OpenFileConvert_Click(object sender, RoutedEventArgs e)
        {
            var picker = new Windows.Storage.Pickers.FileOpenPicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.FileTypeFilter.Add(".txt");
            var file = await picker.PickSingleFileAsync();
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

        private void VectorEditor_Click(object sender, RoutedEventArgs e)
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
                FontFamily = new Microsoft.UI.Xaml.Media.FontFamily("Gentium Book Plus"),
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
            foreach (var box in boxes)
                box.ValueChanged += (s, e2) => UpdatePreview();

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
            dlg.ShowAsync();
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
                /* The screen compositor does not repaint theme resources
                 * after a runtime theme change on this system (background
                 * stays dark while text goes dark -> looks all black).
                 * Setting the backgrounds explicitly bypasses that. */
                SetExplicitBackground(root, theme);
                root.InvalidateMeasure();
                root.InvalidateArrange();
                root.UpdateLayout();
                if (_appWindow != null)
                    ApplyTitleBarTheme(_appWindow);
                SetStatus("theme: " + name.ToLowerInvariant());
            }
            catch { }
        }

        private void SetExplicitBackground(FrameworkElement root,
                                           ElementTheme theme)
        {
            var bg = new Microsoft.UI.Xaml.Media.SolidColorBrush(
                theme == ElementTheme.Light
                    ? Windows.UI.Color.FromArgb(255, 243, 243, 243)
                    : theme == ElementTheme.Dark
                        ? Windows.UI.Color.FromArgb(255, 32, 32, 32)
                        : Windows.UI.Color.FromArgb(255, 0, 0, 0));
            if (theme == ElementTheme.Default)
            {
                /* restore theme-driven background */
                if (root is Microsoft.UI.Xaml.Controls.Grid g) g.Background = null;
                if (StatusText.Parent is Microsoft.UI.Xaml.Controls.Grid sg)
                    sg.Background = null;
                return;
            }
            /* apply to every container we own */
            if (root is Microsoft.UI.Xaml.Controls.Grid rg)
                rg.Background = bg;
            if (StatusText.Parent is Microsoft.UI.Xaml.Controls.Grid sg2)
                sg2.Background = bg;
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
            var rows = Core.ForwardRaw(ipa);
            if (rows == null || rows.Length == 0)
            {
                AppendOutput("=== Loop ===\nparse error");
                return;
            }
            int width = WidthCombo.SelectedIndex;
            if (width < 0) width = 3;
            var sb = new System.Text.StringBuilder();
            for (int s = 0; s < rows.Length; s++)
            {
                var vec = string.Join(",", Array.ConvertAll(rows[s],
                    x => x.ToString("F4")));
                sb.AppendLine($"[{s}] vector: ({vec})");
                sb.AppendLine($"    fit:   {Core.Reverse(vec, width)}");
            }
            AppendOutput("=== IPA -> vector -> IPA (loop) ===\n" +
                         sb.ToString().TrimEnd());
            SetStatus("loop done");
        }

        private async void ExportCsv_Click(object sender, RoutedEventArgs e)
        {
            var picker = new Windows.Storage.Pickers.FileSavePicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.SuggestedFileName = "ipa2vec-table.csv";
            picker.FileTypeChoices.Add("CSV", new List<string> { ".csv" });
            var file = await picker.PickSaveFileAsync();
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

        private void Splitter_Pressed(object sender, PointerRoutedEventArgs e)
        {
            _drag = true;
            _dragStartX = e.GetCurrentPoint(null).Position.X;
            _dragStartWidth = LeftCol.ActualWidth;
            Splitter.CapturePointer(e.Pointer);
        }

        private void Splitter_Moved(object sender, PointerRoutedEventArgs e)
        {
            if (!_drag) return;
            double dx = e.GetCurrentPoint(null).Position.X - _dragStartX;
            double w = _dragStartWidth + dx;
            if (w < 360) w = 360;
            if (w > 1400) w = 1400;
            LeftCol.Width = new GridLength(w);
        }

        private void Splitter_Released(object sender, PointerRoutedEventArgs e)
        {
            if (!_drag) return;
            _drag = false;
            Splitter.ReleasePointerCapture(e.Pointer);
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
            catch { }
            /* dedupe and cap */
            var seen = new HashSet<string>();
            _favorites.RemoveAll(s => !seen.Add(s));
            if (_favorites.Count > 200)
                _favorites.RemoveRange(200, _favorites.Count - 200);

            var consPos = Core.ConsPositions();
            double Pos(string s) =>
                consPos.TryGetValue(s, out var d) ? d : 0.5;

            _allCons.Clear();
            _allCons.AddRange(Core.KeyboardCons()
                .OrderBy(s => MannerWeight(Info(s)))
                .ThenBy(Pos));
            _allCons.AddRange(TieComposites);
            _allNp.Clear();
            _allNp.AddRange(Core.KeyboardConsNp()
                .OrderBy(s => AirstreamWeight(Info(s)))
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

            foreach (var s in _allCons.Where(Matches))
                ConsKeys.Items.Add(MakeKey(s));
            if (ConsKeys.Items.Count == 0) ConsKeys.Items.Add(new TextBlock
            {
                Text = "(no matches)", Foreground =
                    new Microsoft.UI.Xaml.Media.SolidColorBrush(
                        Microsoft.UI.Colors.Gray), Margin = new Thickness(4, 2, 0, 2),
            });
            foreach (var s in _allNp.Where(Matches))
                NpKeys.Items.Add(MakeKey(s));
            foreach (var s in _allVow.Where(Matches))
                VowKeys.Items.Add(MakeKey(s));
            foreach (var s in _allDiac.Where(Matches))
                DiacKeys.Items.Add(MakeKey(s, fontSize: 20));
            foreach (var s in _allLet.Where(Matches))
                LetterKeys.Items.Add(MakeKey(s, fontSize: 16));
            foreach (var s in _allTone.Where(Matches))
                ToneKeys.Items.Add(MakeKey(s));

            LblFav.Visibility = _favorites.Count > 0
                ? Visibility.Visible : Visibility.Collapsed;
            if (_favorites.Count > 0)
                foreach (var s in _favorites.Where(Matches))
                    FavKeys.Items.Add(MakeKey(s));
        }

        private void FilterBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            RebuildKeyboard(FilterBox.Text.Trim());
        }

        private void LblFav_Tapped(object sender, TappedRoutedEventArgs e)
        {
            ScrollToSection(LblFav);
        }

        /* right-click (or double-click fallback) symbol details */
        private void ShowSymbolDetail(string sym)
        {
            bool fav = _favorites.Contains(sym);
            var dlg = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = _zh ? $"符号 {sym}" : $"Symbol {sym}",
                Content = new TextBlock
                {
                    Text = _zh ? TranslateTerms(_symInfo[sym]) : _symInfo[sym],
                    FontSize = 15,
                    FontFamily = new Microsoft.UI.Xaml.Media.FontFamily(
                        "Gentium Book Plus"),
                    TextWrapping = TextWrapping.Wrap,
                },
                PrimaryButtonText = fav
                    ? (_zh ? "从收藏移除" : "Remove from favorites")
                    : (_zh ? "加入收藏" : "Add to favorites"),
                CloseButtonText = _zh ? "确定" : "OK",
            };
            dlg.PrimaryButtonClick += (s2, e2) => ToggleFavorite(sym);
            dlg.ShowAsync();
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
            catch { }
            RebuildKeyboard(FilterBox.Text.Trim());
        }

        private static readonly string[] TieComposites =
        {
            "t͡ʃ", "d͡ʒ", "t͡s", "d͡z", "t͡ɕ", "d͡ʑ",
            "ʈ͡ʂ", "ɖ͡ʐ", "k͡p", "ɡ͡b", "k͡x", "q͡χ", "ŋ͡m",
        };

        private readonly Dictionary<string, string> _symInfo = new();
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
                { "lab.dnt", "唇齿" }, { "lbd", "唇齿" },
                { "dnt", "齿" }, { "den", "齿" },
                { "alv", "齿龈" }, { "rfl", "卷舌" }, { "alvpal", "龈腭" },
                { "pst", "龈后" }, { "pal", "腭" }, { "vel", "软腭" },
                { "uvu", "小舌" }, { "pha", "咽" }, { "epl", "会厌" },
                { "phr", "咽" }, { "epi", "会厌" }, { "glo", "喉" },
                { "glt", "喉" },
                { "pls", "塞音" }, { "nas", "鼻" }, { "frc", "擦音" },
                { "appr", "近音" }, { "apx", "近音" },
                { "lat", "边音" }, { "tap", "闪音" }, { "flp", "拍音" },
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
                { "rhot", "卷舌化" }, { "ej", "挤喉" }, { "ejt", "挤喉音" },
                { "clk", "搭嘴音" }, { "imp", "内爆音" },
                { "pulmonic", "肺部气流" }, { "glottalic egressive", "挤喉音" },
                { "glottalic ingressive", "内爆音" }, { "lingual", "搭嘴音" },
                { "percussive", "敲击音" },
                /* modifier-detail framework words */
                { "modifier: ", "修饰符：" },
                { "extIPA base: ", "extIPA 基段：" },
                { "base: ", "基段：" },
                { "tier=", "层级=" },
                { "[sets airstream]", "[设置气流]" },
                { "[inference]", "[推断]" },
                /* superscript / subscript letters */
                { "sup_rhot_ʢ", "卷舌化上标ʢ" }, { "sup_rhot_ʕ", "卷舌化上标ʕ" },
                { "sup_rhot_ʁ", "卷舌化上标ʁ" }, { "sup_rhot_r", "卷舌化上标r" },
                { "sup_e", "上标e" }, { "sup_u", "上标u" },
                { "sup_O", "上标O" }, { "sup_U", "上标U" },
                { "sup_W", "上标W" }, { "sup_ɛ", "上标ɛ" },
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
                { "pitch_midrise", "中升" }, { "pitch_midfall", "中降" },
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
                { "half", "半长" }, { "unrel", "未除阻" },
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
                { "alveolar", "齿龈" }, { "apical", "舌尖" },
                { "laminal", "舌叶" }, { "retroflex", "卷舌" },
                { "phar", "咽化" }, { "glottal_onset", "喉塞起始" },
                { "nas_click", "鼻搭嘴" },
                { "schwa_rel", "ə化" }, { "offglide", "滑音" },
                { "rnd_less", "少圆唇" }, { "rnd_more", "多圆唇" },
                { "lam", "舌叶" },
            };

        /* translate feature abbreviations in symbol details. Keys are
         * replaced only at token boundaries (not inside words), so e.g.
         * "fr" cannot corrupt "fric" and "lab" cannot corrupt "labial".
         * Longest keys first (omid before mid, labiodental before lab). */
        private static string TranslateTerms(string text)
        {
            foreach (var kv in TermMap.OrderByDescending(k => k.Key.Length))
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
        {            if (sym.Contains('\u25CC'))
                sym = sym.Replace("\u25CC", "");
            return Core.Query(sym);
        }

        private Button MakeKey(string sym, double fontSize = 14)
        {
            var btn = new Button
            {
                Content = sym,
                FontSize = fontSize,
                MinWidth = 44,
                MinHeight = 34,
                Padding = new Thickness(3, 2, 3, 2),
                Margin = new Thickness(2),
            };
            if (!_symInfo.ContainsKey(sym))
                _symInfo[sym] = QuerySymbol(sym);
            ToolTipService.SetToolTip(btn, _zh ? TranslateTerms(_symInfo[sym]) : _symInfo[sym]);
            /* left press starts glide mode; left release types via Click.
             * Gliding over neighbouring keys types while held down.
             * Right press shows the symbol details instead. */
            btn.PointerPressed += (s, e) =>
            {
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
                catch { }
                _slideMode = true;
                _slid = false;
            };
            btn.PointerEntered += (s, e) =>
            {
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
                if (!_slid)
                    AppendToInput(sym);
                _slid = false;
            };
            return btn;
        }

        /* set the IPA input programmatically (no placeholder reset) */
        private void SetIpaInputRight(string text)
        {
            _programmatic = true;
            IpaInputRight.Text = text;
            _programmatic = false;
            _placeholder = false;
        }

        private void AppendToInput(string sym)
        {
            try
            {
                File.AppendAllText(
                    Path.Combine(Path.GetTempPath(), "vec4ipa", "kb.log"),
                    $"{DateTime.Now:HH:mm:ss.fff}: append '{sym}' " +
                    $"pressed={_kbPressedBox?.GetType().Name ?? "null"} " +
                    $"focused={_focusedBox?.GetType().Name ?? "null"}\n");
            }
            catch { }
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
            if (_recentBtns.TryGetValue(sym, out var old))
                RecentKeys.Items.Remove(old);
            _recent.Remove(sym);
            _recent.Insert(0, sym);
            var btn = MakeKey(sym);
            _recentBtns[sym] = btn;
            RecentKeys.Items.Insert(0, btn);
            while (_recent.Count > 60)
            {
                string last = _recent[^1];
                _recent.RemoveAt(_recent.Count - 1);
                if (_recentBtns.Remove(last, out var b))
                    RecentKeys.Items.Remove(b);
            }
        }

        private void Example_Click(object sender, RoutedEventArgs e)
        {
            var item = (MenuFlyoutItem)sender;
            string text = item.Text;
            int cut = text.IndexOf(": ");
            string ipa = cut >= 0 ? text[(cut + 2)..] : text;
            ipa = ipa.Split(' ')[0]; // symbol = first token, rest is description
            IpaInputRight.Text = ipa;
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

        private void AddHistory(string title, string body)
        {
            _history.Add((title, body));
            while (_history.Count > 200)
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
            int fmt = FormatCombo.SelectedIndex;
            string? result;
            switch (fmt)
            {
                case 1:
                    result = Core.Ir(ipa);
                    AppendOutput($"=== IPA -> IR ===\ninput: /{ipa}/\n" + result);
                    break;
                case 2:
                    result = Core.Json(ipa);
                    AppendOutput($"=== IPA -> JSON ===\ninput: /{ipa}/\n" + result);
                    break;
                default:
                    result = _featureNames ? Core.ForwardNamed(ipa)
                                           : Core.Forward(ipa, out _);
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
                                     "Hmm, I could not parse: /" + ipa + "/\n" + hint);
                        break;
                    }
                    AppendOutput(_featureNames
                        ? $"=== IPA -> vectors (feature names) ===\ninput: /{ipa}/\n" + result
                        : $"=== IPA -> vectors ===\ninput: /{ipa}/\n" + result);
                    break;
            }
            AddHistory("Convert: " + ipa, result);
            SetStatus("converted " + ipa.Length + " chars");
            IpaInputRight.Focus(FocusState.Programmatic);
        }

        private void ReverseBtn_Click(object sender, RoutedEventArgs e)
        {
            int width = WidthCombo.SelectedIndex;
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
            OutputAppendRaw(text);
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

        private void OutputAppendRaw(string text)
        {
            OutputBox.Document.GetText(
                Microsoft.UI.Text.TextGetOptions.None, out string cur);
            cur = cur ?? "";
            string sep = cur.Length > 0 && cur[^1] != '\r' && cur[^1] != '\n'
                ? "\r" : "";
            OutputSet(cur + sep + text);
            var sel = OutputBox.Document.Selection;
            sel.StartPosition = sel.EndPosition = int.MaxValue;
            ScrollToEnd();
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
            catch { }
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
            catch { }
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
            catch { }
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

        private void About_Click(object sender, RoutedEventArgs e)
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
            dlg.ShowAsync();
        }

        private void Docs_Click(object sender, RoutedEventArgs e)
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
            dlg.ShowAsync();
        }

        private void ExportCmd_Click(object sender, RoutedEventArgs e)
        {
            string dir = AppContext.BaseDirectory;
            string text =
                "# vec4ipa CLI commands\n" +
                $"# app directory: {dir}\n\n" +
                ":: ipa2vec - IPA -> 16-D vectors\n" +
                $"\"{Path.Combine(dir, "tools", "ipa2vec.exe")}\" --width 3 -i \"\\\"\\u02c8t\\u02b0a\\\"\"\n\n" +
                ":: vec2ipa - 16-D vector -> IPA\n" +
                $"\"{Path.Combine(dir, "tools", "vec2ipa.exe")}\" --width 3 " +
                "\"0.0,0.0,0.55,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0,0.0,0.0,1.0\"\n\n" +
                ":: vec4ipa - inventory / query / reverse\n" +
                $"\"{Path.Combine(dir, "tools", "vec4ipa.exe")}\" -q \\u02b0\n" +
                $"\"{Path.Combine(dir, "tools", "vec4ipa.exe")}\" --width 3 -r " +
                "\"0.0,0.0,0.55,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0,0.0,0.0,1.0\"\n";
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
            dlg.PrimaryButtonClick += (s, e2) =>
            {
                try
                {
                    var dp = new Windows.ApplicationModel.DataTransfer.DataPackage();
                    dp.SetText(box.Text);
                    Windows.ApplicationModel.DataTransfer.Clipboard.SetContent(dp);
                }
                catch { }
            };
            dlg.ShowAsync();
        }

        private async void ExportTools_Click(object sender, RoutedEventArgs e)
        {
            var picker = new Windows.Storage.Pickers.FolderPicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.FileTypeFilter.Add("*");
            var folder = await picker.PickSingleFolderAsync();
            if (folder == null) return;

            string src = Path.Combine(AppContext.BaseDirectory, "tools");
            string[] names = { "ipa2vec.exe", "vec2ipa.exe", "vec4ipa.exe" };
            int ok = 0, missing = 0;
            foreach (var name in names)
            {
                string from = Path.Combine(src, name);
                if (!File.Exists(from)) { missing++; continue; }
                try
                {
                    var f = await Windows.Storage.StorageFile.GetFileFromPathAsync(from);
                    await f.CopyAsync(folder, name,
                        Windows.Storage.NameCollisionOption.ReplaceExisting);
                    ok++;
                }
                catch { }
            }
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
}
