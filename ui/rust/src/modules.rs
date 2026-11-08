//! Module registry: parser alias modules from the C core plus keyboard groups.
//!
//! Parser modules come from the wrapper's alias inventory. Keyboard modules are
//! the six symbol groups of the soft keyboard. Both kinds use namespaced ids so
//! one persisted list can name every module without ambiguity.

use std::collections::HashSet;

use crate::engine::ModuleInfo;
use crate::keyboard::KeyboardModel;
use crate::settings::{ModuleProfile, PROFILE_ALL_OFF, PROFILE_ALL_ON};

/// Keyboard group metadata: key, English label, Chinese label, English
/// description, Chinese description.
pub const KEYBOARD_GROUPS: [(&str, &str, &str, &str, &str); 6] = [
    (
        "consonants",
        "Consonants",
        "辅音",
        "Pulmonic consonants in IPA chart order.",
        "肺部气流辅音，按音标表顺序排列。",
    ),
    (
        "nonpulmonic",
        "Non-pulmonic",
        "非肺气流",
        "Ejectives, implosives, and clicks.",
        "挤喉音、内爆音和搭嘴音。",
    ),
    (
        "vowels",
        "Vowels",
        "元音",
        "Vowels arranged by height and backness.",
        "按舌位高低和前后排列的元音。",
    ),
    (
        "diacritics",
        "Diacritics",
        "附加符",
        "Combining marks for articulation details.",
        "表示发音细节的组合附加符。",
    ),
    (
        "letters",
        "Letters",
        "字母",
        "Modifier letters and other IPA letters.",
        "修饰字母及其他音标字母。",
    ),
    (
        "tones",
        "Tones",
        "声调",
        "Contour and level tone marks.",
        "曲折调与平调符号。",
    ),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ModuleKind {
    Parser,
    Keyboard,
}

impl ModuleKind {
    pub fn id_prefix(self) -> &'static str {
        match self {
            Self::Parser => "parser",
            Self::Keyboard => "keyboard",
        }
    }

    pub fn label(self, zh: bool) -> &'static str {
        match (self, zh) {
            (Self::Parser, false) => "Parser modules",
            (Self::Parser, true) => "解析模块",
            (Self::Keyboard, false) => "Keyboard groups",
            (Self::Keyboard, true) => "键盘组",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Module {
    pub id: String,
    /// Name the provider uses: alias module name or keyboard group key.
    pub key: String,
    pub label_en: String,
    pub label_zh: String,
    pub description_en: String,
    pub description_zh: String,
    pub kind: ModuleKind,
    pub count: usize,
    pub always_on: bool,
}

impl Module {
    pub fn label(&self, zh: bool) -> &str {
        if zh { &self.label_zh } else { &self.label_en }
    }

    pub fn description(&self, zh: bool) -> &str {
        if zh {
            &self.description_zh
        } else {
            &self.description_en
        }
    }

    /// Case-insensitive match over id, key, labels, and descriptions.
    pub fn matches(&self, filter: &str) -> bool {
        let filter = filter.trim().to_lowercase();
        if filter.is_empty() {
            return true;
        }
        [
            self.id.as_str(),
            self.key.as_str(),
            self.label_en.as_str(),
            self.label_zh.as_str(),
            self.description_en.as_str(),
            self.description_zh.as_str(),
        ]
        .iter()
        .any(|field| field.to_lowercase().contains(&filter))
    }
}

#[derive(Clone, Debug, Default)]
pub struct Registry {
    modules: Vec<Module>,
}

impl Registry {
    /// Builds the registry from the wrapper inventory and the keyboard model.
    pub fn build(parser: Vec<ModuleInfo>, keyboard: &KeyboardModel) -> Result<Self, String> {
        let mut modules = Vec::new();
        for info in parser {
            modules.push(Module {
                id: format!("{}:{}", ModuleKind::Parser.id_prefix(), info.name),
                key: info.name.clone(),
                label_en: info.name.clone(),
                label_zh: info.name.clone(),
                description_en: if info.school {
                    "School-specific alias symbols.".to_string()
                } else {
                    "Always-on alias symbols.".to_string()
                },
                description_zh: if info.school {
                    "学校转写惯例的别名符号。".to_string()
                } else {
                    "始终启用的别名符号。".to_string()
                },
                kind: ModuleKind::Parser,
                count: info.symbols,
                always_on: !info.school,
            });
        }
        for (key, label_en, label_zh, description_en, description_zh) in KEYBOARD_GROUPS {
            modules.push(Module {
                id: format!("{}:{key}", ModuleKind::Keyboard.id_prefix()),
                key: key.to_string(),
                label_en: label_en.to_string(),
                label_zh: label_zh.to_string(),
                description_en: description_en.to_string(),
                description_zh: description_zh.to_string(),
                kind: ModuleKind::Keyboard,
                count: keyboard.group_len(key),
                always_on: false,
            });
        }
        Self::new(modules)
    }

    /// Validates that no two providers registered the same module id.
    pub fn new(modules: Vec<Module>) -> Result<Self, String> {
        let mut seen = HashSet::new();
        for module in &modules {
            if !seen.insert(module.id.clone()) {
                return Err(format!("duplicate module id: {}", module.id));
            }
        }
        Ok(Self { modules })
    }

    pub fn find(&self, id: &str) -> Option<&Module> {
        self.modules.iter().find(|module| module.id == id)
    }

    pub fn of_kind(&self, kind: ModuleKind) -> impl Iterator<Item = &Module> {
        self.modules
            .iter()
            .filter(move |module| module.kind == kind)
    }

    /// Every toggleable module of a kind, in registry order.
    pub fn optional_ids(&self, kind: ModuleKind) -> Vec<String> {
        self.of_kind(kind)
            .filter(|module| !module.always_on)
            .map(|module| module.id.clone())
            .collect()
    }

    /// Keeps saved ids that still exist for this kind and are toggleable.
    /// Unknown, always-on, duplicate, and cross-kind ids are dropped.
    pub fn reconcile(&self, kind: ModuleKind, saved: &[String]) -> Vec<String> {
        let mut result = Vec::new();
        for id in saved {
            let Some(module) = self.find(id) else {
                continue;
            };
            if module.kind != kind || module.always_on {
                continue;
            }
            if result.iter().any(|known| known == id) {
                continue;
            }
            result.push(id.clone());
        }
        result
    }

    /// Sum of the item counts of the given enabled module ids.
    pub fn symbols(&self, enabled: &[String]) -> usize {
        enabled
            .iter()
            .filter_map(|id| self.find(id))
            .map(|module| module.count)
            .sum()
    }
}

/// Keyboard state at startup: a missing list means every group, while an
/// explicit list keeps only known, toggleable keyboard ids.
pub fn initial_keyboard(registry: &Registry, saved: Option<&[String]>) -> Vec<String> {
    match saved {
        Some(saved) => registry.reconcile(ModuleKind::Keyboard, saved),
        None => registry.optional_ids(ModuleKind::Keyboard),
    }
}

/// Namespaced id for a keyboard group key.
pub fn keyboard_module_id(key: &str) -> String {
    format!("{}:{key}", ModuleKind::Keyboard.id_prefix())
}

/// True when the keyboard group is enabled. The group order always follows
/// the keyboard model, so re-enabling restores the original position.
pub fn keyboard_visible(enabled: &[String], key: &str) -> bool {
    let id = keyboard_module_id(key);
    enabled.iter().any(|known| known == &id)
}

/// Toggles one module id. Returns the new state (`true` = enabled).
/// Always-on and unknown ids are rejected.
pub fn toggle(registry: &Registry, enabled: &mut Vec<String>, id: &str) -> Result<bool, String> {
    let module = registry
        .find(id)
        .ok_or_else(|| format!("unknown module: {id}"))?;
    if module.always_on {
        return Err(format!("module is always on: {id}"));
    }
    if let Some(index) = enabled.iter().position(|item| item == id) {
        enabled.remove(index);
        Ok(false)
    } else {
        enabled.push(id.to_string());
        Ok(true)
    }
}

/// Enables every optional module of a kind, or removes every module of that
/// kind. Always-on modules never enter the enabled list.
pub fn set_all(
    registry: &Registry,
    enabled: &mut Vec<String>,
    kind: ModuleKind,
    on: bool,
) -> usize {
    if on {
        *enabled = registry.optional_ids(kind);
        enabled.len()
    } else {
        enabled.retain(|id| !registry.find(id).is_some_and(|module| module.kind == kind));
        0
    }
}

/// The built-in profile selections, or `None` for a user profile name.
pub fn builtin_selection(registry: &Registry, name: &str) -> Option<(Vec<String>, Vec<String>)> {
    match name {
        PROFILE_ALL_ON => Some((
            registry.optional_ids(ModuleKind::Parser),
            registry.optional_ids(ModuleKind::Keyboard),
        )),
        PROFILE_ALL_OFF => Some((Vec::new(), Vec::new())),
        _ => None,
    }
}

/// Compares the live selection with a saved profile. Parser order is part of
/// the profile (it is the alias priority); keyboard order is not.
pub fn selection_matches(parser: &[String], keyboard: &[String], profile: &ModuleProfile) -> bool {
    parser == profile.parser && same_set(keyboard, &profile.keyboard)
}

fn same_set(left: &[String], right: &[String]) -> bool {
    left.len() == right.len() && left.iter().all(|id| right.contains(id))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn keyboard() -> KeyboardModel {
        KeyboardModel {
            consonants: vec!["p".into(), "t".into()],
            non_pulmonic: vec!["pʼ".into()],
            vowels: vec!["a".into()],
            diacritics: vec!["◌".into()],
            letters: vec!["ʰ".into()],
            tones: vec!["˥".into()],
            search: Default::default(),
        }
    }

    fn parser() -> Vec<ModuleInfo> {
        vec![
            ModuleInfo {
                name: "generic".into(),
                school: false,
                symbols: 3,
            },
            ModuleInfo {
                name: "americanist".into(),
                school: true,
                symbols: 4,
            },
            ModuleInfo {
                name: "sinologist".into(),
                school: true,
                symbols: 2,
            },
        ]
    }

    fn registry() -> Registry {
        Registry::build(parser(), &keyboard()).expect("registry")
    }

    #[test]
    fn builds_parser_and_keyboard_descriptors() {
        let registry = registry();
        let generic = registry.find("parser:generic").expect("generic");
        assert!(generic.always_on);
        assert_eq!(generic.kind, ModuleKind::Parser);
        assert_eq!(generic.count, 3);

        let americanist = registry.find("parser:americanist").expect("americanist");
        assert!(!americanist.always_on);
        assert_eq!(americanist.count, 4);

        let consonants = registry.find("keyboard:consonants").expect("consonants");
        assert_eq!(consonants.kind, ModuleKind::Keyboard);
        assert_eq!(consonants.count, 2);
        assert_eq!(registry.optional_ids(ModuleKind::Keyboard).len(), 6);
    }

    #[test]
    fn rejects_duplicate_module_ids() {
        let mut parser = parser();
        parser.push(parser[1].clone());
        let error = Registry::build(parser, &keyboard()).expect_err("duplicate");
        assert!(error.contains("duplicate"), "{error}");
    }

    #[test]
    fn reconcile_drops_unknown_always_on_and_duplicate_ids() {
        let registry = registry();
        let saved = vec![
            "parser:americanist".to_string(),
            "parser:generic".to_string(),
            "parser:missing".to_string(),
            "parser:americanist".to_string(),
            "keyboard:consonants".to_string(),
        ];
        assert_eq!(
            registry.reconcile(ModuleKind::Parser, &saved),
            vec!["parser:americanist".to_string()]
        );
        assert_eq!(
            registry.reconcile(ModuleKind::Keyboard, &saved),
            vec!["keyboard:consonants".to_string()]
        );
    }

    #[test]
    fn toggle_preserves_order_and_rejects_always_on() {
        let registry = registry();
        let mut enabled = Vec::new();
        assert!(toggle(&registry, &mut enabled, "parser:americanist").expect("enable"));
        assert!(toggle(&registry, &mut enabled, "parser:sinologist").expect("enable"));
        assert_eq!(
            enabled,
            vec![
                "parser:americanist".to_string(),
                "parser:sinologist".to_string()
            ]
        );

        assert!(!toggle(&registry, &mut enabled, "parser:americanist").expect("disable"));
        assert_eq!(enabled, vec!["parser:sinologist".to_string()]);

        assert!(toggle(&registry, &mut enabled, "parser:americanist").expect("re-enable"));
        assert_eq!(
            enabled,
            vec![
                "parser:sinologist".to_string(),
                "parser:americanist".to_string()
            ]
        );

        assert!(toggle(&registry, &mut enabled, "parser:generic").is_err());
        assert!(toggle(&registry, &mut enabled, "parser:missing").is_err());
    }

    #[test]
    fn keyboard_modules_hide_and_return_in_place() {
        let registry = registry();
        let mut enabled = registry.optional_ids(ModuleKind::Keyboard);
        assert!(keyboard_visible(&enabled, "consonants"));

        assert!(!toggle(&registry, &mut enabled, "keyboard:consonants").expect("hide"));
        assert!(!keyboard_visible(&enabled, "consonants"));
        assert!(keyboard_visible(&enabled, "vowels"));

        assert!(toggle(&registry, &mut enabled, "keyboard:consonants").expect("restore"));
        assert!(keyboard_visible(&enabled, "consonants"));
        assert_eq!(
            registry
                .optional_ids(ModuleKind::Keyboard)
                .iter()
                .position(|id| id == "keyboard:consonants"),
            Some(0)
        );
    }

    #[test]
    fn missing_keyboard_settings_enable_all_groups() {
        let registry = registry();
        assert_eq!(initial_keyboard(&registry, None).len(), 6);

        let saved = vec!["keyboard:tones".to_string(), "keyboard:missing".to_string()];
        assert_eq!(
            initial_keyboard(&registry, Some(&saved)),
            vec!["keyboard:tones".to_string()]
        );
        assert!(initial_keyboard(&registry, Some(&[])).is_empty());
    }

    #[test]
    fn saved_profile_restores_both_kinds() {
        use crate::settings::Settings;

        let registry = registry();
        let profile = ModuleProfile {
            name: "fieldwork".into(),
            parser: vec!["parser:americanist".into(), "parser:sinologist".into()],
            keyboard: vec!["keyboard:consonants".into(), "keyboard:tones".into()],
        };
        let settings = Settings {
            enabled_parser_modules: profile.parser.clone(),
            keyboard_modules: Some(profile.keyboard.clone()),
            module_profiles: vec![profile.clone()],
            active_profile: profile.name.clone(),
            ..Settings::default()
        };

        let text = serde_json::to_string(&settings).expect("serialize");
        let loaded: Settings = serde_json::from_str(&text).expect("deserialize");
        let parser = registry.reconcile(ModuleKind::Parser, &loaded.enabled_parser_modules);
        let keyboard = registry.reconcile(
            ModuleKind::Keyboard,
            loaded.keyboard_modules.as_deref().expect("keyboard ids"),
        );

        assert!(selection_matches(
            &parser,
            &keyboard,
            &loaded.module_profiles[0]
        ));
        assert_eq!(loaded.active_profile, "fieldwork");
    }

    #[test]
    fn bulk_actions_only_touch_their_kind() {
        let registry = registry();
        let mut parser = Vec::new();
        let mut keyboard = vec!["keyboard:tones".to_string()];

        assert_eq!(set_all(&registry, &mut parser, ModuleKind::Parser, true), 2);
        assert_eq!(
            parser,
            vec![
                "parser:americanist".to_string(),
                "parser:sinologist".to_string()
            ]
        );

        set_all(&registry, &mut parser, ModuleKind::Parser, false);
        assert!(parser.is_empty());
        assert_eq!(keyboard, vec!["keyboard:tones".to_string()]);

        assert_eq!(
            set_all(&registry, &mut keyboard, ModuleKind::Keyboard, true),
            6
        );
        assert_eq!(keyboard.len(), 6);
    }

    #[test]
    fn built_in_profiles_cover_both_kinds() {
        let registry = registry();
        let (parser, keyboard) = builtin_selection(&registry, PROFILE_ALL_ON).expect("all on");
        assert_eq!(
            parser,
            vec![
                "parser:americanist".to_string(),
                "parser:sinologist".to_string()
            ]
        );
        assert_eq!(keyboard.len(), 6);

        let (parser, keyboard) = builtin_selection(&registry, PROFILE_ALL_OFF).expect("all off");
        assert!(parser.is_empty());
        assert!(keyboard.is_empty());
        assert!(builtin_selection(&registry, "fieldwork").is_none());
    }

    #[test]
    fn profile_match_uses_parser_order_but_not_keyboard_order() {
        let profile = ModuleProfile {
            name: "fieldwork".into(),
            parser: vec!["parser:americanist".into(), "parser:sinologist".into()],
            keyboard: vec!["keyboard:tones".into(), "keyboard:vowels".into()],
        };
        assert!(selection_matches(
            &profile.parser,
            &["keyboard:vowels".to_string(), "keyboard:tones".to_string()],
            &profile
        ));
        assert!(!selection_matches(
            &[
                "parser:sinologist".to_string(),
                "parser:americanist".to_string()
            ],
            &profile.keyboard,
            &profile
        ));
    }
}
