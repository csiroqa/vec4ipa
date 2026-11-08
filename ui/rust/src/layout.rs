use serde::{Deserialize, Serialize};

pub const WIDE_BREAKPOINT: f64 = 1000.0;
pub const DEFAULT_SPLIT: f64 = 0.46;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum Density {
    #[default]
    Compact,
    Comfortable,
}

impl Density {
    pub fn next(self) -> Self {
        match self {
            Self::Compact => Self::Comfortable,
            Self::Comfortable => Self::Compact,
        }
    }

    pub fn label(self, zh: bool) -> &'static str {
        match (self, zh) {
            (Self::Compact, false) => "Compact",
            (Self::Compact, true) => "紧凑",
            (Self::Comfortable, false) => "Comfortable",
            (Self::Comfortable, true) => "舒适",
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum NarrowPane {
    #[default]
    Input,
    Output,
    Tools,
}

impl NarrowPane {
    pub fn label(self, zh: bool) -> &'static str {
        match (self, zh) {
            (Self::Input, false) => "Input",
            (Self::Input, true) => "输入",
            (Self::Output, false) => "Output",
            (Self::Output, true) => "输出",
            (Self::Tools, false) => "Tools",
            (Self::Tools, true) => "工具",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LayoutMode {
    Wide,
    Narrow,
}

pub fn layout_mode(width: f64) -> LayoutMode {
    if width >= WIDE_BREAKPOINT {
        LayoutMode::Wide
    } else {
        LayoutMode::Narrow
    }
}

#[derive(Clone, Copy, Debug)]
pub struct LayoutMetrics {
    pub pane_padding: f64,
    pub section_gap: f64,
    pub stack_gap: f64,
    pub control_gap: f64,
    pub input_height: f64,
    pub output_height: f64,
    pub view_height: f64,
    pub control_height: f64,
    pub keyboard_font: f64,
    pub keyboard_width: f64,
    pub keyboard_height: f64,
}

impl LayoutMetrics {
    pub fn for_density(density: Density) -> Self {
        match density {
            Density::Compact => Self {
                pane_padding: 6.0,
                section_gap: 4.0,
                stack_gap: 6.0,
                control_gap: 3.0,
                input_height: 72.0,
                output_height: 180.0,
                view_height: 140.0,
                control_height: 32.0,
                keyboard_font: 16.0,
                keyboard_width: 52.0,
                keyboard_height: 44.0,
            },
            Density::Comfortable => Self {
                pane_padding: 10.0,
                section_gap: 8.0,
                stack_gap: 8.0,
                control_gap: 4.0,
                input_height: 96.0,
                output_height: 240.0,
                view_height: 180.0,
                control_height: 40.0,
                keyboard_font: 16.0,
                keyboard_width: 56.0,
                keyboard_height: 48.0,
            },
        }
    }
}

pub fn default_collapsed_sections() -> Vec<String> {
    [
        "views",
        "modules",
        "symbol_tools",
        "files",
        "history",
        "examples",
        "kb_nonpulmonic",
        "kb_vowels",
        "kb_modifiers",
        "kb_tones",
    ]
    .into_iter()
    .map(str::to_string)
    .collect()
}

pub fn is_collapsed(collapsed: &[String], id: &str) -> bool {
    collapsed.iter().any(|entry| entry == id)
}

pub fn keyboard_columns(available_width: f64, metrics: &LayoutMetrics) -> usize {
    let step = metrics.keyboard_width + metrics.control_gap;
    let fit = ((available_width + metrics.control_gap) / step).floor();
    (fit as usize).clamp(1, 12)
}

pub fn toggle_section(collapsed: &mut Vec<String>, id: &str) {
    if let Some(index) = collapsed.iter().position(|entry| entry == id) {
        collapsed.remove(index);
    } else {
        collapsed.push(id.to_string());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compact_keeps_targets_large_enough() {
        let metrics = LayoutMetrics::for_density(Density::Compact);
        assert!(metrics.control_height >= 32.0);
        assert!(metrics.keyboard_width >= 32.0);
        assert!(metrics.keyboard_height >= 32.0);
        assert!(metrics.keyboard_font >= 16.0);
        assert!(
            metrics.input_height < LayoutMetrics::for_density(Density::Comfortable).input_height
        );
    }

    #[test]
    fn breakpoint_is_wide_at_threshold() {
        assert_eq!(layout_mode(999.9), LayoutMode::Narrow);
        assert_eq!(layout_mode(1000.0), LayoutMode::Wide);
        assert_eq!(layout_mode(1280.0), LayoutMode::Wide);
    }

    #[test]
    fn default_collapsed_sections_keep_primary_groups_open() {
        let collapsed = default_collapsed_sections();
        assert!(is_collapsed(&collapsed, "views"));
        assert!(is_collapsed(&collapsed, "files"));
        assert!(!is_collapsed(&collapsed, "kb_consonants"));
        assert!(!is_collapsed(&collapsed, "favorites"));
        assert!(!is_collapsed(&collapsed, "recent"));
    }

    #[test]
    fn toggling_section_is_reversible() {
        let mut collapsed = Vec::new();
        toggle_section(&mut collapsed, "views");
        assert!(is_collapsed(&collapsed, "views"));
        toggle_section(&mut collapsed, "views");
        assert!(!is_collapsed(&collapsed, "views"));
    }

    #[test]
    fn keyboard_columns_fit_the_available_width() {
        let compact = LayoutMetrics::for_density(Density::Compact);
        let comfortable = LayoutMetrics::for_density(Density::Comfortable);
        assert_eq!(keyboard_columns(451.0, &compact), 8);
        assert_eq!(keyboard_columns(580.0, &compact), 10);
        assert_eq!(keyboard_columns(200.0, &compact), 3);
        assert_eq!(keyboard_columns(2000.0, &comfortable), 12);
        assert_eq!(keyboard_columns(-20.0, &compact), 1);
    }
}
