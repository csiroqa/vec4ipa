use std::path::{Path, PathBuf};

use rfd::FileDialog;
use windows_reactor::*;

use crate::engine::{Engine, Segment, ToneGroup, describe_query};
use crate::keyboard::{self, KeyboardModel};
use crate::layout::{
    Density, LayoutMetrics, LayoutMode, NarrowPane, is_collapsed, keyboard_columns, layout_mode,
    toggle_section,
};
use crate::modules::{self, ModuleKind, Registry};
use crate::settings::{
    Language, ModuleProfile, PROFILE_ALL_OFF, PROFILE_ALL_ON, PROFILE_CUSTOM, Settings, ThemeChoice,
};
use crate::startup::{Startup, is_modifier_symbol};
use crate::win32;

const EXAMPLES: &[&str] = &["tʰeɪk", "ã", "t͡ʃ", "ma˩˨", "ɬ", "k͡p", "t̬˞̩ˤ"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OutputFormat {
    Vectors,
    Ir,
    Json,
}

impl OutputFormat {
    fn label(self) -> &'static str {
        match self {
            Self::Vectors => "Vectors",
            Self::Ir => "IR",
            Self::Json => "JSON",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ViewKind {
    None,
    Table,
    Modules,
    Stats,
    Weights,
    Effective,
    Dimensions,
    Docs,
}

#[derive(Clone, Debug)]
struct HistoryEntry {
    label: String,
    input: String,
    output: String,
}

struct KeyboardGroupSpec<'a> {
    id: &'static str,
    title: &'static str,
    symbols: &'a [String],
    always: bool,
    font_size: f64,
}

#[derive(Clone)]
pub enum Message {
    InputChanged(String),
    ReverseChanged(String),
    FilterChanged(String),
    QueryChanged(String),
    CompareA(String),
    CompareB(String),
    AlignA(String),
    AlignB(String),
    Convert,
    Loop,
    Clear,
    Reverse,
    SetFormat(OutputFormat),
    SetNarrowness(u8),
    Symbol(String),
    AddFavorite,
    HistorySelect(usize),
    Example(usize),
    ClearHistory,
    ThemeCycle,
    LanguageToggle,
    PinToggle,
    ToggleDensity,
    ResetLayout,
    ToggleSection(String),
    SetNarrowPane(NarrowPane),
    OpenKeyboard,
    CloseKeyboard,
    ToggleKeyboardMode,
    SplitChanged(f64),
    WindowSize(WindowSize),
    LoadScheme,
    LoadMetric,
    SaveOutput,
    OpenIpaFile,
    ExportCsv,
    ExportIr,
    ExportTools,
    ShowView(ViewKind),
    ShowCommand,
    Query,
    Compare,
    Align,
    ModuleFilterChanged(String),
    ProfileNameChanged(String),
    ToggleModule(String),
    SetAllModules(ModuleKind, bool),
    ApplyProfile(String),
    SaveProfile,
    DeleteProfile,
}

pub struct Workbench {
    engine: Engine,
    settings: Settings,
    lang: Language,
    theme: ThemeChoice,
    density: Density,
    narrow_pane: NarrowPane,
    keyboard_open: bool,
    keyboard_mode: bool,
    window_handle: isize,
    collapsed_sections: Vec<String>,
    always_on_top: bool,
    split: f64,
    window_width: f64,
    window_height: f64,
    window_size_seen: bool,
    window_size_events: u8,
    input: String,
    output: String,
    reverse_input: String,
    narrowness: u8,
    format: OutputFormat,
    filter: String,
    recent: Vec<String>,
    favorites: Vec<String>,
    history: Vec<HistoryEntry>,
    view: ViewKind,
    view_text: String,
    query: String,
    compare_a: String,
    compare_b: String,
    align_a: String,
    align_b: String,
    status: String,
    keyboard: KeyboardModel,
    modules: Registry,
    enabled_parser: Vec<String>,
    enabled_keyboard: Vec<String>,
    module_filter: String,
    profile_name: String,
    active_profile: String,
    font_loaded: bool,
}

impl Component for Workbench {
    type Input = Startup;
    type Message = Message;

    fn create(startup: &Startup, _context: &ComponentContext<Self>) -> Self {
        let settings = crate::settings::load();
        let theme = startup.theme.unwrap_or(settings.theme);
        let mut engine = Engine::new();
        let mut status = String::new();

        if let Some(scheme) = startup.scheme.clone().or_else(|| settings.scheme.clone()) {
            if Path::new(&scheme).exists() {
                let _ = engine.set_args(&["-D", &scheme]);
            } else {
                status = format!("scheme not found: {scheme}");
            }
        }
        let narrowness = startup.narrowness;
        let _ = engine.set_args(&["--narrowness", &narrowness.to_string()]);
        if let Some(metric) = startup.metric.clone().or_else(|| settings.metric.clone()) {
            if Path::new(&metric).exists() {
                if let Err(error) = engine.load_metric(&metric) {
                    status = format!("metric: {error}");
                }
            } else {
                status = format!("metric not found: {metric}");
            }
        }

        let keyboard = build_keyboard(&engine);
        let modules = match Registry::build(engine.modules_all(), &keyboard) {
            Ok(registry) => registry,
            Err(error) => {
                status = if status.is_empty() {
                    error
                } else {
                    format!("{status}; {error}")
                };
                Registry::default()
            }
        };
        let enabled_parser =
            modules.reconcile(ModuleKind::Parser, &settings.enabled_parser_modules);
        let enabled_keyboard =
            modules::initial_keyboard(&modules, settings.keyboard_modules.as_deref());
        let mut ignored = settings
            .enabled_parser_modules
            .iter()
            .filter(|id| !enabled_parser.contains(id))
            .count();
        if let Some(saved) = &settings.keyboard_modules {
            ignored += saved
                .iter()
                .filter(|id| !enabled_keyboard.contains(id))
                .count();
        }
        if ignored > 0 {
            let note = format!("ignored {ignored} saved module ids");
            status = if status.is_empty() {
                note
            } else {
                format!("{status}; {note}")
            };
        }
        let parser_names = enabled_parser
            .iter()
            .filter_map(|id| modules.find(id))
            .map(|module| module.key.clone())
            .collect::<Vec<_>>();
        let _ = engine.set_modules(&parser_names);
        let font_loaded = win32::load_private_font(&win32::bundled_font());
        let active_profile = settings.active_profile.clone();

        let mut workbench = Self {
            engine,
            settings: settings.clone(),
            lang: settings.language,
            theme,
            density: settings.density,
            narrow_pane: settings.narrow_pane,
            keyboard_open: false,
            keyboard_mode: false,
            window_handle: 0,
            collapsed_sections: settings.collapsed_sections.clone(),
            always_on_top: settings.always_on_top,
            split: settings.split.clamp(0.25, 0.75),
            window_width: settings.width,
            window_height: settings.height,
            window_size_seen: false,
            window_size_events: 0,
            input: startup.input.clone().unwrap_or_default(),
            output: String::new(),
            reverse_input: startup.reverse.clone().unwrap_or_default(),
            narrowness,
            format: OutputFormat::Vectors,
            filter: String::new(),
            recent: Vec::new(),
            favorites: crate::favorites::path()
                .map_or_else(Vec::new, |path| crate::favorites::load_from(&path)),
            history: Vec::new(),
            view: ViewKind::None,
            view_text: String::new(),
            query: startup.query.clone().unwrap_or_default(),
            compare_a: "ʃ".to_string(),
            compare_b: "s".to_string(),
            align_a: "tʰa".to_string(),
            align_b: "ta".to_string(),
            status,
            keyboard,
            modules,
            enabled_parser,
            enabled_keyboard,
            module_filter: String::new(),
            profile_name: String::new(),
            active_profile,
            font_loaded,
        };

        if workbench.active_profile != PROFILE_CUSTOM
            && !workbench.profile_matches(&workbench.active_profile.clone())
        {
            workbench.active_profile = workbench.detect_profile();
        }
        workbench.settings.enabled_parser_modules = workbench.enabled_parser.clone();
        workbench.settings.keyboard_modules = Some(workbench.enabled_keyboard.clone());
        workbench.settings.active_profile = workbench.active_profile.clone();

        if let Some(reverse) = &startup.reverse {
            workbench.reverse_input = reverse.clone();
            workbench.convert_reverse();
        } else if let Some(query) = &startup.query {
            workbench.query = query.clone();
            workbench.run_query();
        } else if !workbench.input.is_empty() {
            workbench.convert_forward();
        }

        if let Some(destination) = &startup.export_tools {
            match win32::copy_tools(Path::new(destination)) {
                Ok(count) => workbench.status = format!("exported {count} tools"),
                Err(error) => workbench.status = error,
            }
        }
        if !workbench.font_loaded {
            workbench.status = format!("{} (font fallback)", workbench.status);
        }
        workbench
    }

    fn update(&mut self, message: Message, _context: &ComponentContext<Self>) {
        match message {
            Message::InputChanged(value) => self.input = value,
            Message::ReverseChanged(value) => self.reverse_input = value,
            Message::FilterChanged(value) => self.filter = value,
            Message::QueryChanged(value) => self.query = value,
            Message::CompareA(value) => self.compare_a = value,
            Message::CompareB(value) => self.compare_b = value,
            Message::AlignA(value) => self.align_a = value,
            Message::AlignB(value) => self.align_b = value,
            Message::Convert => self.convert_forward(),
            Message::Loop => self.run_loop(),
            Message::Clear => {
                self.input.clear();
                self.output.clear();
                self.status = self.t("cleared", "已清空").to_string();
            }
            Message::Reverse => self.convert_reverse(),
            Message::SetFormat(format) => {
                self.format = format;
                if !self.input.trim().is_empty() {
                    self.convert_forward();
                }
            }
            Message::SetNarrowness(level) => {
                self.narrowness = level.min(4);
                let _ = self
                    .engine
                    .set_args(&["--narrowness", &self.narrowness.to_string()]);
                if !self.reverse_input.trim().is_empty() {
                    self.convert_reverse();
                }
            }
            Message::Symbol(symbol) => {
                if self.keyboard_mode {
                    self.send_symbol(&symbol);
                } else {
                    self.append_symbol(&symbol);
                }
            }
            Message::AddFavorite => self.add_favorite(),
            Message::HistorySelect(index) => {
                if let Some(entry) = self.history.get(index).cloned() {
                    self.input = entry.input;
                    self.output = entry.output;
                }
            }
            Message::Example(index) => {
                if let Some(example) = EXAMPLES.get(index) {
                    self.input = (*example).to_string();
                    self.convert_forward();
                }
            }
            Message::ClearHistory => self.history.clear(),
            Message::ThemeCycle => {
                self.theme = self.theme.next();
                self.settings.theme = self.theme;
                self.settings.save();
            }
            Message::LanguageToggle => {
                self.lang = self.lang.toggled();
                self.settings.language = self.lang;
                self.settings.save();
            }
            Message::PinToggle => {
                self.always_on_top = !self.always_on_top;
                if !win32::set_always_on_top(self.always_on_top) {
                    self.status = self
                        .t("could not change topmost", "无法切换置顶")
                        .to_string();
                }
                self.settings.always_on_top = self.always_on_top;
                self.settings.save();
            }
            Message::ToggleDensity => {
                self.density = self.density.next();
                self.settings.density = self.density;
                self.settings.save();
            }
            Message::ResetLayout => {
                self.settings.reset_layout();
                self.density = self.settings.density;
                self.split = self.settings.split;
                self.narrow_pane = self.settings.narrow_pane;
                self.collapsed_sections = self.settings.collapsed_sections.clone();
                self.settings.save();
                self.status = self.t("layout reset", "布局已重置").to_string();
            }
            Message::ToggleSection(id) => {
                toggle_section(&mut self.collapsed_sections, &id);
                self.settings.collapsed_sections = self.collapsed_sections.clone();
                self.settings.save();
            }
            Message::SetNarrowPane(pane) => {
                self.narrow_pane = pane;
                self.settings.narrow_pane = pane;
                self.settings.save();
            }
            Message::OpenKeyboard => self.keyboard_open = true,
            Message::CloseKeyboard => self.keyboard_open = false,
            Message::ToggleKeyboardMode => self.toggle_keyboard_mode(),
            Message::SplitChanged(value) => {
                self.split = value.clamp(0.25, 0.75);
                self.settings.split = self.split;
                self.settings.save();
            }
            Message::WindowSize(size) => {
                if !self.window_size_seen {
                    self.window_size_events = self.window_size_events.saturating_add(1);
                    let matches = (size.width - self.window_width).abs() <= 1.0
                        && (size.height - self.window_height).abs() <= 1.0;
                    // The first event reports the size the window manager restored,
                    // before the saved size is applied. Keep the saved size unless
                    // the event already matches it, and accept the reported size
                    // after one more event so the window can never lock.
                    if !matches && self.window_size_events < 2 {
                        return;
                    }
                    self.window_size_seen = true;
                }
                self.window_width = size.width;
                self.window_height = size.height;
                self.settings.width = size.width;
                self.settings.height = size.height;
                self.settings.save();
            }
            Message::LoadScheme => self.load_scheme(),
            Message::LoadMetric => self.load_metric(),
            Message::SaveOutput => self.save_output(),
            Message::OpenIpaFile => self.open_ipa_file(),
            Message::ExportCsv => self.export_csv(),
            Message::ExportIr => self.export_ir(),
            Message::ExportTools => self.export_tools(),
            Message::ShowView(view) => {
                self.view = view;
                self.refresh_view();
            }
            Message::ShowCommand => self.show_command(),
            Message::Query => self.run_query(),
            Message::Compare => self.run_compare(),
            Message::Align => self.run_align(),
            Message::ModuleFilterChanged(value) => self.module_filter = value,
            Message::ProfileNameChanged(value) => self.profile_name = value,
            Message::ToggleModule(id) => self.toggle_module(&id),
            Message::SetAllModules(kind, on) => self.set_all_modules(kind, on),
            Message::ApplyProfile(name) => self.apply_profile(&name),
            Message::SaveProfile => self.save_profile(),
            Message::DeleteProfile => self.delete_profile(),
        }
    }

    fn view(&self, _input: &Startup, context: &mut ViewContext<Self>) -> View {
        context.window_title(format!("vec4ipa Workbench — {} D", self.engine.ndim()));
        let mut visuals = WindowVisuals::new()
            .theme(self.theme.window_theme())
            .backdrop(WindowBackdrop::Mica)
            .icon(concat!(env!("CARGO_MANIFEST_DIR"), "/../vec_ipa.ico"));
        if !self.window_size_seen {
            visuals = visuals.client_size(self.window_width, self.window_height);
        }
        context.window_visuals(visuals);
        context.on_window_size(context.callback(Message::WindowSize));

        let metrics = self.metrics();
        let title_bar = TitleBar::new()
            .title("vec4ipa Workbench")
            .subtitle(format!(
                "{} · {} D · {}",
                self.status,
                self.engine.ndim(),
                self.engine.version()
            ))
            .grid_row(0);

        let mut toolbar_items = vec![
            Button::new()
                .on_click(context.message(Message::ThemeCycle))
                .content(self.theme.label(self.lang.is_zh())),
            Button::new()
                .on_click(context.message(Message::LanguageToggle))
                .content(if self.lang.is_zh() { "中文" } else { "EN" }),
            Button::new()
                .on_click(context.message(Message::PinToggle))
                .content(if self.always_on_top {
                    self.t("Pinned", "已置顶")
                } else {
                    self.t("Pin", "置顶")
                }),
            Button::new()
                .on_click(context.message(Message::ToggleDensity))
                .content(self.density.label(self.lang.is_zh())),
            Button::new()
                .on_click(context.message(Message::ResetLayout))
                .content(self.t("Reset layout", "重置布局")),
            Button::new()
                .on_click(context.message(Message::ToggleKeyboardMode))
                .content(self.t("Keyboard mode", "键盘模式")),
        ];
        if layout_mode(self.window_width) == LayoutMode::Wide {
            toolbar_items.push(
                Slider::new()
                    .minimum(0.25)
                    .maximum(0.75)
                    .step_frequency(0.01)
                    .value(self.split)
                    .width(180.0)
                    .on_value_changed(context.callback(Message::SplitChanged))
                    .into(),
            );
        }
        let toolbar = StackPanel::new()
            .orientation(Orientation::Horizontal)
            .spacing(metrics.control_gap)
            .grid_row(1)
            .keyed_children(keys(toolbar_items));

        let action_bar = self.action_bar(context);
        let content: View = match layout_mode(self.window_width) {
            LayoutMode::Wide => Grid::new()
                .columns([
                    GridLength::Star(self.split),
                    GridLength::Star(1.0 - self.split),
                ])
                .grid_row(3)
                .children((self.left_pane(context), self.right_pane(context))),
            LayoutMode::Narrow => {
                let pane: View = match self.narrow_pane {
                    NarrowPane::Input => self.left_pane(context),
                    NarrowPane::Output => self.output_pane(context),
                    NarrowPane::Tools => self.tools_pane(context),
                };
                Grid::new()
                    .rows([GridLength::Auto, GridLength::Star(1.0)])
                    .row_spacing(metrics.stack_gap)
                    .grid_row(3)
                    .keyed_children(keys(vec![
                        grid_row_cell(0, self.narrow_selector(context)),
                        grid_row_cell(1, pane),
                    ]))
            }
        };

        let mut root_children: Vec<View> = vec![title_bar.into()];
        root_children.extend([toolbar, action_bar, content]);
        if self.keyboard_mode {
            root_children.push(self.keyboard_overlay(context));
        } else if self.keyboard_open {
            root_children.push(self.keyboard_popup(context));
        }

        Grid::new()
            .rows([
                GridLength::Auto,
                GridLength::Auto,
                GridLength::Auto,
                GridLength::Star(1.0),
            ])
            .keyed_children(keys(root_children))
    }
}

impl Workbench {
    fn t(&self, en: &'static str, zh: &'static str) -> &'static str {
        if self.lang.is_zh() { zh } else { en }
    }

    fn left_pane(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let input = self.fixed_section(
            self.t("IPA input", "IPA 输入"),
            TextBox::new()
                .text(self.input.clone())
                .placeholder_text(self.t("Type IPA or click the keyboard", "输入 IPA 或点击软键盘"))
                .accepts_return(true)
                .text_wrapping(TextWrapping::Wrap)
                .height(metrics.input_height)
                .on_text_changed(context.callback(Message::InputChanged)),
        );
        let narrow = layout_mode(self.window_width) == LayoutMode::Narrow;
        let body = if narrow {
            Grid::new()
                .rows([GridLength::Auto, GridLength::Star(1.0)])
                .row_spacing(metrics.section_gap)
                .keyed_children(keys(vec![
                    grid_row_cell(0, input),
                    grid_row_cell(1, self.inline_output_unit()),
                ]))
        } else {
            Grid::new()
                .rows([GridLength::Auto, GridLength::Auto, GridLength::Star(1.0)])
                .row_spacing(metrics.section_gap)
                .keyed_children(keys(vec![
                    grid_row_cell(0, input),
                    grid_row_cell(
                        1,
                        self.fixed_section(
                            self.t("Soft keyboard", "软键盘"),
                            StackPanel::new()
                                .spacing(metrics.control_gap)
                                .keyed_children(keys(vec![
                                    TextBox::new()
                                        .text(self.filter.clone())
                                        .placeholder_text(self.t("Filter symbols", "筛选符号"))
                                        .on_text_changed(context.callback(Message::FilterChanged))
                                        .into(),
                                    self.horizontal(vec![self.button(
                                        self.t("Favorite filter", "收藏筛选"),
                                        context.message(Message::AddFavorite),
                                    )]),
                                ])),
                        ),
                    ),
                    ScrollViewer::new().grid_row(2).content(
                        self.stack(self.keyboard_groups(context, self.keyboard_columns())),
                    ),
                ]))
        };

        Border::new()
            .grid_column(0)
            .padding(Thickness::new(
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding / 2.0,
                metrics.pane_padding,
            ))
            .content(body)
    }

    fn inline_output_unit(&self) -> View {
        let metrics = self.metrics();
        Grid::new()
            .rows([GridLength::Auto, GridLength::Star(1.0)])
            .row_spacing(metrics.section_gap)
            .keyed_children(keys(vec![
                TextBlock::new()
                    .text(self.t("Output", "输出"))
                    .font_size(15.0)
                    .grid_row(0)
                    .into(),
                ScrollViewer::new().grid_row(1).content(
                    TextBlock::new()
                        .text(self.output.clone())
                        .text_wrapping(TextWrapping::Wrap)
                        .is_text_selection_enabled(true),
                ),
            ]))
    }

    fn keyboard_groups(&self, context: &mut ViewContext<Self>, columns: usize) -> Vec<View> {
        let metrics = self.metrics();
        let mut groups = Vec::new();
        if !self.favorites.is_empty()
            && let Some(group) = self.keyboard_group(
                KeyboardGroupSpec {
                    id: "favorites",
                    title: self.t("Favorites", "收藏"),
                    symbols: &self.favorites,
                    always: true,
                    font_size: metrics.keyboard_font,
                },
                context,
                columns,
            )
        {
            groups.push(group);
        }
        if !self.recent.is_empty()
            && let Some(group) = self.keyboard_group(
                KeyboardGroupSpec {
                    id: "recent",
                    title: self.t("Recent", "最近"),
                    symbols: &self.recent,
                    always: true,
                    font_size: metrics.keyboard_font,
                },
                context,
                columns,
            )
        {
            groups.push(group);
        }
        for (key, id, title_en, title_zh, symbols, font) in [
            (
                "consonants",
                "kb_consonants",
                "Consonants",
                "辅音",
                &self.keyboard.consonants,
                metrics.keyboard_font,
            ),
            (
                "nonpulmonic",
                "kb_nonpulmonic",
                "Non-pulmonic",
                "非肺气流",
                &self.keyboard.non_pulmonic,
                metrics.keyboard_font,
            ),
            (
                "vowels",
                "kb_vowels",
                "Vowels",
                "元音",
                &self.keyboard.vowels,
                metrics.keyboard_font,
            ),
            (
                "diacritics",
                "kb_modifiers",
                "Diacritics",
                "附加符",
                &self.keyboard.diacritics,
                20.0,
            ),
            (
                "letters",
                "kb_letters",
                "Letters",
                "字母",
                &self.keyboard.letters,
                metrics.keyboard_font,
            ),
            (
                "tones",
                "kb_tones",
                "Tones",
                "声调",
                &self.keyboard.tones,
                metrics.keyboard_font,
            ),
        ] {
            if !self.keyboard_module_enabled(key) {
                continue;
            }
            if let Some(group) = self.keyboard_group(
                KeyboardGroupSpec {
                    id,
                    title: self.t(title_en, title_zh),
                    symbols,
                    always: false,
                    font_size: font,
                },
                context,
                columns,
            ) {
                groups.push(group);
            }
        }
        groups
    }

    fn keyboard_popup(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let width = (self.window_width - 80.0).clamp(320.0, 760.0);
        let height = (self.window_height - 120.0).clamp(260.0, 620.0);
        let columns = keyboard_columns(width - 48.0, &metrics);

        let mut title_items: Vec<View> = Vec::new();
        if let Some(icon) = app_icon_view(20.0) {
            title_items.push(icon.into());
        }
        title_items.push(
            TextBlock::new()
                .text(self.t("Soft keyboard", "软键盘"))
                .font_size(16.0)
                .vertical_alignment(VerticalAlignment::Center)
                .into(),
        );
        let title_row = StackPanel::new()
            .orientation(Orientation::Horizontal)
            .spacing(6.0)
            .vertical_alignment(VerticalAlignment::Center)
            .keyed_children(keys(title_items));

        let header = Grid::new()
            .columns([GridLength::Star(1.0), GridLength::Auto])
            .column_spacing(metrics.control_gap)
            .grid_row(0)
            .children((
                title_row,
                Button::new()
                    .on_click(context.message(Message::CloseKeyboard))
                    .min_height(metrics.control_height)
                    .grid_column(1)
                    .content(self.t("Close", "关闭")),
            ));

        let filter = Grid::new()
            .columns([GridLength::Star(1.0), GridLength::Auto])
            .column_spacing(metrics.control_gap)
            .grid_row(1)
            .children((
                TextBox::new()
                    .text(self.filter.clone())
                    .placeholder_text(self.t("Filter symbols", "筛选符号"))
                    .on_text_changed(context.callback(Message::FilterChanged))
                    .grid_column(0),
                Button::new()
                    .on_click(context.message(Message::AddFavorite))
                    .min_height(metrics.control_height)
                    .grid_column(1)
                    .content(self.t("Favorite filter", "收藏筛选")),
            ));

        let body = Grid::new()
            .rows([GridLength::Auto, GridLength::Auto, GridLength::Star(1.0)])
            .row_spacing(metrics.section_gap)
            .keyed_children(keys(vec![
                header,
                filter,
                ScrollViewer::new()
                    .grid_row(2)
                    .content(self.stack(self.keyboard_groups(context, columns))),
            ]));

        let card = Border::new()
            .width(width)
            .height(height)
            .padding(Thickness::new(12.0, 12.0, 12.0, 12.0))
            .corner_radius(8.0)
            .background(ThemeBrush::SolidBackground)
            .border_brush(ThemeBrush::CardStroke)
            .border_thickness(Thickness::new(1.0, 1.0, 1.0, 1.0))
            .horizontal_alignment(HorizontalAlignment::Center)
            .vertical_alignment(VerticalAlignment::Center)
            .content(body);

        Grid::new()
            .grid_row(0)
            .grid_row_span(4)
            .background(Brush::Solid(Color::argb(140, 0, 0, 0)))
            .children([card])
    }

    fn action_bar(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let primary = vec![
            self.button(self.t("Convert", "转换"), context.message(Message::Convert)),
            self.button(self.t("Loop", "回环"), context.message(Message::Loop)),
            self.button(self.t("Clear", "清空"), context.message(Message::Clear)),
            self.button(self.t("Reverse", "反向"), context.message(Message::Reverse)),
        ];
        let mut modes = Vec::new();
        for format in [OutputFormat::Vectors, OutputFormat::Ir, OutputFormat::Json] {
            let label = if self.format == format {
                format!("[{}]", format.label())
            } else {
                format.label().to_string()
            };
            modes.push(self.button(&label, context.message(Message::SetFormat(format))));
        }
        for level in 0..=4u8 {
            let label = if self.narrowness == level {
                format!("[{level}]")
            } else {
                level.to_string()
            };
            modes.push(self.button(&label, context.message(Message::SetNarrowness(level))));
        }
        match layout_mode(self.window_width) {
            LayoutMode::Wide => {
                let mut items = primary;
                items.extend(modes);
                StackPanel::new()
                    .orientation(Orientation::Horizontal)
                    .spacing(metrics.control_gap)
                    .grid_row(2)
                    .keyed_children(keys(items))
            }
            LayoutMode::Narrow => {
                let mut items = primary;
                items.push(self.button(
                    self.t("Keyboard", "软键盘"),
                    context.message(Message::OpenKeyboard),
                ));
                StackPanel::new()
                    .spacing(metrics.control_gap)
                    .grid_row(2)
                    .keyed_children(keys(vec![
                        StackPanel::new()
                            .orientation(Orientation::Horizontal)
                            .spacing(metrics.control_gap)
                            .keyed_children(keys(items)),
                        StackPanel::new()
                            .orientation(Orientation::Horizontal)
                            .spacing(metrics.control_gap)
                            .keyed_children(keys(modes)),
                    ]))
            }
        }
    }

    fn keyboard_columns(&self) -> usize {
        let metrics = self.metrics();
        let available = match layout_mode(self.window_width) {
            LayoutMode::Wide => self.window_width * self.split - metrics.pane_padding * 1.5,
            LayoutMode::Narrow => self.window_width - metrics.pane_padding * 2.0,
        };
        keyboard_columns(available - 20.0, &metrics)
    }

    fn narrow_selector(&self, context: &mut ViewContext<Self>) -> View {
        let mut items = Vec::new();
        for pane in [NarrowPane::Input, NarrowPane::Output, NarrowPane::Tools] {
            let label = if self.narrow_pane == pane {
                format!("[{}]", pane.label(self.lang.is_zh()))
            } else {
                pane.label(self.lang.is_zh()).to_string()
            };
            items.push(self.button(&label, context.message(Message::SetNarrowPane(pane))));
        }
        self.horizontal(items)
    }

    fn output_pane(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let mut children = Vec::new();
        for (row, unit) in self.output_content(context).into_iter().enumerate() {
            children.push(grid_row_cell(row as i32, unit));
        }
        children.push(grid_row_cell(3, View::empty()));
        children.push(
            TextBlock::new()
                .text(self.status.clone())
                .font_size(12.0)
                .grid_row(4)
                .into(),
        );
        Border::new()
            .padding(Thickness::new(
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
            ))
            .content(
                Grid::new()
                    .rows([
                        GridLength::Auto,
                        GridLength::Auto,
                        GridLength::Auto,
                        GridLength::Star(1.0),
                        GridLength::Auto,
                    ])
                    .row_spacing(metrics.section_gap)
                    .keyed_children(keys(children)),
            )
    }

    fn tools_pane(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let tools = ScrollViewer::new()
            .grid_row(0)
            .content(self.stack(self.tools_content(context)));
        let status = TextBlock::new()
            .text(self.status.clone())
            .font_size(12.0)
            .grid_row(1);
        Border::new()
            .padding(Thickness::new(
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
            ))
            .content(
                Grid::new()
                    .rows([GridLength::Star(1.0), GridLength::Auto])
                    .row_spacing(metrics.section_gap)
                    .children((tools, status)),
            )
    }

    fn right_pane(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let mut children = Vec::new();
        for (row, unit) in self.output_content(context).into_iter().enumerate() {
            children.push(grid_row_cell(row as i32, unit));
        }
        children.push(
            ScrollViewer::new()
                .grid_row(3)
                .content(self.stack(self.tools_content(context))),
        );
        children.push(
            TextBlock::new()
                .text(self.status.clone())
                .font_size(12.0)
                .grid_row(4)
                .into(),
        );
        Border::new()
            .grid_column(1)
            .padding(Thickness::new(
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
            ))
            .content(
                Grid::new()
                    .rows([
                        GridLength::Auto,
                        GridLength::Auto,
                        GridLength::Auto,
                        GridLength::Star(1.0),
                        GridLength::Auto,
                    ])
                    .row_spacing(metrics.section_gap)
                    .keyed_children(keys(children)),
            )
    }

    fn output_content(&self, context: &mut ViewContext<Self>) -> Vec<View> {
        let metrics = self.metrics();
        vec![
            self.fixed_section(
                self.t("Output", "输出"),
                ScrollViewer::new().height(metrics.output_height).content(
                    TextBlock::new()
                        .text(self.output.clone())
                        .text_wrapping(TextWrapping::Wrap)
                        .is_text_selection_enabled(true),
                ),
            ),
            self.fixed_section(
                self.t("Vector → IPA", "向量 → IPA"),
                TextBox::new()
                    .text(self.reverse_input.clone())
                    .placeholder_text(self.t(
                        "One vector row per line (comma or space separated)",
                        "每行一个向量（逗号或空格分隔）",
                    ))
                    .accepts_return(true)
                    .text_wrapping(TextWrapping::Wrap)
                    .height(metrics.input_height * 0.75)
                    .on_text_changed(context.callback(Message::ReverseChanged)),
            ),
            self.fixed_section(
                self.t("View output", "视图输出"),
                ScrollViewer::new().height(metrics.view_height).content(
                    TextBlock::new()
                        .text(self.view_text.clone())
                        .text_wrapping(TextWrapping::Wrap)
                        .is_text_selection_enabled(true),
                ),
            ),
        ]
    }

    fn tools_content(&self, context: &mut ViewContext<Self>) -> Vec<View> {
        let mut children = Vec::new();
        let narrow = layout_mode(self.window_width) == LayoutMode::Narrow;
        let per_row = if narrow { 4 } else { 9 };

        let view_buttons = vec![
            self.button(
                self.t("Table", "总表"),
                context.message(Message::ShowView(ViewKind::Table)),
            ),
            self.button(
                self.t("Modules", "模块"),
                context.message(Message::ShowView(ViewKind::Modules)),
            ),
            self.button(
                self.t("Stats", "统计"),
                context.message(Message::ShowView(ViewKind::Stats)),
            ),
            self.button(
                self.t("Weights", "权重"),
                context.message(Message::ShowView(ViewKind::Weights)),
            ),
            self.button(
                self.t("Effective", "生效权重"),
                context.message(Message::ShowView(ViewKind::Effective)),
            ),
            self.button(
                self.t("Axes", "维度"),
                context.message(Message::ShowView(ViewKind::Dimensions)),
            ),
            self.button(
                self.t("Docs", "文档"),
                context.message(Message::ShowView(ViewKind::Docs)),
            ),
        ];
        children.push(self.section(
            context,
            "views",
            self.t("Views", "视图"),
            None,
            self.button_rows(view_buttons, per_row),
        ));

        children.push(self.module_manager(context, per_row));

        children.push(
            self.section(
                context,
                "symbol_tools",
                self.t("Symbol tools", "符号工具"),
                None,
                StackPanel::new()
                    .spacing(self.metrics().control_gap)
                    .children((
                        self.horizontal(vec![
                            TextBox::new()
                                .text(self.query.clone())
                                .placeholder_text(self.t("Query symbol", "查询符号"))
                                .on_text_changed(context.callback(Message::QueryChanged))
                                .into(),
                            self.button(self.t("Query", "查询"), context.message(Message::Query)),
                        ]),
                        self.horizontal(vec![
                            TextBox::new()
                                .text(self.compare_a.clone())
                                .on_text_changed(context.callback(Message::CompareA))
                                .into(),
                            TextBox::new()
                                .text(self.compare_b.clone())
                                .on_text_changed(context.callback(Message::CompareB))
                                .into(),
                            self.button(
                                self.t("Compare", "比较"),
                                context.message(Message::Compare),
                            ),
                        ]),
                        self.horizontal(vec![
                            TextBox::new()
                                .text(self.align_a.clone())
                                .on_text_changed(context.callback(Message::AlignA))
                                .into(),
                            TextBox::new()
                                .text(self.align_b.clone())
                                .on_text_changed(context.callback(Message::AlignB))
                                .into(),
                            self.button(self.t("Align", "对齐"), context.message(Message::Align)),
                        ]),
                    )),
            ),
        );

        children.push(
            self.section(
                context,
                "files",
                self.t("Files and exports", "文件与导出"),
                None,
                StackPanel::new()
                    .spacing(self.metrics().control_gap)
                    .children((
                        self.button_rows(
                            vec![
                                self.button(
                                    self.t("Open IPA file", "打开 IPA 文件"),
                                    context.message(Message::OpenIpaFile),
                                ),
                                self.button(
                                    self.t("Save output", "保存输出"),
                                    context.message(Message::SaveOutput),
                                ),
                                self.button(
                                    self.t("Export CSV", "导出 CSV"),
                                    context.message(Message::ExportCsv),
                                ),
                                self.button(
                                    self.t("Export IR", "导出 IR"),
                                    context.message(Message::ExportIr),
                                ),
                            ],
                            per_row,
                        ),
                        self.button_rows(
                            vec![
                                self.button(
                                    self.t("Load scheme", "加载方案"),
                                    context.message(Message::LoadScheme),
                                ),
                                self.button(
                                    self.t("Load metric", "加载度量"),
                                    context.message(Message::LoadMetric),
                                ),
                                self.button(
                                    self.t("Export tools", "导出工具"),
                                    context.message(Message::ExportTools),
                                ),
                                self.button(
                                    self.t("Show command", "显示命令"),
                                    context.message(Message::ShowCommand),
                                ),
                            ],
                            per_row,
                        ),
                    )),
            ),
        );

        let mut history_buttons = Vec::new();
        for (index, entry) in self.history.iter().take(8).enumerate() {
            history_buttons.push(self.button(
                &format!("{} → {}", entry.label, preview(&entry.output, 40)),
                context.callback(move |_| Message::HistorySelect(index)),
            ));
        }
        history_buttons.push(self.button(
            self.t("Clear history", "清除历史"),
            context.message(Message::ClearHistory),
        ));
        children.push(self.section(
            context,
            "history",
            self.t("History", "历史"),
            Some(self.history.len()),
            self.stack(history_buttons),
        ));

        let mut examples = Vec::new();
        for (index, example) in EXAMPLES.iter().enumerate() {
            examples.push(self.button(example, context.callback(move |_| Message::Example(index))));
        }
        children.push(self.section(
            context,
            "examples",
            self.t("Examples", "示例"),
            Some(examples.len()),
            self.button_rows(examples, per_row),
        ));

        children
    }

    fn module_manager(&self, context: &mut ViewContext<Self>, per_row: usize) -> View {
        let metrics = self.metrics();
        let zh = self.lang.is_zh();
        let filter = self.module_filter.trim().to_lowercase();
        let mut blocks: Vec<View> = Vec::new();

        blocks.push(
            TextBox::new()
                .text(self.module_filter.clone())
                .placeholder_text(self.t("Filter modules", "筛选模块"))
                .on_text_changed(context.callback(Message::ModuleFilterChanged))
                .into(),
        );

        let profile_columns = (per_row / 2).max(2);
        let mut profile_buttons = Vec::new();
        for name in self.profile_names() {
            let label = if self.active_profile == name {
                format!("[{name}]")
            } else {
                name.clone()
            };
            profile_buttons.push(self.button(
                &label,
                context.callback({
                    let name = name.clone();
                    move |_| Message::ApplyProfile(name.clone())
                }),
            ));
        }
        blocks.push(
            TextBlock::new()
                .text(format!(
                    "{}: {}",
                    self.t("Profile", "配置档案"),
                    self.active_profile
                ))
                .font_size(13.0)
                .into(),
        );
        blocks.push(self.button_rows(profile_buttons, profile_columns));
        blocks.push(self.horizontal(vec![
            TextBox::new()
                .text(self.profile_name.clone())
                .placeholder_text(self.t("Profile name", "档案名称"))
                .on_text_changed(context.callback(Message::ProfileNameChanged))
                .into(),
            self.button(
                self.t("Save current", "保存当前"),
                context.message(Message::SaveProfile),
            ),
            self.button(
                self.t("Delete active", "删除当前"),
                context.message(Message::DeleteProfile),
            ),
        ]));

        for kind in [ModuleKind::Parser, ModuleKind::Keyboard] {
            let visible = self
                .modules
                .of_kind(kind)
                .filter(|module| module.matches(&filter))
                .collect::<Vec<_>>();
            if visible.is_empty() {
                continue;
            }
            let enabled = self.enabled_for(kind);
            let header = TextBlock::new()
                .text(format!(
                    "{} ({}/{})",
                    kind.label(zh),
                    enabled.len(),
                    self.modules.optional_ids(kind).len()
                ))
                .font_size(15.0);
            let bulk = self.button_rows(
                vec![
                    self.button(
                        self.t("All on", "全部启用"),
                        context.callback(move |_| Message::SetAllModules(kind, true)),
                    ),
                    self.button(
                        self.t("All off", "全部禁用"),
                        context.callback(move |_| Message::SetAllModules(kind, false)),
                    ),
                ],
                2,
            );
            let mut rows = Vec::new();
            for module in visible {
                let is_on = enabled.contains(&module.id);
                let label = if module.always_on {
                    format!("{} · {}", module.label(zh), self.t("always on", "始终启用"))
                } else if is_on {
                    format!("[{}]", module.label(zh))
                } else {
                    module.label(zh).to_string()
                };
                let control: View = if module.always_on {
                    Button::new()
                        .is_enabled(false)
                        .min_height(metrics.control_height)
                        .content(label)
                } else {
                    self.button(
                        &label,
                        context.callback({
                            let id = module.id.clone();
                            move |_| Message::ToggleModule(id.clone())
                        }),
                    )
                };
                let info = TextBlock::new()
                    .text(format!(
                        "{} · {} {}",
                        module.description(zh),
                        module.count,
                        self.t("symbols", "个符号")
                    ))
                    .font_size(12.0)
                    .text_wrapping(TextWrapping::Wrap);
                rows.push(
                    Grid::new()
                        .columns([GridLength::Auto, GridLength::Star(1.0)])
                        .column_spacing(metrics.control_gap)
                        .keyed_children(keys(vec![control, info.grid_column(1).into()])),
                );
            }
            blocks.push(self.stack(vec![header.into(), bulk, self.stack(rows)]));
        }

        let parser_total = self.modules.optional_ids(ModuleKind::Parser).len();
        let keyboard_total = self.modules.optional_ids(ModuleKind::Keyboard).len();
        let enabled_total = self.enabled_parser.len() + self.enabled_keyboard.len();
        let symbols = self.enabled_symbols();
        blocks.push(
            TextBlock::new()
                .text(format!(
                    "{}: {}/{} · {}: {}/{} · {}: {}",
                    self.t("Parser", "解析"),
                    self.enabled_parser.len(),
                    parser_total,
                    self.t("Keyboard", "键盘"),
                    self.enabled_keyboard.len(),
                    keyboard_total,
                    self.t("Symbols", "符号"),
                    symbols
                ))
                .font_size(12.0)
                .into(),
        );

        self.section(
            context,
            "modules",
            self.t("Module manager", "模块管理器"),
            Some(enabled_total),
            self.stack(blocks),
        )
    }

    fn metrics(&self) -> LayoutMetrics {
        LayoutMetrics::for_density(self.density)
    }

    fn fixed_section(&self, title: &'static str, content: impl Into<View>) -> View {
        StackPanel::new()
            .spacing(self.metrics().section_gap)
            .children((TextBlock::new().text(title).font_size(15.0), content.into()))
    }

    fn section(
        &self,
        context: &mut ViewContext<Self>,
        id: &'static str,
        title: &'static str,
        count: Option<usize>,
        content: impl Into<View>,
    ) -> View {
        self.section_with_force(context, id, title, count, false, content)
    }

    fn section_with_force(
        &self,
        context: &mut ViewContext<Self>,
        id: &'static str,
        title: &'static str,
        count: Option<usize>,
        force_open: bool,
        content: impl Into<View>,
    ) -> View {
        let metrics = self.metrics();
        let expanded = force_open || !is_collapsed(&self.collapsed_sections, id);
        let glyph = if expanded { "▾" } else { "▸" };
        let mut label = format!("{glyph} {title}");
        if let Some(count) = count {
            label.push_str(&format!(" ({count})"));
        }
        let toggle = context.callback({
            let id = id.to_string();
            move |_| Message::ToggleSection(id.clone())
        });
        let header = Button::new()
            .on_click(toggle)
            .min_height(metrics.control_height)
            .content(label);
        let mut children = vec![header];
        if expanded {
            children.push(content.into());
        }
        StackPanel::new()
            .spacing(metrics.section_gap)
            .keyed_children(keys(children))
    }

    fn stack(&self, children: Vec<View>) -> View {
        StackPanel::new()
            .spacing(self.metrics().stack_gap)
            .keyed_children(keys(children))
    }

    fn horizontal(&self, children: Vec<View>) -> View {
        StackPanel::new()
            .orientation(Orientation::Horizontal)
            .spacing(self.metrics().control_gap)
            .keyed_children(keys(children))
    }

    fn button_rows(&self, buttons: Vec<View>, per_row: usize) -> View {
        let per_row = per_row.max(1);
        let mut rows: Vec<View> = Vec::new();
        let mut current: Vec<View> = Vec::new();
        for button in buttons {
            current.push(button);
            if current.len() == per_row {
                rows.push(self.horizontal(std::mem::take(&mut current)));
            }
        }
        if !current.is_empty() {
            rows.push(self.horizontal(current));
        }
        self.stack(rows)
    }

    fn button(&self, label: &str, callback: impl IntoUnitCallback) -> View {
        Button::new()
            .on_click(callback)
            .min_height(self.metrics().control_height)
            .content(label)
    }

    /// Hover card for a keyboard key: the glyph, its feature name, and the
    /// airstream or tier line, matching the WinUI reference workbench.
    fn symbol_tooltip(&self, symbol: &str) -> Tooltip {
        let raw = self.engine.query(symbol).unwrap_or_default();
        let (name, air) = describe_query(&raw);
        let mut items: Vec<View> = vec![
            TextBlock::new()
                .text(symbol.to_string())
                .font_size(26.0)
                .into(),
        ];
        if !name.is_empty() {
            items.push(
                TextBlock::new()
                    .text(name)
                    .font_size(13.0)
                    .text_wrapping(TextWrapping::Wrap)
                    .max_width(320.0)
                    .into(),
            );
        }
        if !air.is_empty() {
            items.push(
                TextBlock::new()
                    .text(air)
                    .font_size(12.0)
                    .text_wrapping(TextWrapping::Wrap)
                    .max_width(320.0)
                    .into(),
            );
        }
        Tooltip::rich(StackPanel::new().spacing(2.0).keyed_children(keys(items)))
            .placement(TooltipPlacement::Mouse)
    }

    fn keyboard_group(
        &self,
        spec: KeyboardGroupSpec,
        context: &mut ViewContext<Self>,
        columns: usize,
    ) -> Option<View> {
        let metrics = self.metrics();
        let filter = self.filter.trim().to_lowercase();
        let filtered = spec
            .symbols
            .iter()
            .filter(|symbol| filter.is_empty() || self.symbol_matches(symbol, &filter))
            .cloned()
            .collect::<Vec<_>>();
        if filtered.is_empty() && !spec.always {
            return None;
        }

        let mut rows = Vec::new();
        for chunk in filtered.chunks(columns) {
            let mut buttons = Vec::new();
            for symbol in chunk {
                let symbol = symbol.clone();
                let click_symbol = symbol.clone();
                let tooltip = self.symbol_tooltip(&symbol);
                let label = TextBlock::new()
                    .text(symbol)
                    .font_size(spec.font_size)
                    .text_wrapping(TextWrapping::NoWrap)
                    .horizontal_alignment(HorizontalAlignment::Center)
                    .vertical_alignment(VerticalAlignment::Center);
                buttons.push(
                    Button::new()
                        .on_click(context.callback(move |_| Message::Symbol(click_symbol.clone())))
                        .width(metrics.keyboard_width)
                        .height(metrics.keyboard_height)
                        .horizontal_content_alignment(HorizontalAlignment::Center)
                        .vertical_content_alignment(VerticalAlignment::Center)
                        .resource_overrides(
                            ResourceOverrides::new()
                                .set("ButtonPadding", Thickness::new(0.0, 0.0, 0.0, 0.0)),
                        )
                        .content(label)
                        .tooltip_with(tooltip),
                );
            }
            rows.push(
                StackPanel::new()
                    .orientation(Orientation::Horizontal)
                    .spacing(metrics.control_gap)
                    .keyed_children(keys(buttons)),
            );
        }
        let body = StackPanel::new()
            .spacing(metrics.control_gap)
            .keyed_children(keys(rows));
        Some(self.section_with_force(
            context,
            spec.id,
            spec.title,
            Some(filtered.len()),
            !filter.is_empty(),
            body,
        ))
    }

    fn keyboard_overlay(&self, context: &mut ViewContext<Self>) -> View {
        Grid::new()
            .grid_row(1)
            .grid_row_span(3)
            .background(ThemeBrush::SolidBackground)
            .children([self.keyboard_panel(context)])
    }

    fn keyboard_panel(&self, context: &mut ViewContext<Self>) -> View {
        let metrics = self.metrics();
        let columns = keyboard_columns(self.window_width - 48.0, &metrics);

        let title = TextBlock::new()
            .text(self.t("IPA keyboard", "IPA 软键盘"))
            .font_size(16.0)
            .vertical_alignment(VerticalAlignment::Center);
        let exit = Button::new()
            .on_click(context.message(Message::ToggleKeyboardMode))
            .min_height(metrics.control_height)
            .grid_column(1)
            .content(self.t("Exit", "退出"));
        let header = Grid::new()
            .columns([GridLength::Star(1.0), GridLength::Auto])
            .column_spacing(metrics.control_gap)
            .children((title, exit));

        let body = Grid::new()
            .rows([GridLength::Auto, GridLength::Star(1.0), GridLength::Auto])
            .row_spacing(metrics.section_gap)
            .keyed_children(keys(vec![
                grid_row_cell(0, header),
                grid_row_cell(
                    1,
                    ScrollViewer::new().content(self.stack(self.keyboard_groups(context, columns))),
                ),
                grid_row_cell(
                    2,
                    TextBlock::new()
                        .text(self.status.clone())
                        .font_size(12.0)
                        .into(),
                ),
            ]));

        Border::new()
            .padding(Thickness::new(
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
                metrics.pane_padding,
            ))
            .content(body)
    }

    fn toggle_keyboard_mode(&mut self) {
        if self.keyboard_mode {
            self.leave_keyboard_mode();
        } else {
            self.enter_keyboard_mode();
        }
    }

    fn enter_keyboard_mode(&mut self) {
        let Some(hwnd) = win32::foreground_window() else {
            self.status = self
                .t("No active window handle", "无法获取活动窗口")
                .to_string();
            return;
        };
        self.window_handle = hwnd;
        win32::set_no_activate(hwnd, true);
        win32::set_topmost(hwnd, true);
        self.keyboard_open = false;
        self.keyboard_mode = true;
        self.status = self
            .t(
                "Click the target application, then pick symbols",
                "先点目标程序，再点符号",
            )
            .to_string();
    }

    fn leave_keyboard_mode(&mut self) {
        if self.window_handle != 0 {
            win32::set_no_activate(self.window_handle, false);
            win32::set_topmost(self.window_handle, self.always_on_top);
            win32::set_foreground(self.window_handle);
        }
        self.keyboard_mode = false;
        self.status = self.t("keyboard mode off", "已退出键盘模式").to_string();
    }

    fn send_symbol(&mut self, symbol: &str) {
        let symbol = symbol.replace('\u{25cc}', "");
        if symbol.is_empty() {
            return;
        }
        let foreground = win32::foreground_window();
        if foreground.is_none() || foreground == Some(self.window_handle) {
            self.status = self
                .t("Click the target application first", "请先点击目标程序")
                .to_string();
            return;
        }
        match crate::input::inject(&symbol) {
            crate::input::Delivery::Sent => {
                self.status = format!("{} {symbol}", self.t("sent", "已发送"));
            }
            crate::input::Delivery::Clipboard => {
                self.status = format!("{} {symbol} (clipboard)", self.t("sent", "已发送"));
            }
            crate::input::Delivery::Failed(error) => self.status = error,
        }
    }

    fn symbol_matches(&self, symbol: &str, filter: &str) -> bool {
        let search = self.keyboard.search.get(symbol).map(String::as_str);
        if search.is_some() {
            return keyboard::matches(symbol, search, filter);
        }
        let computed = search_text(&self.engine, symbol);
        keyboard::matches(symbol, Some(&computed), filter)
    }

    fn append_symbol(&mut self, symbol: &str) {
        let symbol = symbol.replace('\u{25cc}', "");
        if symbol.is_empty() {
            return;
        }
        if is_modifier_symbol(&symbol) && self.input.trim().is_empty() {
            self.status = self
                .t(
                    "Pick a base segment before a combining mark",
                    "请先选择基段再输入附加符",
                )
                .to_string();
            return;
        }
        self.input.push_str(&symbol);
        self.recent.retain(|item| item != &symbol);
        self.recent.insert(0, symbol);
        self.recent.truncate(16);
        self.convert_forward();
    }

    fn add_favorite(&mut self) {
        let value = if !self.filter.trim().is_empty() {
            self.filter.trim().to_string()
        } else {
            self.query.trim().to_string()
        };
        if value.is_empty() {
            self.status = self
                .t("Nothing to favorite", "没有可收藏的符号")
                .to_string();
            return;
        }
        if !self.favorites.contains(&value) {
            self.favorites.insert(0, value);
        }
        self.favorites = crate::favorites::normalize(std::mem::take(&mut self.favorites));
        if let Some(path) = crate::favorites::path()
            && let Err(error) = crate::favorites::save_to(&path, &self.favorites)
        {
            self.status = error;
        }
    }

    fn convert_forward(&mut self) {
        if self.input.trim().is_empty() {
            self.status = self
                .t("Type or click an IPA symbol", "请输入或点击 IPA 符号")
                .to_string();
            return;
        }
        match self.format {
            OutputFormat::Vectors => match self.engine.forward(&self.input) {
                Ok(mut segments) => {
                    if let Ok(toned) = self.engine.forward_with_tone(&self.input) {
                        for (segment, toned) in segments.iter_mut().zip(toned) {
                            segment.tones = toned.tones;
                        }
                    }
                    self.output = segments
                        .iter()
                        .enumerate()
                        .map(|(index, segment)| format_segment(index, segment))
                        .collect::<Vec<_>>()
                        .join("\n");
                    self.record_history();
                }
                Err(error) => {
                    self.output = format!("parse error: {error}");
                    self.status = error;
                }
            },
            OutputFormat::Ir => {
                self.output = self.engine.ir(&self.input);
                self.record_history();
            }
            OutputFormat::Json => {
                self.output = self.engine.json(&self.input);
                self.record_history();
            }
        }
    }

    fn convert_reverse(&mut self) {
        if self.reverse_input.trim().is_empty() {
            self.status = self.t("Enter a vector row", "请输入向量").to_string();
            return;
        }
        let width = self.engine.ndim();
        let mut lines = Vec::new();
        let mut errors = Vec::new();
        for (index, line) in self.reverse_input.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            match parse_vector(line, width) {
                Ok(vector) => match self.engine.reverse(&vector) {
                    Ok(text) => lines.push(format!("[{index}] {text}")),
                    Err(error) => errors.push(format!("[{index}] {error}")),
                },
                Err(error) => errors.push(format!("[{index}] {error}")),
            }
        }
        self.output = lines
            .into_iter()
            .chain(errors)
            .collect::<Vec<_>>()
            .join("\n");
        self.record_history_reverse();
    }

    fn run_loop(&mut self) {
        if self.input.trim().is_empty() {
            self.status = self.t("Nothing to loop", "没有可回环的输入").to_string();
            return;
        }
        match self.engine.forward_with_tone(&self.input) {
            Ok(segments) => {
                let mut lines = Vec::new();
                for (index, segment) in segments.iter().enumerate() {
                    let vector = segment
                        .values
                        .iter()
                        .map(|value| format!("{value:.4}"))
                        .collect::<Vec<_>>()
                        .join(",");
                    let tone = tone_annotation(&segment.tones);
                    let mut line = format!("[{index}] vector: ({vector})");
                    if !tone.is_empty() {
                        line.push_str(&format!("  tone={tone}"));
                    }
                    match self.engine.reverse(&segment.values) {
                        Ok(fit) => {
                            line.push_str(&format!("\n    fit:   {fit}"));
                            if !tone.is_empty() {
                                line.push_str(&format!("  tone={tone}"));
                            }
                        }
                        Err(error) => line.push_str(&format!("\n    fit:   error: {error}")),
                    }
                    lines.push(line);
                }
                self.output = lines.join("\n");
                self.record_history();
            }
            Err(error) => {
                self.output = format!("parse error: {error}");
                self.status = error;
            }
        }
    }

    fn run_query(&mut self) {
        match self.engine.query(&self.query) {
            Ok(text) => {
                self.output = text;
                self.status = self.t("query done", "查询完成").to_string();
            }
            Err(error) => self.status = error,
        }
    }

    fn run_compare(&mut self) {
        match self.engine.distance(&self.compare_a, &self.compare_b) {
            Ok(distance) => {
                self.output = format!(
                    "{}: {}\n{}: {}\nd = {distance:.4}",
                    self.t("A", "A"),
                    self.engine.query(&self.compare_a).unwrap_or_default(),
                    self.t("B", "B"),
                    self.engine.query(&self.compare_b).unwrap_or_default()
                );
            }
            Err(error) => self.output = error,
        }
    }

    fn run_align(&mut self) {
        match self.engine.align(&self.align_a, &self.align_b) {
            Ok(text) => self.output = text,
            Err(error) => self.output = error,
        }
    }

    fn refresh_view(&mut self) {
        self.view_text = match self.view {
            ViewKind::None => String::new(),
            ViewKind::Table => self.engine.table(),
            ViewKind::Modules => self.engine.modules_full(),
            ViewKind::Stats => self.engine.stats(),
            ViewKind::Weights => self.engine.weights_effective(),
            ViewKind::Effective => self.engine.weights_effective(),
            ViewKind::Dimensions => self.engine.dim_names().join("\n"),
            ViewKind::Docs => self.engine.docs(),
        };
    }

    fn show_command(&mut self) {
        let input = if self.input.trim().is_empty() {
            "<IPA>"
        } else {
            &self.input
        };
        let forward = match self.format {
            OutputFormat::Vectors => format!("ipa2vec \"{input}\""),
            OutputFormat::Ir => format!("ipa2vec -L \"{input}\""),
            OutputFormat::Json => format!("ipa2vec -j \"{input}\""),
        };
        let mut command = forward;
        if !self.reverse_input.trim().is_empty() {
            command.push_str(&format!(
                "\nvec2ipa -N {} \"{}\"",
                self.narrowness, self.reverse_input
            ));
        }
        self.output = command;
        self.status = self
            .t("command line for the current input", "当前输入的命令行")
            .to_string();
    }

    fn load_scheme(&mut self) {
        let Some(path) = FileDialog::new()
            .add_filter("Scheme", &["scheme"])
            .pick_file()
        else {
            return;
        };
        let path = path.to_string_lossy().to_string();
        if let Err(error) = self.engine.set_args(&["-D", &path]) {
            self.status = error;
            return;
        }
        self.settings.scheme = Some(path);
        self.settings.save();
        self.reload_keyboard();
        self.status = format!("loaded scheme: {} D", self.engine.ndim());
    }

    fn load_metric(&mut self) {
        let Some(path) = FileDialog::new()
            .add_filter("Metric JSON", &["json"])
            .pick_file()
        else {
            return;
        };
        let path = path.to_string_lossy().to_string();
        match self.engine.load_metric(&path) {
            Ok(()) => {
                self.settings.metric = Some(path);
                self.settings.save();
                self.status = self.t("metric loaded", "度量已加载").to_string();
            }
            Err(error) => self.status = error,
        }
    }

    fn open_ipa_file(&mut self) {
        let Some(path) = FileDialog::new()
            .add_filter("IPA text", &["txt", "ipa"])
            .pick_file()
        else {
            return;
        };
        let Ok(text) = std::fs::read_to_string(&path) else {
            self.status = format!("could not read {}", path.display());
            return;
        };
        let mut output = Vec::new();
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            match self.engine.forward(line) {
                Ok(segments) => {
                    output.push(format!("> {line}"));
                    output.extend(
                        segments
                            .iter()
                            .enumerate()
                            .map(|(index, segment)| format_segment(index, segment)),
                    );
                }
                Err(error) => output.push(format!("> {line}\n  error: {error}")),
            }
        }
        self.output = output.join("\n");
        self.status = format!("converted {}", path.display());
    }

    fn save_output(&mut self) {
        let Some(path) = FileDialog::new()
            .set_file_name("vec4ipa-output.txt")
            .save_file()
        else {
            return;
        };
        match std::fs::write(&path, &self.output) {
            Ok(()) => self.status = format!("saved {}", path.display()),
            Err(error) => self.status = error.to_string(),
        }
    }

    fn export_csv(&mut self) {
        let Some(path) = FileDialog::new()
            .set_file_name("ipa2vec-table.csv")
            .save_file()
        else {
            return;
        };
        let table = self.engine.table();
        let mut csv = String::new();
        for line in table.lines() {
            let fields = line.split('\t').collect::<Vec<_>>();
            csv.push_str(
                &fields
                    .iter()
                    .map(|field| csv_quote(field))
                    .collect::<Vec<_>>()
                    .join(","),
            );
            csv.push('\n');
        }
        match std::fs::write(&path, csv) {
            Ok(()) => self.status = format!("saved {}", path.display()),
            Err(error) => self.status = error.to_string(),
        }
    }

    fn export_ir(&mut self) {
        let Some(path) = FileDialog::new().set_file_name("vec4ipa-ir").save_file() else {
            return;
        };
        let base = path.with_extension("").to_string_lossy().to_string();
        match self.engine.ir_export(&self.input, &base) {
            Ok(()) => self.status = format!("exported {base}.layer1/.layer2"),
            Err(error) => self.status = error,
        }
    }

    fn export_tools(&mut self) {
        let Some(directory) = FileDialog::new().pick_folder() else {
            return;
        };
        match win32::copy_tools(&directory) {
            Ok(count) => self.status = format!("exported {count} tools"),
            Err(error) => self.status = error,
        }
    }

    fn enabled_for(&self, kind: ModuleKind) -> &[String] {
        match kind {
            ModuleKind::Parser => &self.enabled_parser,
            ModuleKind::Keyboard => &self.enabled_keyboard,
        }
    }

    fn enabled_symbols(&self) -> usize {
        self.modules.symbols(&self.enabled_parser) + self.modules.symbols(&self.enabled_keyboard)
    }

    fn keyboard_module_enabled(&self, key: &str) -> bool {
        modules::keyboard_visible(&self.enabled_keyboard, key)
    }

    fn profile_names(&self) -> Vec<String> {
        let mut names = vec![PROFILE_ALL_ON.to_string(), PROFILE_ALL_OFF.to_string()];
        names.extend(
            self.settings
                .module_profiles
                .iter()
                .map(|profile| profile.name.clone()),
        );
        names
    }

    fn profile_matches(&self, name: &str) -> bool {
        if let Some(profile) = self.settings.module_profile(name) {
            return modules::selection_matches(
                &self.enabled_parser,
                &self.enabled_keyboard,
                profile,
            );
        }
        if name == PROFILE_ALL_ON {
            self.enabled_parser == self.modules.optional_ids(ModuleKind::Parser)
                && self.enabled_keyboard == self.modules.optional_ids(ModuleKind::Keyboard)
        } else if name == PROFILE_ALL_OFF {
            self.enabled_parser.is_empty() && self.enabled_keyboard.is_empty()
        } else {
            false
        }
    }

    fn detect_profile(&self) -> String {
        for profile in &self.settings.module_profiles {
            if modules::selection_matches(&self.enabled_parser, &self.enabled_keyboard, profile) {
                return profile.name.clone();
            }
        }
        if self.profile_matches(PROFILE_ALL_ON) {
            PROFILE_ALL_ON.to_string()
        } else if self.profile_matches(PROFILE_ALL_OFF) {
            PROFILE_ALL_OFF.to_string()
        } else {
            PROFILE_CUSTOM.to_string()
        }
    }

    fn toggle_module(&mut self, id: &str) {
        let Some(module) = self.modules.find(id) else {
            self.status = format!("unknown module: {id}");
            return;
        };
        if module.always_on {
            self.status = format!("module is always on: {id}");
            return;
        }
        let kind = module.kind;
        let label = module.label(self.lang.is_zh()).to_string();
        let enabled = match kind {
            ModuleKind::Parser => &mut self.enabled_parser,
            ModuleKind::Keyboard => &mut self.enabled_keyboard,
        };
        match modules::toggle(&self.modules, enabled, id) {
            Ok(true) => {
                self.active_profile = PROFILE_CUSTOM.to_string();
                self.sync_modules();
                self.status = format!("enabled module: {label}");
            }
            Ok(false) => {
                self.active_profile = PROFILE_CUSTOM.to_string();
                self.sync_modules();
                self.status = format!("disabled module: {label}");
            }
            Err(error) => self.status = error,
        }
    }

    fn set_all_modules(&mut self, kind: ModuleKind, on: bool) {
        let enabled = match kind {
            ModuleKind::Parser => &mut self.enabled_parser,
            ModuleKind::Keyboard => &mut self.enabled_keyboard,
        };
        modules::set_all(&self.modules, enabled, kind, on);
        self.active_profile = PROFILE_CUSTOM.to_string();
        self.sync_modules();
        self.status = format!(
            "{} {}",
            if on {
                self.t("enabled all", "已全部启用")
            } else {
                self.t("disabled all", "已全部禁用")
            },
            kind.label(self.lang.is_zh())
        );
    }

    fn apply_profile(&mut self, name: &str) {
        if let Some((parser, keyboard)) = modules::builtin_selection(&self.modules, name) {
            self.enabled_parser = parser;
            self.enabled_keyboard = keyboard;
        } else if let Some(profile) = self.settings.module_profile(name).cloned() {
            self.enabled_parser = self.modules.reconcile(ModuleKind::Parser, &profile.parser);
            self.enabled_keyboard = self
                .modules
                .reconcile(ModuleKind::Keyboard, &profile.keyboard);
        } else {
            self.status = format!("unknown profile: {name}");
            return;
        }
        self.active_profile = name.to_string();
        self.sync_modules();
        self.status = format!("applied profile: {name}");
    }

    fn save_profile(&mut self) {
        let name = self.profile_name.trim().to_string();
        if name.is_empty() {
            self.status = self.t("profile name is empty", "档案名称为空").to_string();
            return;
        }
        if [PROFILE_ALL_ON, PROFILE_ALL_OFF, PROFILE_CUSTOM].contains(&name.as_str()) {
            self.status = format!("profile name is reserved: {name}");
            return;
        }
        let profile = ModuleProfile {
            name: name.clone(),
            parser: self.enabled_parser.clone(),
            keyboard: self.enabled_keyboard.clone(),
        };
        self.settings.save_module_profile(profile);
        self.active_profile = name.clone();
        self.sync_modules();
        self.status = format!("saved profile: {name}");
    }

    fn delete_profile(&mut self) {
        let name = self.active_profile.clone();
        if name == PROFILE_CUSTOM || name == PROFILE_ALL_ON || name == PROFILE_ALL_OFF {
            self.status = self
                .t("select a saved profile first", "请先应用一个已保存的档案")
                .to_string();
            return;
        }
        if self.settings.delete_module_profile(&name) {
            self.active_profile = PROFILE_CUSTOM.to_string();
            self.sync_modules();
            self.status = format!("deleted profile: {name}");
        } else {
            self.status = format!("profile not found: {name}");
        }
    }

    fn sync_modules(&mut self) {
        let names = self
            .enabled_parser
            .iter()
            .filter_map(|id| self.modules.find(id))
            .map(|module| module.key.clone())
            .collect::<Vec<_>>();
        let _ = self.engine.set_modules(&names);
        self.settings.enabled_parser_modules = self.enabled_parser.clone();
        self.settings.keyboard_modules = Some(self.enabled_keyboard.clone());
        self.settings.active_profile = self.active_profile.clone();
        self.settings.save();
    }

    fn reload_keyboard(&mut self) {
        self.keyboard = build_keyboard(&self.engine);
        match Registry::build(self.engine.modules_all(), &self.keyboard) {
            Ok(registry) => {
                self.modules = registry;
                self.enabled_parser = self
                    .modules
                    .reconcile(ModuleKind::Parser, &self.enabled_parser);
                self.enabled_keyboard = self
                    .modules
                    .reconcile(ModuleKind::Keyboard, &self.enabled_keyboard);
            }
            Err(error) => self.status = error,
        }
    }

    fn record_history(&mut self) {
        let entry = HistoryEntry {
            label: preview(&self.input, 28),
            input: self.input.clone(),
            output: self.output.clone(),
        };
        self.history.insert(0, entry);
        self.history.truncate(50);
    }

    fn record_history_reverse(&mut self) {
        let entry = HistoryEntry {
            label: format!("vector → {}", preview(&self.output, 28)),
            input: self.input.clone(),
            output: self.output.clone(),
        };
        self.history.insert(0, entry);
        self.history.truncate(50);
    }
}

