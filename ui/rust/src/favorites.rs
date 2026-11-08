//! Keyboard favorites persisted beside the C# workbench data.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

const MAX_FAVORITES: usize = 200;

pub fn path() -> Option<PathBuf> {
    let base = std::env::var_os("APPDATA").map(PathBuf::from)?;
    Some(base.join("vec4ipa").join("favorites.txt"))
}

pub fn normalize(list: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut out = Vec::new();
    for item in list {
        let item = item.trim().to_string();
        if item.is_empty() || !seen.insert(item.clone()) {
            continue;
        }
        out.push(item);
        if out.len() == MAX_FAVORITES {
            break;
        }
    }
    out
}

pub fn load_from(path: &Path) -> Vec<String> {
    let text = std::fs::read_to_string(path).unwrap_or_default();
    normalize(text.lines().map(str::to_string))
}

pub fn save_to(path: &Path, favorites: &[String]) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|error| format!("create {}: {error}", parent.display()))?;
    }
    let temp = path.with_extension("tmp");
    let body = favorites.join("\n");
    std::fs::write(&temp, body).map_err(|error| format!("write {}: {error}", temp.display()))?;
    std::fs::rename(&temp, path).map_err(|error| format!("rename {}: {error}", temp.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_trims_dedupes_and_caps() {
        let list = vec![
            " ʃ ".to_string(),
            "ʃ".to_string(),
            String::new(),
            "a".to_string(),
        ];
        assert_eq!(normalize(list), vec!["ʃ".to_string(), "a".to_string()]);
    }

    #[test]
    fn normalize_caps_at_the_limit() {
        let list = (0..250)
            .map(|index| format!("s{index}"))
            .collect::<Vec<_>>();
        assert_eq!(normalize(list).len(), MAX_FAVORITES);
    }

    #[test]
    fn round_trips_through_a_file() {
        let dir = std::env::temp_dir().join("vec4ipa-favorites-test");
        let path = dir.join("favorites.txt");
        let list = vec!["ʃ".to_string(), "t͡s".to_string()];
        save_to(&path, &list).expect("save");
        assert_eq!(load_from(&path), list);
        let _ = std::fs::remove_dir_all(dir);
    }
}
