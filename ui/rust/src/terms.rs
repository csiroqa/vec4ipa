//! Chinese feature terms, ported from the C# reference workbench.

const TERMS: &[(&str, &str)] = &[
    ("vl", "清"),
    ("vd", "浊"),
    ("asp", "送气"),
    ("blab", "双唇"),
    ("bil", "双唇"),
    ("lab", "唇"),
    ("lab.dnt", "唇齿"),
    ("lab.vel", "唇–软腭"),
    ("lab.pal", "唇–硬腭"),
    ("lbd", "唇齿"),
    ("dnt", "齿"),
    ("den", "齿"),
    ("alv", "龈"),
    ("rfl", "卷舌"),
    ("alvpal", "龈–腭"),
    ("pst", "龈后"),
    ("pal", "腭"),
    ("vel", "软腭"),
    ("uvu", "小舌"),
    ("pha", "咽"),
    ("epl", "会厌"),
    ("phr", "咽"),
    ("epi", "会厌"),
    ("glo", "喉"),
    ("glt", "喉"),
    ("pls", "爆发音"),
    ("nas", "鼻"),
    ("frc", "擦音"),
    ("appr", "近音"),
    ("apx", "近音"),
    ("lat", "边音"),
    ("tap", "拍音"),
    ("flp", "闪音"),
    ("trl", "颤音"),
    ("trill", "颤音"),
    ("afc", "塞擦音"),
    ("afr", "塞擦音"),
    ("per", "敲击"),
    ("vwl", "元音"),
    ("cls", "高"),
    ("ncls", "次高"),
    ("cmid", "半高"),
    ("omid", "半开"),
    ("nopn", "次开"),
    ("mid", "中"),
    ("opn", "开"),
    ("unr", "不圆唇"),
    ("rnd", "圆唇"),
    ("cnt", "央"),
    ("cent", "央"),
    ("fr", "前"),
    ("front", "前"),
    ("bk", "后"),
    ("back", "后"),
    ("rhot", "r 色彩"),
    ("ej", "喷"),
    ("ejt", "喷音"),
    ("clk", "啧音"),
    ("imp", "内爆音"),
    ("pulmonic", "肺部气流"),
    ("glottalic egressive", "喷音"),
    ("glottalic ingressive", "内爆音"),
    ("lingual", "啧音"),
    ("percussive", "敲击音"),
    ("modifier: ", "修饰符："),
    ("extIPA base: ", "extIPA 基段："),
    ("base: ", "基段："),
    ("alias: ", "别名："),
    ("dotted circle", "点圆圈"),
    ("placeholder", "占位符"),
    ("tier=", "层级="),
    ("[sets airstream]", "[设置气流]"),
    ("[inference]", "[推断]"),
    ("sup_rhot_ʢ", "r 色彩上标ʢ"),
    ("sup_rhot_ʕ", "r 色彩上标ʕ"),
    ("sup_rhot_ʁ", "r 色彩上标ʁ"),
    ("sup_rhot_r", "r 色彩上标r"),
    ("sup_e", "上标e"),
    ("sup_u", "上标u"),
    ("sup_O", "上标O"),
    ("sup_U", "上标U"),
    ("sup_W", "上标W"),
    ("sup_eps", "上标ɛ"),
    ("sup_d", "上标d"),
    ("sup_B", "上标B"),
    ("sup_P", "上标P"),
    ("sup_N", "上标N"),
    ("sup_A", "上标A"),
    ("sub_i", "下标i"),
    ("sub_r", "下标r"),
    ("bidental", "双齿"),
    ("velophar", "咽软腭"),
    ("tone_5", "最高"),
    ("tone_4", "高"),
    ("tone_3", "中"),
    ("tone_2", "低"),
    ("tone_1", "最低"),
    ("tone_high", "高平"),
    ("tone_low", "低平"),
    ("tone_fall", "降调"),
    ("tone_rise", "升调"),
    ("tone_extralow", "特低"),
    ("tone_lowfall", "低降"),
    ("tone_lowrise", "低升"),
    ("tone_highv", "高"),
    ("tone_lowv", "低"),
    ("pitch_0", "音高0"),
    ("pitch_1", "音高1"),
    ("pitch_2", "音高2"),
    ("pitch_3", "音高3"),
    ("pitch_4", "音高4"),
    ("pitch_5", "音高5"),
    ("pitch_6", "音高6"),
    ("pitch_7", "音高7"),
    ("pitch_8", "音高8"),
    ("pitch_9", "音高9"),
    ("pitch_highrise", "高升"),
    ("pitch_highfall", "高降"),
    ("pitch_lowrise", "低升"),
    ("pitch_risefall", "升降"),
    ("pitch_fallrise", "降升"),
    ("sandhi_5", "变调5"),
    ("sandhi_4", "变调4"),
    ("sandhi_3", "变调3"),
    ("sandhi_2", "变调2"),
    ("sandhi_1", "变调1"),
    ("class1", "阴平"),
    ("class2", "阳平"),
    ("class3", "阴上"),
    ("class4", "阳上"),
    ("class5", "阴去"),
    ("class6", "阳去"),
    ("class7", "阴入"),
    ("class8", "阳入"),
    ("upstep", "升阶"),
    ("downstep", "降阶"),
    ("global_up", "全局升"),
    ("global_down", "全局降"),
    ("macron_tone", "长音调"),
    ("sliding", "滑动"),
    ("short", "短"),
    ("long", "长"),
    ("lengthened", "延长"),
    ("gemination", "重叠"),
    ("half", "半长"),
    ("unrel", "无闻除阻"),
    ("fric_release", "擦除阻"),
    ("lat_release", "边除阻"),
    ("nasal_rel", "鼻除阻"),
    ("nas_rel", "鼻化除阻"),
    ("adv", "前移"),
    ("retr", "后移"),
    ("rtr", "舌根后缩"),
    ("atr", "舌根前伸"),
    ("raised", "抬高"),
    ("lowered", "降低"),
    ("centralized", "央化"),
    ("midcent", "中央"),
    ("breathy", "气声"),
    ("breathy_asp", "气声送气"),
    ("creaky", "嘎裂声"),
    ("fortis", "强"),
    ("lenis", "弱"),
    ("weak_asp", "弱送气"),
    ("whistled", "哨音"),
    ("syl", "成音节"),
    ("nsyl", "不成音节"),
    ("link", "连接"),
    ("tie", "连音线"),
    ("stress_1", "主重音"),
    ("stress_2", "次重音"),
    ("dark", "软腭化"),
    ("light", "清亮"),
    ("pal_hook", "腭化钩"),
    ("pal_prime", "腭化撇"),
    ("lab_subw", "唇化下标w"),
    ("labiodental", "唇齿"),
    ("linguolabial", "舌唇"),
    ("dental", "齿"),
    ("alveolar", "龈"),
    ("apical", "舌尖"),
    ("laminal", "舌叶"),
    ("retroflex", "卷舌"),
    ("phar", "咽化"),
    ("glottal_onset", "喉塞起始"),
    ("nas_click", "鼻啧音"),
    ("schwa_rel", "ə化"),
    ("offglide", "滑音"),
    ("rnd_less", "少圆唇"),
    ("rnd_more", "多圆唇"),
    ("lam", "舌叶"),
];

