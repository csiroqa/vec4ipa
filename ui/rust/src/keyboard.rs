//! Keyboard model: section membership, IPA-chart ordering, and search text.

use std::collections::HashMap;

use crate::startup::is_modifier_symbol;

const TIE_COMPOSITES: &[&str] = &[
    "t͡ʃ", "d͡ʒ", "t͡s", "d͡z", "t͡ɕ", "d͡ʑ", "ʈ͡ʂ", "d͡ʐ", "k͡p", "ɡ͡b", "k͡x", "q͡χ", "ŋ͡m",
];

pub struct Inventory {
    pub consonants: Vec<String>,
    pub non_pulmonic: Vec<(String, i32)>,
    pub vowels: Vec<String>,
    pub modifiers: Vec<String>,
    pub tones: Vec<String>,
    pub consonant_places: Vec<(String, f64)>,
    pub vowel_positions: Vec<(String, (u8, u8))>,
    pub modifier_tiers: Vec<(String, i32)>,
}

pub struct KeyboardModel {
    pub consonants: Vec<String>,
    pub non_pulmonic: Vec<String>,
    pub vowels: Vec<String>,
    pub diacritics: Vec<String>,
    pub letters: Vec<String>,
    pub tones: Vec<String>,
    pub search: HashMap<String, String>,
}

impl KeyboardModel {
    /// Returns a symbol group by its module key.
    pub fn group(&self, key: &str) -> Option<&[String]> {
        match key {
            "consonants" => Some(&self.consonants),
            "nonpulmonic" => Some(&self.non_pulmonic),
            "vowels" => Some(&self.vowels),
            "diacritics" => Some(&self.diacritics),
            "letters" => Some(&self.letters),
            "tones" => Some(&self.tones),
            _ => None,
        }
    }

    pub fn group_len(&self, key: &str) -> usize {
        self.group(key).map_or(0, |group| group.len())
    }
}

/// IPA-chart manner order, read from the Latin feature identifier in a query.
pub fn manner_weight(info: &str) -> i32 {
    if info.contains(".pls") {
        0
    } else if info.contains(".afc") || info.contains(".afr") {
        1
    } else if info.contains(".frc") {
        2
    } else if info.contains(".nas") {
        3
    } else if info.contains(".lat") {
        4
    } else if info.contains(".tap") || info.contains(".flp") {
        5
    } else if info.contains(".trl") {
        6
    } else if info.contains(".appr") || info.contains(".apx") {
        7
    } else {
        8
    }
}

pub fn matches(symbol: &str, search: Option<&str>, filter: &str) -> bool {
    symbol.to_lowercase().contains(filter) || search.is_some_and(|text| text.contains(filter))
}