fn parse_vector(line: &str, width: usize) -> Result<Vec<f64>, String> {
    let head = line.split(['?', '(']).next().unwrap_or(line).trim();
    let values = head
        .split(|ch: char| ch == ',' || ch == ';' || ch.is_whitespace())
        .filter(|value| !value.is_empty())
        .map(|value| value.parse::<f64>())
        .collect::<Result<Vec<_>, _>>()
        .map_err(|_| format!("could not parse vector: {line}"))?;
    if values.len() != width {
        return Err(format!(
            "vector needs {width} values, got {}: {line}",
            values.len()
        ));
    }
    if values.iter().any(|value| !value.is_finite()) {
        return Err(format!("vector must contain finite values: {line}"));
    }
    Ok(values)
}

fn format_segment(index: usize, segment: &Segment) -> String {
    let values = segment
        .values
        .iter()
        .map(|value| format!("{value:.4}"))
        .collect::<Vec<_>>()
        .join(", ");
    let tone = tone_annotation(&segment.tones);
    let mut line = format!(
        "[{index}]  ({values})  {}{}{}",
        segment.airstream_label(),
        if segment.note.is_empty() { "" } else { "  " },
        segment.note
    );
    if !tone.is_empty() {
        line.push_str(&format!("  tone={tone}"));
    }
    line
}