fn is_word_char(value: char) -> bool {
    value.is_ascii_alphanumeric() || value == '_'
}

fn contains_term(text: &str, term: &str) -> bool {
    for (begin, _) in text.match_indices(term) {
        let end = begin + term.len();
        let before_ok = term.chars().next().is_none_or(|value| !is_word_char(value))
            || text[..begin]
                .chars()
                .next_back()
                .is_none_or(|value| !is_word_char(value));
        let after_ok = term
            .chars()
            .next_back()
            .is_none_or(|value| !is_word_char(value))
            || text[end..]
                .chars()
                .next()
                .is_none_or(|value| !is_word_char(value));
        if before_ok && after_ok {
            return true;
        }
    }
    false
}

/// Chinese terms whose Latin keys occur in `text`, joined by spaces.
pub fn chinese_terms(text: &str) -> String {
    let mut out = String::new();
    for (key, value) in TERMS {
        if contains_term(text, key) {
            out.push_str(value);
            out.push(' ');
        }
    }
    out.trim_end().to_string()
}

const ENGLISH: &[(&str, &str)] = &[
    ("vl", "voiceless"),
    ("vd", "voiced"),
    ("asp", "aspirated"),
    ("blab", "bilabial"),
    ("bil", "bilabial"),
    ("lab.dnt", "labiodental"),
    ("lbd", "labiodental"),
    ("lab.vel", "labiovelar"),
    ("lab.pal", "labiopalatal"),
    ("dnt", "dental"),
    ("den", "dental"),
    ("alvpal", "alveolo-palatal"),
    ("alv", "alveolar"),
    ("pst", "postalveolar"),
    ("rfl", "retroflex"),
    ("pal", "palatal"),
    ("vel", "velar"),
    ("uvu", "uvular"),
    ("pha", "pharyngeal"),
    ("phr", "pharyngeal"),
    ("epl", "epiglottal"),
    ("epi", "epiglottal"),
    ("glo", "glottal"),
    ("glt", "glottal"),
    ("pls", "plosive"),
    ("afc", "affricate"),
    ("afr", "affricate"),
    ("frc", "fricative"),
    ("nas", "nasal"),
    ("lat", "lateral"),
    ("tap", "tap"),
    ("flp", "flap"),
    ("trl", "trill"),
    ("appr", "approximant"),
    ("apx", "approximant"),
    ("per", "percussive"),
    ("vwl", "vowel"),
    ("cls", "close"),
    ("ncls", "near-close"),
    ("cmid", "close-mid"),
    ("omid", "open-mid"),
    ("nopn", "near-open"),
    ("mid", "mid"),
    ("opn", "open"),
    ("unr", "unrounded"),
    ("rnd", "rounded"),
    ("cnt", "central"),
    ("cent", "central"),
    ("front", "front"),
    ("back", "back"),
    ("fr", "front"),
    ("bk", "back"),
    ("rhot", "rhotic"),
    ("ejt", "ejective"),
    ("ej", "ejective"),
    ("clk", "click"),
    ("imp", "implosive"),
    ("glottalic egressive", "ejective"),
    ("glottalic ingressive", "implosive"),
    ("lingual", "click"),
    ("pulmonic", "pulmonic"),
];

