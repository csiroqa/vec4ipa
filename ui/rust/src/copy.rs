//! Plain-language copy for the workbench.
//!
//! Composed lines, status sentences, and built-in profile labels live here so
//! the separator and localization rules can be tested without a window.

use crate::settings::{PROFILE_ALL_OFF, PROFILE_ALL_ON, PROFILE_CUSTOM};

pub const APP_NAME: &str = "vec4ipa Workbench";
pub const ACTIVE_MARK: &str = "✓";

pub fn version_line(version: &str, ndim: usize) -> String {
    format!("vec4ipa-ui {version} ({ndim} dimensions)")
}

/// Window subtitle. The runtime width is part of the subtitle so the title bar
/// does not need a separator chain for the status.
pub fn subtitle(version: &str, ndim: usize, zh: bool) -> String {
    if zh {
        format!("版本 {version}，{ndim} 维")
    } else {
        format!("Version {version}, {ndim} dimensions")
    }
}

/// Adds the single active marker to a selected label.
pub fn selected(label: &str, active: bool) -> String {
    if active {
        format!("{label} {ACTIVE_MARK}")
    } else {
        label.to_string()
    }
}

/// A directional label using one Unicode arrow. This is an aid, not a
/// separator; it must read correctly without the arrow.
pub fn direction(source: &str, target: &str) -> String {
    format!("{source} → {target}")
}

/// Display name for a built-in profile id. User names pass through unchanged.
pub fn profile_label(name: &str, zh: bool) -> String {
    match name {
        PROFILE_ALL_ON => {
            if zh {
                "全部启用".to_string()
            } else {
                "All on".to_string()
            }
        }
        PROFILE_ALL_OFF => {
            if zh {
                "全部禁用".to_string()
            } else {
                "All off".to_string()
            }
        }
        PROFILE_CUSTOM => {
            if zh {
                "自定义".to_string()
            } else {
                "Custom".to_string()
            }
        }
        _ => name.to_string(),
    }
}

/// Three plain summary lines for the module manager.
pub fn module_summary(
    parser_on: usize,
    parser_total: usize,
    keyboard_on: usize,
    keyboard_total: usize,
    symbols: usize,
    zh: bool,
) -> [String; 3] {
    if zh {
        [
            format!("解析模块：{parser_total} 个中已启用 {parser_on} 个"),
            format!("键盘组：{keyboard_total} 个中已启用 {keyboard_on} 个"),
            format!("符号：{symbols} 个"),
        ]
    } else {
        [
            format!("Parser modules: {parser_on} of {parser_total} on"),
            format!("Keyboard groups: {keyboard_on} of {keyboard_total} on"),
            format!("Symbols: {symbols}"),
        ]
    }
}

/// Module row metadata: description first, then state and count.
pub fn module_meta(description: &str, count: usize, always_on: bool, zh: bool) -> String {
    let symbols = if zh {
        format!("{count} 个符号。")
    } else {
        format!("{count} symbols.")
    };
    if always_on {
        if zh {
            format!("{description}始终启用。{symbols}")
        } else {
            format!("{description} Always on. {symbols}")
        }
    } else if zh {
        format!("{description}{symbols}")
    } else {
        format!("{description} {symbols}")
    }
}

pub fn enabled_module(label: &str, zh: bool) -> String {
    if zh {
        format!("已启用 {label}。")
    } else {
        format!("Enabled {label}.")
    }
}

pub fn disabled_module(label: &str, zh: bool) -> String {
    if zh {
        format!("已禁用 {label}。")
    } else {
        format!("Disabled {label}.")
    }
}

/// `kind_en` is the bare noun (`parser`, `keyboard`).
pub fn all_modules(kind_en: &str, kind_zh: &str, on: bool, zh: bool) -> String {
    if zh {
        format!("已全部{}{}。", if on { "启用" } else { "禁用" }, kind_zh)
    } else {
        format!(
            "{} all {} modules.",
            if on { "Enabled" } else { "Disabled" },
            kind_en
        )
    }
}

