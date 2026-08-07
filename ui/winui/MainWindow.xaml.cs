using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using System;

namespace IPA2VectorUI
{
    public sealed partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();
            Title = "IPA2Vector Workbench";
            BuildKeyboard();
        }

        private void BuildKeyboard()
        {
            AddKeys(ConsKeys, Core.KeyboardCons());
            AddKeys(VowKeys, Core.KeyboardVowels());
            AddKeys(ModKeys, Core.KeyboardMods());
            AddKeys(ToneKeys, ToneSymbols());
        }

        private static readonly string[] ToneSymbolsList =
        {
            "\u02E5", "\u02E6", "\u02E7", "\u02E8", "\u02E9",   // ˥˦˧˨˩
            "\uA712", "\uA713", "\uA714", "\uA715", "\uA716",   // ꜒꜓꜔꜕꜖
            "\u2197", "\u2198", "\uA71B", "\uA71C",              // ↗↘ꜛꜜ
            "\u2070", "\u00B9", "\u00B2", "\u00B3", "\u2074",   // ⁰¹²³⁴
            "\u2075", "\u2076", "\u2077", "\u2078", "\u2079",   // ⁵⁶⁷⁸⁹
            "\u203F", " ",                                      // ‿ space
        };

        private static string[] ToneSymbols() => ToneSymbolsList;

        private void AddKeys(ItemsControl host, string[] symbols)
        {
            foreach (var sym in symbols)
            {
                var btn = new Button
                {
                    Content = sym,
                    FontSize = 16,
                    MinWidth = 40,
                    MinHeight = 34,
                    Margin = new Thickness(2),
                };
                btn.Click += (s, e) => AppendToInput(sym);
                host.Items.Add(btn);
            }
        }

        private void AppendToInput(string sym)
        {
            IpaInput.Text += sym;
            IpaInput.SelectionStart = IpaInput.Text.Length;
            IpaInput.Focus(FocusState.Programmatic);
        }

        private void ConvertBtn_Click(object sender, RoutedEventArgs e)
        {
            string? error;
            var result = Core.Forward(IpaInput.Text, out error);
            if (result == null)
                AppendOutput($"parse error: {error}");
            else
                AppendOutput($"=== IPA -> vectors ===\n{result}");
        }

        private void ReverseBtn_Click(object sender, RoutedEventArgs e)
        {
            int width = WidthCombo.SelectedIndex;
            if (width < 0) width = 3;
            AppendOutput($"=== Vector -> IPA (width {width}) ===\n" +
                         Core.Reverse(VecInput.Text, width));
        }

        private void QueryBtn_Click(object sender, RoutedEventArgs e)
        {
            AppendOutput($"=== Query ===\n{Core.Query(QueryInput.Text)}");
        }

        private void AppendOutput(string text)
        {
            OutputBox.Text = string.IsNullOrEmpty(OutputBox.Text)
                ? text : OutputBox.Text + "\n" + text;
            OutputBox.SelectionStart = OutputBox.Text.Length;
        }
    }
}
