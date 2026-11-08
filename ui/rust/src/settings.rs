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

pub const PROFILE_ALL_ON: &str = "All on";
pub const PROFILE_ALL_OFF: &str = "All off";
pub const PROFILE_CUSTOM: &str = "Custom";

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ModuleProfile {
    pub name: String,
    pub parser: Vec<String>,
    pub keyboard: Vec<String>,
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
    pub enabled_parser_modules: Vec<String>,
    pub keyboard_modules: Option<Vec<String>>,
    pub module_profiles: Vec<ModuleProfile>,
    pub active_profile: String,
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
            enabled_parser_modules: Vec::new(),
            keyboard_modules: None,
            module_profiles: Vec::new(),
            active_profile: PROFILE_CUSTOM.to_string(),
        }
    }
}

impl Settings {
    pub fn module_profile(&self, name: &str) -> Option<&ModuleProfile> {
        self.module_profiles
            .iter()
            .find(|profile| profile.name == name)
    }

    /// Adds a user profile, replacing a profile with the same name.
    pub fn save_module_profile(&mut self, profile: ModuleProfile) {
        if let Some(existing) = self
            .module_profiles
            .iter_mut()
            .find(|known| known.name == profile.name)
        {
            *existing = profile;
        } else {
            self.module_profiles.push(profile);
        }
    }

    /// Removes a user profile by name. Returns `true` when one was removed.
    pub fn delete_module_profile(&mut self, name: &str) -> bool {
        let before = self.module_profiles.len();
        self.module_profiles.retain(|profile| profile.name != name);
        self.module_profiles.len() != before
    }

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
        assert!(settings.enabled_parser_modules.is_empty());
        assert!(settings.keyboard_modules.is_none());
        assert!(settings.module_profiles.is_empty());
        assert_eq!(settings.active_profile, PROFILE_CUSTOM);
    }

    #[test]
    fn module_settings_round_trip() {
        let settings = Settings {
            enabled_parser_modules: vec!["parser:americanist".into(), "parser:sinologist".into()],
            keyboard_modules: Some(vec!["keyboard:consonants".into()]),
            module_profiles: vec![ModuleProfile {
                name: "fieldwork".into(),
                parser: vec!["parser:oed".into()],
                keyboard: vec!["keyboard:vowels".into(), "keyboard:tones".into()],
            }],
            active_profile: "fieldwork".into(),
            ..Settings::default()
        };

        let text = serde_json::to_string(&settings).expect("serialize");
        let loaded: Settings = serde_json::from_str(&text).expect("deserialize");

        assert_eq!(
            loaded.enabled_parser_modules,
            settings.enabled_parser_modules
        );
        assert_eq!(loaded.keyboard_modules, settings.keyboard_modules);
        assert_eq!(loaded.module_profiles, settings.module_profiles);
        assert_eq!(loaded.active_profile, "fieldwork");
    }

    #[test]
    fn profiles_save_replaces_and_delete_removes_only_named() {
        let mut settings = Settings::default();
        settings.save_module_profile(ModuleProfile {
            name: "fieldwork".into(),
            parser: vec!["parser:americanist".into()],
            keyboard: vec!["keyboard:consonants".into()],
        });
        settings.save_module_profile(ModuleProfile {
            name: "teaching".into(),
            parser: Vec::new(),
            keyboard: vec!["keyboard:tones".into()],
        });
        settings.save_module_profile(ModuleProfile {
            name: "fieldwork".into(),
            parser: vec!["parser:oed".into()],
            keyboard: vec!["keyboard:vowels".into()],
        });

        assert_eq!(settings.module_profiles.len(), 2);
        assert_eq!(
            settings
                .module_profile("fieldwork")
                .expect("fieldwork")
                .parser,
            vec!["parser:oed".to_string()]
        );

        assert!(settings.delete_module_profile("fieldwork"));
        assert!(settings.module_profile("fieldwork").is_none());
        assert!(settings.module_profile("teaching").is_some());
        assert!(!settings.delete_module_profile("fieldwork"));
    }

    #[test]
    fn reset_layout_restores_defaults() {
        let mut settings = Settings {
            density: Density::Comfortable,
            split: 0.7,
            narrow_pane: NarrowPane::Tools,
            collapsed_sections: Vec::new(),
            ..Settings::default()
        };

        settings.reset_layout();

        assert_eq!(settings.density, Density::Compact);
        assert_eq!(settings.split, DEFAULT_SPLIT);
        assert_eq!(settings.narrow_pane, NarrowPane::Input);
        assert!(settings.collapsed_sections.iter().any(|id| id == "files"));
    }
}