/// English feature words whose Latin keys occur in `text`, joined by spaces.
pub fn english_terms(text: &str) -> String {
    let mut out = String::new();
    for (key, value) in ENGLISH {
        if contains_term(text, key) {
            out.push_str(value);
            out.push(' ');
        }
    }
    out.trim_end().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_place_and_manner_terms() {
        let terms = chinese_terms("base: /p/  vl.bil.pls  (pulmonic)");
        assert!(terms.contains("清"), "{terms}");
        assert!(terms.contains("双唇"), "{terms}");
        assert!(terms.contains("爆发音"), "{terms}");
        assert!(terms.contains("肺部气流"), "{terms}");
    }

    #[test]
    fn finds_english_feature_words() {
        let terms = english_terms("vl.pst.frc");
        assert!(terms.contains("voiceless"), "{terms}");
        assert!(terms.contains("postalveolar"), "{terms}");
        assert!(terms.contains("fricative"), "{terms}");
    }

    #[test]
    fn finds_vowel_and_tone_terms() {
        let vowel = chinese_terms("vwl.front.opn.unr");
        assert!(vowel.contains("元音"), "{vowel}");
        assert!(vowel.contains("前"), "{vowel}");
        assert!(vowel.contains("开"), "{vowel}");
        let tone = chinese_terms("modifier: \u{0301}  class1  tier=3");
        assert!(tone.contains("阴平"), "{tone}");
        assert!(tone.contains("层级="), "{tone}");
    }

    #[test]
    fn ignores_terms_inside_longer_words() {
        assert!(!contains_term("xfrx", "fr"));
        assert!(contains_term("fr.opn", "fr"));
    }
}