pub fn applied_profile(label: &str, zh: bool) -> String {
    if zh {
        format!("已应用档案：{label}。")
    } else {
        format!("Applied profile: {label}.")
    }
}

pub fn saved_profile(label: &str, zh: bool) -> String {
    if zh {
        format!("已保存档案：{label}。")
    } else {
        format!("Saved profile: {label}.")
    }
}

pub fn deleted_profile(label: &str, zh: bool) -> String {
    if zh {
        format!("已删除档案：{label}。")
    } else {
        format!("Deleted profile: {label}.")
    }
}

pub fn profile_not_found(name: &str, zh: bool) -> String {
    if zh {
        format!("找不到档案：{name}。")
    } else {
        format!("Profile not found: {name}.")
    }
}

pub fn profile_name_empty(zh: bool) -> String {
    if zh {
        "请输入档案名称。".to_string()
    } else {
        "Enter a profile name.".to_string()
    }
}

pub fn profile_name_reserved(zh: bool) -> String {
    if zh {
        "该档案名称已保留。".to_string()
    } else {
        "That profile name is reserved.".to_string()
    }
}

pub fn missing_file(kind_en: &str, kind_zh: &str, path: &str, zh: bool) -> String {
    if zh {
        format!("{kind_zh}文件不存在。{path}")
    } else {
        format!("{kind_en} file not found. {path}")
    }
}

pub fn tools_exported(count: usize, zh: bool) -> String {
    if zh {
        format!("已导出 {count} 个工具。")
    } else {
        format!("Exported {count} tools.")
    }
}

pub fn scheme_loaded(ndim: usize, zh: bool) -> String {
    if zh {
        format!("已加载方案，共 {ndim} 维。")
    } else {
        format!("Loaded scheme with {ndim} dimensions.")
    }
}

pub fn ignored_modules(count: usize, zh: bool) -> String {
    if zh {
        format!("已忽略 {count} 个已保存模块。")
    } else {
        format!("Ignored {count} saved modules.")
    }
}