fn tone_annotation(groups: &[ToneGroup; 3]) -> String {
    let last = groups.iter().rposition(|group| group.kind != 0);
    let Some(last) = last else {
        return String::new();
    };
    let mut out = String::new();
    for (index, group) in groups.iter().enumerate().take(last + 1) {
        if index > 0 {
            out.push('?');
        }
        if group.kind == 0 {
            continue;
        }
        out.push('(');
        if index == 2 {
            for slot in 0..3 {
                if slot > 0 {
                    out.push(',');
                }
                out.push_str(&tone_number(group.values[slot]));
            }
        } else {
            let values = if group.values[2].is_nan() {
                if (group.values[0] - group.values[1]).abs() < 1e-9 {
                    &group.values[..1]
                } else {
                    &group.values[..2]
                }
            } else {
                &group.values[..3]
            };
            for (slot, value) in values.iter().enumerate() {
                if slot > 0 {
                    out.push(',');
                }
                out.push_str(&tone_number(*value));
            }
        }
        out.push(')');
    }
    out
}

fn tone_number(value: f64) -> String {
    if value.is_nan() {
        "0".to_string()
    } else if value.fract().abs() < 1e-9 {
        format!("{value:.0}")
    } else {
        format!("{value:.1}")
    }
}

fn preview(text: &str, limit: usize) -> String {
    let text = text.replace('\n', " ");
    if text.chars().count() <= limit {
        text
    } else {
        text.chars().take(limit).collect::<String>() + "…"
    }
}