pub fn build(
    inventory: Inventory,
    search: impl Fn(&str) -> String,
    manner: impl Fn(&str) -> i32,
) -> KeyboardModel {
    let places = inventory
        .consonant_places
        .into_iter()
        .collect::<HashMap<_, _>>();
    let vowel_positions = inventory
        .vowel_positions
        .into_iter()
        .collect::<HashMap<_, _>>();
    let tiers = inventory
        .modifier_tiers
        .into_iter()
        .collect::<HashMap<_, _>>();

    let mut consonants = inventory.consonants;
    for tie in TIE_COMPOSITES {
        if !consonants.iter().any(|symbol| symbol == tie) {
            consonants.push((*tie).to_string());
        }
    }
    let manner_of = consonants
        .iter()
        .map(|symbol| (symbol.clone(), manner(symbol)))
        .collect::<HashMap<_, _>>();
    consonants.sort_by(|a, b| {
        manner_of
            .get(a)
            .unwrap_or(&8)
            .cmp(manner_of.get(b).unwrap_or(&8))
            .then(
                places
                    .get(a)
                    .unwrap_or(&0.5)
                    .partial_cmp(places.get(b).unwrap_or(&0.5))
                    .unwrap_or(std::cmp::Ordering::Equal),
            )
    });

    let mut non_pulmonic = inventory.non_pulmonic;
    non_pulmonic.sort_by(|(a, class_a), (b, class_b)| {
        class_a.cmp(class_b).then(
            manner(a).cmp(&manner(b)).then(
                places
                    .get(a)
                    .unwrap_or(&0.5)
                    .partial_cmp(places.get(b).unwrap_or(&0.5))
                    .unwrap_or(std::cmp::Ordering::Equal),
            ),
        )
    });
    let non_pulmonic = non_pulmonic
        .into_iter()
        .map(|(symbol, _)| symbol)
        .collect::<Vec<_>>();

    let mut vowels = inventory.vowels;
    vowels.sort_by_key(|symbol| vowel_positions.get(symbol).copied().unwrap_or((9, 9)));

    let mut diacritics = Vec::new();
    let mut letters = Vec::new();
    for symbol in inventory.modifiers {
        if is_modifier_symbol(&symbol) {
            diacritics.push(symbol);
        } else {
            letters.push(symbol);
        }
    }
    if !diacritics.iter().any(|symbol| symbol == "◌") {
        diacritics.push("◌".to_string());
    }
    diacritics.sort_by_key(|symbol| tiers.get(symbol).copied().unwrap_or(9));
    letters.sort_by_key(|symbol| tiers.get(symbol).copied().unwrap_or(9));

    let tones = inventory.tones;

    let mut search_map = HashMap::new();
    for symbol in consonants
        .iter()
        .chain(&non_pulmonic)
        .chain(&vowels)
        .chain(&diacritics)
        .chain(&letters)
        .chain(&tones)
    {
        search_map
            .entry(symbol.clone())
            .or_insert_with(|| search(symbol));
    }

    KeyboardModel {
        consonants,
        non_pulmonic,
        vowels,
        diacritics,
        letters,
        tones,
        search: search_map,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn inventory() -> Inventory {
        Inventory {
            consonants: vec!["s".into(), "p".into()],
            non_pulmonic: vec![("ʘ".into(), 3), ("pʼ".into(), 1)],
            vowels: vec!["u".into(), "a".into()],
            modifiers: vec!["\u{0303}".into(), "ʰ".into()],
            tones: vec!["˥".into()],
            consonant_places: vec![("p".into(), 1.0), ("s".into(), 3.0)],
            vowel_positions: vec![("a".into(), (0, 0)), ("u".into(), (0, 2))],
            modifier_tiers: vec![("\u{0303}".into(), 2), ("ʰ".into(), 1)],
        }
    }

    fn latin(symbol: &str) -> &'static str {
        match symbol {
            "p" | "pʼ" => "vl.bil.pls",
            "s" => "vl.alv.frc",
            "ʘ" => "clk",
            _ => "",
        }
    }

    fn model() -> KeyboardModel {
        build(
            inventory(),
            |symbol| symbol.to_string(),
            manner_weight_lookup,
        )
    }

    fn manner_weight_lookup(symbol: &str) -> i32 {
        manner_weight(latin(symbol))
    }

    #[test]
    fn sorts_consonants_by_manner_then_place() {
        let model = model();
        let p = model.consonants.iter().position(|s| s == "p").unwrap();
        let s = model.consonants.iter().position(|s| s == "s").unwrap();
        assert!(p < s, "{:?}", model.consonants);
    }

    #[test]
    fn sorts_non_pulmonic_by_airstream_class() {
        let model = model();
        assert_eq!(model.non_pulmonic, vec!["pʼ", "ʘ"]);
    }

    #[test]
    fn splits_diacritics_from_letters_and_adds_dotted_circle() {
        let model = model();
        assert!(model.diacritics.contains(&"◌".to_string()));
        assert!(model.diacritics.contains(&"\u{0303}".to_string()));
        assert!(model.letters.contains(&"ʰ".to_string()));
        assert!(!model.letters.contains(&"◌".to_string()));
    }

    #[test]
    fn adds_tie_composites_once() {
        let model = model();
        assert!(model.consonants.iter().any(|s| s == "t͡s"));
        assert_eq!(model.consonants.iter().filter(|s| *s == "t͡s").count(), 1);
    }

    #[test]
    fn search_text_is_cached_for_every_symbol() {
        let model = model();
        for symbol in model
            .consonants
            .iter()
            .chain(&model.vowels)
            .chain(&model.tones)
        {
            assert!(model.search.contains_key(symbol), "{symbol}");
        }
    }

    #[test]
    fn matches_symbol_name_and_chinese_term() {
        let fricative = "ʃ voiceless postalveolar fricative 清 龈后 擦音";
        let plosive = "p voiceless bilabial plosive 清 双唇 爆发音 肺部气流";
        assert!(matches("ʃ", Some(fricative), "ʃ"));
        assert!(matches("ʃ", Some(fricative), "fricative"));
        assert!(matches("p", Some(plosive), "plosive"));
        assert!(!matches("p", Some(plosive), "擦音"));
        assert!(matches("ʃ", Some(fricative), "擦音"));
        assert!(!matches("p", Some(plosive), "tone"));
    }
}
