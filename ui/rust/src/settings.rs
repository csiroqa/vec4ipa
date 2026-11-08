use serde::{Deserialize, Serialize};
use std::path::PathBuf;

use windows_reactor::WindowTheme;

use crate::layout::{DEFAULT_SPLIT, Density, NarrowPane, default_collapsed_sections};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum ThemeChoice {
    #[default]
    System,
    Light,
    Dark,
}

impl ThemeChoice {
    pub fn next(self) -> Self {
        match self {
            Self::System => Self::Light,
            Self::Light => Self::Dark,
            Self::Dark => Self::System,
        }
    }

    pub fn label(self, zh: bool) -> &'static str {
        match (self, zh) {
            (Self::System, false) => "System",
            (Self::System, true) => "跟随系统",
            (Self::Light, false) => "Light",
            (Self::Light, true) => "浅色",
            (Self::Dark, false) => "Dark",
            (Self::Dark, true) => "深色",
        }
    }

    pub fn window_theme(self) -> WindowTheme {
        match self {
            Self::System => WindowTheme::System,
            Self::Light => WindowTheme::Light,
            Self::Dark => WindowTheme::Dark,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum Language {
    #[default]
    En,
    Zh,
}

impl Language {
    pub fn toggled(self) -> Self {
        match self {
            Self::En => Self::Zh,
            Self::Zh => Self::En,
        }
    }

    pub fn is_zh(self) -> bool {
        matches!(self, Self::Zh)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub theme: ThemeChoice,
    pub language: Language,
    pub always_on_top: bool,
    pub split: f64,
    pub width: f64,
    pub height: f64,
    pub density: Density,
    pub narrow_pane: NarrowPane,
    pub collapsed_sections: Vec<String>,
    pub scheme: Option<String>,
    pub metric: Option<String>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            theme: ThemeChoice::System,
            language: Language::En,
            always_on_top: false,
            split: DEFAULT_SPLIT,
            width: 1280.0,
            height: 820.0,
            density: Density::Compact,
            narrow_pane: NarrowPane::Input,
            collapsed_sections: default_collapsed_sections(),
            scheme: None,
            metric: None,
        }
    }
}

impl Settings {
    pub fn reset_layout(&mut self) {
        self.density = Density::Compact;
        self.split = DEFAULT_SPLIT;
        self.narrow_pane = NarrowPane::Input;
        self.collapsed_sections = default_collapsed_sections();
    }

    pub fn save(&self) {
        let Some(path) = settings_path() else {
            return;
        };
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(text) = serde_json::to_string_pretty(self) {
            let _ = std::fs::write(path, text);
        }
    }
}

pub fn load() -> Settings {
    let Some(path) = settings_path() else {
        return Settings::default();
    };
    std::fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

fn settings_path() -> Option<PathBuf> {
    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("USERPROFILE").map(|home| PathBuf::from(home).join("AppData/Local"))
        })
        .unwrap_or_else(std::env::temp_dir);
    Some(base.join("vec4ipa").join("rust-ui.json"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn old_settings_load_layout_defaults() {
        let settings: Settings = serde_json::from_str("{}").expect("empty settings");
        assert_eq!(settings.density, Density::Compact);
        assert_eq!(settings.narrow_pane, NarrowPane::Input);
        assert!(settings.collapsed_sections.iter().any(|id| id == "views"));
    }

    #[test]
    fn reset_layout_restores_defaults() {
        let mut settings = Settings::default();
        settings.density = Density::Comfortable;
        settings.split = 0.7;
        settings.narrow_pane = NarrowPane::Tools;
        settings.collapsed_sections.clear();

        settings.reset_layout();

        assert_eq!(settings.density, Density::Compact);
        assert_eq!(settings.split, DEFAULT_SPLIT);
        assert_eq!(settings.narrow_pane, NarrowPane::Input);
        assert!(settings.collapsed_sections.iter().any(|id| id == "files"));
    }
}