fn csv_quote(field: &str) -> String {
    if field.contains([',', '"', '\n']) {
        format!("\"{}\"", field.replace('"', "\"\""))
    } else {
        field.to_string()
    }
}

fn keys(children: Vec<View>) -> Vec<KeyedView> {
    children
        .into_iter()
        .enumerate()
        .map(|(index, child)| KeyedView::new(index.to_string(), child))
        .collect()
}

/// Places a single view in a grid row. `GridChildExt` is implemented for
/// controls, not for `View`, so a one-cell grid carries the row assignment.
fn grid_row_cell(row: i32, content: View) -> View {
    Grid::new().grid_row(row).children([content])
}

fn app_icon_path() -> Option<PathBuf> {
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
    [
        exe_dir.join("Assets").join("final_ink.png"),
        exe_dir.join("assets").join("final_ink.png"),
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../assets/final_ink.png"),
    ]
    .into_iter()
    .find(|path| path.exists())
}

fn app_icon_view(size: f64) -> Option<Image> {
    let path = app_icon_path()?;
    Image::new()
        .source_file(path)
        .ok()
        .map(|image| image.width(size).height(size))
}

fn build_keyboard(engine: &Engine) -> KeyboardModel {
    keyboard::build(
        keyboard::Inventory {
            consonants: engine.keyboard_consonants(),
            non_pulmonic: engine.keyboard_non_pulmonic(),
            vowels: engine.keyboard_vowels(),
            modifiers: engine.keyboard_modifiers(),
            tones: engine.keyboard_tones(),
            consonant_places: engine
                .consonant_positions()
                .into_iter()
                .map(|key| (key.symbol, key.place))
                .collect(),
            vowel_positions: engine
                .vowel_positions()
                .into_iter()
                .map(|key| (key.symbol, (key.row, key.column)))
                .collect(),
            modifier_tiers: engine.modifier_tiers(),
        },
        |symbol| search_text(engine, symbol),
        |symbol| keyboard::manner_weight(&engine.query(symbol).unwrap_or_default()),
    )
}

