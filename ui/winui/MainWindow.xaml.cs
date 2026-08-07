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

namespace IPA2VectorUI
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
                "IPA2VectorUI", "window.ini");

        public MainWindow() : this(Array.Empty<string>()) { }

        public MainWindow(string[] args)
        {
            InitializeComponent();
            Title = "IPA2Vector Workbench";
            SetIcon();
            RestoreState();
            BuildKeyboard();
            IpaInput.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    ConvertBtn_Click(s, e);
                    e.Handled = true;
                }
            };
            IpaInput.TextChanged += (s, e) =>
            {
                if (IpaInput.Text != "t\u02b0a") _placeholder = false;
                UpdateButtons();
            };
            VecInput.TextChanged += (s, e) => UpdateButtons();
            QueryInput.TextChanged += (s, e) => UpdateButtons();
            DistA.TextChanged += (s, e) => UpdateButtons();
            DistB.TextChanged += (s, e) => UpdateButtons();
            VecInput.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    ReverseBtn_Click(s, e);
                    e.Handled = true;
                }
            };
            QueryInput.KeyDown += (s, e) =>
            {
                if (e.Key == Windows.System.VirtualKey.Enter)
                {
                    QueryBtn_Click(s, e);
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
            BuildModulesMenu();
            InitStatus();
            ShowWelcome();
            UpdateButtons();
            /* clicking away clears the selection highlight */
            OutputBox.LostFocus += (s, e) => OutputBox.SelectionLength = 0;
            HandleArgs(args);
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
            ConvertBtn.IsEnabled = IpaInput.Text.Length > 0;
            ReverseBtn.IsEnabled = VecInput.Text.Trim().Length > 0;
            QueryBtn.IsEnabled = QueryInput.Text.Length > 0;
            DistBtn.IsEnabled = DistA.Text.Length > 0 && DistB.Text.Length > 0;
        }

        private void ShowWelcome()
        {
            string welcome =
                "Welcome to IPA2Vector Workbench!\n" +
                "---------------------------------\n\n" +
                "1. Type or click an IPA string below (or pick an example\n" +
                "   from File > Examples).\n" +
                "2. Press Convert - each segment becomes a 16-D vector.\n" +
                "3. Paste a vector and press Reverse to fit IPA back,\n" +
                "   choosing the transcription width (0-4).\n\n" +
                "Tip: hover a keyboard key for its name, double-click for\n" +
                "details; symbols you use are collected on the Recent tab.\n\n" +
                "Example to try:  t\u02b0a  (aspirated stop + open vowel)";
            OutputBox.Text = welcome;
            IpaInput.Text = "t\u02b0a";
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
                    appWindow.SetIcon(icon);
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
                else if (a == "--width" && i + 1 < args.Length) i++;
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
                    Title = "IPA2Vector Workbench - usage",
                    Content =
                        "ipa2vec_ui [OPTIONS] [IPA-STRING]\n\n" +
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
                QueryInput.Text = query;
                QueryBtn_Click(this, new RoutedEventArgs());
            }
            if (reverse && vec != null)
            {
                VecInput.Text = vec;
                ReverseBtn_Click(this, new RoutedEventArgs());
            }
            else if (input != null)
            {
                IpaInput.Text = input;
                ConvertBtn_Click(this, new RoutedEventArgs());
            }
        }

        /* ---- View menu: school modules as checkable items ---- */
        private void BuildModulesMenu()
        {
            foreach (var name in Core.Modules())
            {
                var item = new ToggleMenuFlyoutItem
                {
                    Text = "--" + name,
                    IsChecked = false,
                };
                item.Click += (s, e) =>
                {
                    var it = (ToggleMenuFlyoutItem)s;
                    if (it.IsChecked)
                        Core.SetArgs(new[] { "--" + name });
                    else
                        Core.SetArgs(Array.Empty<string>());
                    SetStatus(it.IsChecked
                        ? $"module enabled: {name}"
                        : "module disabled");
                };
                ModulesSub.Items.Add(item);
            }
            if (ModulesSub.Items.Count == 0)
                ModulesSub.IsEnabled = false;
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
            if (IpaInput.Text.Length == 0)
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
            string? err = Core.IrExport(IpaInput.Text, baseName);
            if (err != null) SetStatus("IR export failed: " + err);
            else
            {
                SetStatus("IR written to " + baseName + ".layer1/.layer2");
                AppendOutput($"=== IR exported: {baseName}.layer1/.layer2 ===");
            }
        }

        private void DistBtn_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput($"=== Distance {DistA.Text} ~ {DistB.Text} ===\n" +
                         Core.Distance(DistA.Text, DistB.Text));
            SetStatus("distance computed");
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
                await Windows.Storage.FileIO.WriteTextAsync(file, OutputBox.Text);
                SetStatus("output saved: " + file.Path);
            }
            catch (Exception ex)
            {
                SetStatus("save failed: " + ex.Message);
            }
        }

        private void ClearOutput_Click(object sender, RoutedEventArgs e)
        {
            OutputBox.Text = "";
            SetStatus("output cleared");
        }

        private void CopyOutput_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                var dp = new Windows.ApplicationModel.DataTransfer.DataPackage();
                dp.SetText(OutputBox.Text);
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

        private void Compare_Click(object sender, RoutedEventArgs e)
        {
            string a = DistA.Text, b = DistB.Text;
            if (a.Length == 0 || b.Length == 0)
            {
                SetStatus("type two symbols in the Distance boxes first");
                return;
            }
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
            AppendOutput("=== Compare ===\n" + sb.ToString().TrimEnd());
            SetStatus("comparison shown");
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

        private void FeatureNames_Click(object sender, RoutedEventArgs e)
        {
            _featureNames = ((ToggleMenuFlyoutItem)sender).IsChecked;
            SetStatus(_featureNames
                ? "vector output uses feature names"
                : "vector output uses plain numbers");
        }

        private void Theme_Click(object sender, RoutedEventArgs e)
        {
            var item = (RadioMenuFlyoutItem)sender;
            ApplyTheme(item.Text);
        }

        private void ApplyTheme(string name)
        {
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
                if (KeyboardPivot is Microsoft.UI.Xaml.Controls.Pivot p)
                    p.Background = null;
                if (StatusText.Parent is Microsoft.UI.Xaml.Controls.Grid sg)
                    sg.Background = null;
                return;
            }
            /* apply to every container we own */
            if (root is Microsoft.UI.Xaml.Controls.Grid rg)
                rg.Background = bg;
            if (KeyboardPivot is Microsoft.UI.Xaml.Controls.Pivot p2)
                p2.Background = bg;
            if (StatusText.Parent is Microsoft.UI.Xaml.Controls.Grid sg2)
                sg2.Background = bg;
        }

        private void Loop_Click(object sender, RoutedEventArgs e)
        {
            string ipa = IpaInput.Text;
            if (ipa.Length == 0) return;
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
                string csv = "symbol,feature,value\n";
                var rows = Core.ForwardRaw(""); // no-op guard
                _ = rows;
                var names = Core.DimNames;
                csv = Core.Table().Replace('\t', ',').Replace("\n", "\r\n");
                await Windows.Storage.FileIO.WriteTextAsync(file, csv);
                SetStatus("CSV saved: " + file.Path);
            }
            catch (Exception ex)
            {
                SetStatus("CSV save failed: " + ex.Message);
            }
        }

        private bool _zh;

        private void Lang_Click(object sender, RoutedEventArgs e)
        {
            _zh = ((RadioMenuFlyoutItem)sender).Text == "中文";
            var lbls = new[]
            {
                (LblIpa, _zh ? "IPA 输入（点击软键盘按钮或直接输入）："
                             : "IPA input (click keyboard buttons or type):"),
                (LblVec, _zh ? "16 维向量（逗号分隔）→ 反向拟合："
                             : "16-D vector (comma separated) → reverse fit:"),
                (LblQuery, _zh ? "查询单个符号：" : "Query one symbol:"),
                (LblDist, _zh ? "两个符号之间的距离：" : "Distance between two symbols:"),
                (LblOut, _zh ? "输出：" : "Output:"),
            };
            foreach (var (ctl, text) in lbls)
                ctl.Text = text;
            ConvertBtn.Content = _zh ? "转换" : "Convert";
            ReverseBtn.Content = _zh ? "反向" : "Reverse";
            QueryBtn.Content = _zh ? "查询" : "Query";
            DistBtn.Content = _zh ? "距离" : "Distance";
        }

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

        private void BuildKeyboard()
        {
            AddKeys(ConsKeys, Core.KeyboardCons(), appendTieKeys: true);
            /* vowels: sort by trapezium position (row, col) so the flow
             * layout approximates the IPA vowel chart */
            var pos = Core.VowelPositions();
            var vowels = Core.KeyboardVowels().ToList();
            vowels.Sort((a, b) =>
            {
                (int Row, int Col) pa = pos.TryGetValue(a, out var x)
                    ? x : (0, 0);
                (int Row, int Col) pb = pos.TryGetValue(b, out var y)
                    ? y : (0, 0);
                int r = pa.Row.CompareTo(pb.Row);
                return r != 0 ? r : pa.Col.CompareTo(pb.Col);
            });
            AddKeys(VowKeys, vowels.ToArray(), appendTieKeys: false);
            AddKeys(ModKeys, Core.KeyboardMods(), appendTieKeys: false);
            AddKeys(ToneKeys, Core.KeyboardTones(), appendTieKeys: false);
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
        private bool _placeholder;

        private void AddKeys(ItemsControl host, string[] symbols,
                             bool appendTieKeys)
        {
            foreach (var sym in symbols)
                host.Items.Add(MakeKey(sym));
            if (appendTieKeys)
                foreach (var sym in TieComposites)
                    host.Items.Add(MakeKey(sym, fontSize: 13));
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
                _symInfo[sym] = Core.Query(sym);
            ToolTipService.SetToolTip(btn, _symInfo[sym]);
            btn.Click += (s, e) => AppendToInput(sym);
            btn.DoubleTapped += (s, e) =>
            {
                var dlg = new ContentDialog
                {
                    XamlRoot = Content.XamlRoot,
                    Title = $"Symbol {sym}",
                    Content = new TextBlock
                    {
                        Text = _symInfo[sym],
                        FontSize = 15,
                        FontFamily = new Microsoft.UI.Xaml.Media.FontFamily(
                            "Gentium Book Plus"),
                        TextWrapping = TextWrapping.Wrap,
                    },
                    CloseButtonText = "OK",
                };
                dlg.ShowAsync();
            };
            return btn;
        }

        private void AppendToInput(string sym)
        {
            /* the welcome example ("tʰa") is a placeholder: the first
             * symbol the user picks replaces it instead of appending */
            if (_placeholder)
            {
                IpaInput.Text = "";
                _placeholder = false;
            }
            /* keyboard buttons show diacritics on a dotted circle (◌,
             * U+25CC) as a hint; strip the circle before inserting */
            if (sym.Contains('\u25CC'))
                sym = sym.Replace("\u25CC", "");
            /* combining modifiers (◌...) need a base symbol before them */
            if (IpaInput.Text.Length == 0 && IsCombiningModifier(sym))
            {
                SetStatus("start with a base symbol first (e.g. t, a), then add " + sym);
                return;
            }
            IpaInput.Text += sym;
            IpaInput.SelectionStart = IpaInput.Text.Length;
            IpaInput.Focus(FocusState.Programmatic);
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
            IpaInput.Text = ipa;
            IpaInput.Focus(FocusState.Programmatic);
            FormatCombo.SelectedIndex = 0;
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

        private void ConvertBtn_Click(object sender, RoutedEventArgs e)
        {
            string ipa = IpaInput.Text;
            if (ipa.Length == 0) return;
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
            _history.Add(("Convert: " + ipa, result));
            SetStatus("converted " + ipa.Length + " chars");
            IpaInput.Focus(FocusState.Programmatic);
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
            _history.Add(("Reverse (width " + width + ")", result));
            SetStatus("reverse fit done (" + lines.Length + " vector(s))");
            VecInput.Focus(FocusState.Programmatic);
        }

        private void QueryBtn_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput($"=== Query: {QueryInput.Text} ===\n" +
                         Core.Query(QueryInput.Text));
            SetStatus("query done");
        }

        private void AppendOutput(string text)
        {
            OutputBox.Text = string.IsNullOrEmpty(OutputBox.Text)
                ? text : OutputBox.Text + "\n" + text;
            OutputBox.SelectionStart = OutputBox.Text.Length;
            OutputBox.SelectionLength = 0;
            ScrollToEnd();
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
                Title = "About IPA2Vector Workbench",
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
                "# IPA2Vector CLI commands\n" +
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