pub fn sent(symbol: &str, clipboard: bool, zh: bool) -> String {
    match (zh, clipboard) {
        (true, true) => format!("已通过剪贴板发送 {symbol}。"),
        (true, false) => format!("已发送 {symbol}。"),
        (false, true) => format!("Sent {symbol} with the clipboard."),
        (false, false) => format!("Sent {symbol}."),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::settings::Settings;

    fn assert_plain(text: &str) {
        for forbidden in ["·", "—", "|"] {
            assert!(
                !text.contains(forbidden),
                "{text:?} contains the decorative separator {forbidden:?}"
            );
        }
    }

    #[test]
    fn subtitle_has_one_comma_and_no_status_chain() {
        assert_eq!(subtitle("4.0.0", 16, false), "Version 4.0.0, 16 dimensions");
        assert_eq!(subtitle("4.0.0", 18, true), "版本 4.0.0，18 维");
        assert_plain(&subtitle("4.0.0", 16, false));
    }

    #[test]
    fn version_line_uses_the_binary_name_and_plain_width() {
        assert_eq!(
            version_line("4.0.0", 16),
            "vec4ipa-ui 4.0.0 (16 dimensions)"
        );
    }

    #[test]
    fn only_the_active_label_gets_the_marker() {
        assert_eq!(selected("Vectors", true), "Vectors ✓");
        assert_eq!(selected("Vectors", false), "Vectors");
        assert_eq!(selected("Vectors", true).matches(ACTIVE_MARK).count(), 1);
        assert!(!selected("Vectors", false).contains(ACTIVE_MARK));
    }

    #[test]
    fn directional_label_keeps_one_arrow() {
        let label = direction("Vector", "IPA");
        assert_eq!(label, "Vector → IPA");
        assert_eq!(label.matches('→').count(), 1);
        assert_plain(&label);
    }

    #[test]
    fn built_in_profile_labels_localize_without_changing_ids() {
        assert_eq!(profile_label(PROFILE_ALL_ON, false), "All on");
        assert_eq!(profile_label(PROFILE_ALL_ON, true), "全部启用");
        assert_eq!(profile_label(PROFILE_ALL_OFF, true), "全部禁用");
        assert_eq!(profile_label(PROFILE_CUSTOM, true), "自定义");
        assert_eq!(profile_label("Fieldwork", true), "Fieldwork");

        let settings = Settings {
            active_profile: PROFILE_ALL_ON.to_string(),
            ..Settings::default()
        };
        let json = serde_json::to_string(&settings).expect("serialize settings");
        assert!(json.contains("\"active_profile\":\"All on\""), "{json}");
    }

    #[test]
    fn module_summary_is_three_plain_lines() {
        let english = module_summary(2, 9, 6, 6, 123, false);
        assert_eq!(
            english,
            [
                "Parser modules: 2 of 9 on",
                "Keyboard groups: 6 of 6 on",
                "Symbols: 123"
            ]
        );
        assert!(english.iter().all(|line| !line.contains('/')));
        for line in &english {
            assert_plain(line);
        }

        let chinese = module_summary(2, 9, 6, 6, 123, true);
        assert_eq!(
            chinese,
            [
                "解析模块：9 个中已启用 2 个",
                "键盘组：6 个中已启用 6 个",
                "符号：123 个"
            ]
        );
        for line in &chinese {
            assert_plain(line);
        }
    }

    #[test]
    fn module_meta_uses_words_for_state_and_count() {
        let english = module_meta("Core alias symbols.", 23, true, false);
        assert_eq!(english, "Core alias symbols. Always on. 23 symbols.");
        assert_plain(&english);

        let chinese = module_meta("核心别名符号。", 23, true, true);
        assert_eq!(chinese, "核心别名符号。始终启用。23 个符号。");
        assert_plain(&chinese);
    }

    #[test]
    fn status_sentences_are_plain() {
        assert_eq!(enabled_module("Americanist", false), "Enabled Americanist.");
        assert_eq!(disabled_module("Americanist", true), "已禁用 Americanist。");
        assert_eq!(
            all_modules("parser", "解析", true, false),
            "Enabled all parser modules."
        );
        assert_eq!(
            all_modules("parser", "解析模块", false, true),
            "已全部禁用解析模块。"
        );
        assert_eq!(applied_profile("All on", false), "Applied profile: All on.");
        assert_eq!(
            saved_profile("Fieldwork", false),
            "Saved profile: Fieldwork."
        );
        assert_eq!(
            deleted_profile("Fieldwork", true),
            "已删除档案：Fieldwork。"
        );
        assert_eq!(
            profile_not_found("Fieldwork", false),
            "Profile not found: Fieldwork."
        );
        assert_eq!(tools_exported(3, false), "Exported 3 tools.");
        assert_eq!(
            scheme_loaded(18, false),
            "Loaded scheme with 18 dimensions."
        );
        assert_eq!(ignored_modules(2, true), "已忽略 2 个已保存模块。");
        assert_eq!(sent("ʃ", false, false), "Sent ʃ.");
        assert_eq!(sent("ʃ", true, true), "已通过剪贴板发送 ʃ。");
        for line in [
            enabled_module("Americanist", false),
            applied_profile("All on", false),
            tools_exported(3, false),
        ] {
            assert_plain(&line);
        }
    }

    #[test]
    fn missing_file_keeps_the_path_as_detail() {
        let english = missing_file("Scheme", "方案", r"D:\ipa\custom.scheme", false);
        assert_eq!(english, r"Scheme file not found. D:\ipa\custom.scheme");
        assert_plain(&english);
        let chinese = missing_file("Scheme", "方案", r"D:\ipa\custom.scheme", true);
        assert_eq!(chinese, r"方案文件不存在。D:\ipa\custom.scheme");
    }
}