fn search_text(engine: &Engine, symbol: &str) -> String {
    let raw = engine.query(symbol).unwrap_or_default();
    let (name, air) = describe_query(&raw);
    let first = raw.lines().next().unwrap_or_default();
    let english = crate::terms::english_terms(first);
    let chinese = crate::terms::chinese_terms(first);
    format!(
        "{} {} {} {} {}",
        symbol.to_lowercase(),
        name.to_lowercase(),
        air.to_lowercase(),
        english,
        chinese
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn search_text_includes_symbol_name_and_chinese_term() {
        let engine = Engine::new();
        let text = search_text(&engine, "ʃ");
        assert!(text.contains('ʃ'), "{text}");
        assert!(text.contains("fricative"), "{text}");
        assert!(text.contains("擦音"), "{text}");
    }

    #[test]
    fn keyboard_model_has_every_section_and_search_entry() {
        let engine = Engine::new();
        let model = build_keyboard(&engine);
        assert!(!model.consonants.is_empty());
        assert!(!model.non_pulmonic.is_empty());
        assert!(!model.vowels.is_empty());
        assert!(!model.diacritics.is_empty());
        assert!(!model.tones.is_empty());
        assert!(model.diacritics.iter().any(|symbol| symbol == "◌"));
        assert!(model.search.contains_key("ʃ"));
    }
}
