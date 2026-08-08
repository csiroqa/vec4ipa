#!/usr/bin/env python3
"""Standard Chinese (unt) transcription test suite.

Data source: 新老派普通话的宽严式记音（含儿化韵） by unt
(https://zhuanlan.zhihu.com/p/38258415; untunt/PhonoCollection).

Run:  python tools/test_standard_chinese.py [ipa2vec] [vec2ipa]

Covers, for every pinyin initial / glide / final / rhotacised final /
syllabic component / tone of the article:
  * every broad ([ ]) and narrow (中派) form the tool supports parses
    (rc = 0);
  * the article's special conventions parse as expected (清化浊音 b̥,
    卷舌舌尖 ʂ̺, 齿–龈前移 s̟, 拼合型儿化尾 ɻ˕, 上标 ᵝ/ᶹ/ᶨ …);
  * syllables and whole sentences built from the narrow forms parse
    with the expected segment count (no accidental merges);
  * all-round long IPA strings exercise the whole inventory at once
    (声母+介音+韵母+儿化+声调, 老派/中派/新派);
  * a "gap" section pins down the article symbols the tool does NOT
    support yet (◌̑ ˖ ˗ ◌͑ ◌͗ ȏ ä, 前置 ◌̻ …), asserting they fail so
    that adding support later is a deliberate, tested change.

NOTE: this suite tests the tool as it is; it makes no source changes.
Precomposed ä in the sentence strings is spelled decomposed (a+◌̈,
NFD-normalised) — identical IPA, same result.
"""

import sys
import unicodedata
from pathlib import Path

import _common
from _common import check, run

ROOT = Path(__file__).resolve().parents[1]
EXE = sys.argv[1] if len(sys.argv) > 1 else ROOT / ("ipa2vec" + _common.BIN_SUFFIX)
VEC2IPA = sys.argv[2] if len(sys.argv) > 2 else ROOT / ("vec2ipa" + _common.BIN_SUFFIX)
_common.EXE = EXE

def check_forms(name, forms, **kw):
    for f in forms:
        check(f"{name} {f!r}", [f], **kw)

# ------------------------------------------------------------------
# symbols the tool does not support yet (all of the article's marks
# are in these characters; anything containing them is a gap item)
# ------------------------------------------------------------------
UNSUPPORTED_SYMS = "◌̑˖˗◌͑◌͗ȏä"    # U+0311 U+02D6 U+02D7 U+0351 U+0357 U+020F U+00E4

def is_gap(form):
    """True when the article's spelling cannot be parsed by the tool
    as it stands (unsupported mark, or a combining mark written
    preposed before a base)."""
    if any(ch in form for ch in UNSUPPORTED_SYMS):
        return True
    if form.startswith("̻"):
        return True
    return False

def gap_forms(forms):
    return [f for f in forms if is_gap(f)]

def ok_forms(forms):
    return [f for f in forms if not is_gap(f)]

# ------------------------------------------------------------------
# article data — (label, [forms]) ; article spellings kept verbatim
# ------------------------------------------------------------------
INITIALS = [
    ("b",  ["p", "b̥"]),
    ("p",  ["pʰ", "pʰ"]),
    ("m",  ["m", "m"]),
    ("f",  ["f", "f"]),
    ("d",  ["t", "t̥"]),
    ("t",  ["tʰ", "tʰ"]),
    ("n",  ["n", "n"]),
    ("l",  ["l", "l̠"]),
    ("g",  ["k", "ɡ̊"]),
    ("k",  ["kʰ", "kʰ"]),
    ("h",  ["x", "x̞", "χ"]),                        # χ = 新派
    ("j",  ["tɕ", "t̥͡ʑ̥", "t̥͡z̻̊ʲ"]),                 # d̥͡ʑ̥, 新派 d̥͡z̻̊ʲ
    ("q",  ["tɕʰ", "tɕʰ", "t͡s̻ʲʰ"]),                # 新派 t͡s̻ʲʰ
    ("x",  ["ɕ", "ɕ", "s̻ʲ"]),                       # 新派 s̻ʲ
    ("zh", ["tʂ", "t̥͡ʐ̺̊"]),
    ("ch", ["tʂʰ", "tʂ̺ʰ"]),
    ("sh", ["ʂ", "ʂ̺"]),
    ("r",  ["ɻ", "ɻ̺"]),
    ("z",  ["ts", "t̥͡z̟̊"]),
    ("c",  ["tsʰ", "ts̟ʰ"]),
    ("s",  ["s", "s̟"]),
    # 零声母: 语音为零；有人接 e 时 ɰ，老派有人接 er 时也 ɰ
    ("zero", ["", "ɰ", "ɰə̠ɻ˕"]),
]
GLIDES = [
    ("i", ["j", "ʲj", "j", "̻ʲj"]),                  # j / ◌ʲj; t·d·n 后 ◌̻ʲj
    ("u", ["w", "ʷw", "β̞", "ʋ"]),                   # 零声母后 w~β̞; 新派 [ʋ]
    ("ü", ["ɥ", "ʷɥ", "̻ʲʷɥ"]),                      # n 后 ◌ʷɥ / ◌̻ʲʷɥ
]
FINALS = [
    ("a",  ["a", "ä"]),
    ("ia", ["ja", "jä"]),
    ("ua", ["wa", "wä"]),
    ("o",  ["o", "ʷo̜̽", "ʷo̜ɔ̜̑˖"]),
    ("io", ["jo", "j͗ʏ̯̈o̜̽", "j͗o̜ɔ̜̑˖"]),
    ("uo", ["wo", "wo̜̽", "wo̜ɔ̜̑˖", "ʊ̜ʌ̹̑˖"]),       # 新派 ʊ̜ʌ̹̑˖
    ("e",  ["ɤ", "ɤ̽", "ɤʌ̟̑", "ɯ̽ʌ̟̑", "ə"]),        # 新派 ɯ̽ʌ̟̑; 轻声虚语素 ə
    ("ê",  ["ɛ", "e̞ɛ̠̑", "ɛ̠"]),                     # 老派 ɛ̠
    ("ie", ["jɛ", "je̞ɛ̠̑", "jɛ̠", "je", "je̞ɛ̠̑"]),   # 老派 jɛ̠; 新派 [je]
    ("üe", ["ɥɛ", "ɥe̞͗ɛ̠̑", "ɥɛ̠", "ɥø", "ɥø̜ɛ̹̑˗"]),# 老派 ɥɛ̠; 新派 [ɥø]
    ("i",  ["i", "i", "iᶨ"]),                       # 零声母后 iᶨ
    ("ï₁", ["ɹ̩", "ɹ̟̍"]),                            # zi ci si
    ("ï₂", ["ɻ̍", "ɻ̺̍", "ɨ̞˞", "̻ɻ̺̍͡ɻ̻̍"]),          # zhi chi shi ri; 新派有人…
    ("u₁", ["u", "u", "uᵝ", "u̞"]),                  # 零声母后 uᵝ; 新派 u̞
    ("u₂", ["ʋ̩", "ʋ̩ˠ", "u̜ᶹ"]),                     # fu 的韵母
    ("ü",  ["y", "y", "y˗", "yᶨ", "y˗ᶨ"]),          # 零声母后 yᶨ~y˗ᶨ
    ("ai", ["aɪ", "a̠ɪ̯", "a̽ɪ̯"]),                   # 新派 a̽ɪ̯
    ("uai", ["waɪ", "wa̠ɪ̯", "wa̽ɪ̯"]),               # 新派 wa̽ɪ̯
    ("ei", ["eɪ", "e̽ɪ̯"]),
    ("ui₁", ["weɪ", "we̠ɪ̯"]),                        # 软腭音后
    ("ui₂", ["weɪ", "uɘ̹̑ɪ̯"]),                       # 舌冠音后; 新派并入 ui₁
    ("ao", ["ɑʊ", "ɑ̟ʊ̯", "ɑ̽ʊ̯"]),                   # 新派 ɑ̽ʊ̯
    ("iao", ["jɑʊ", "jɑ̟ʊ̯", "jɑ̽ʊ̯"]),               # 新派 jɑ̽ʊ̯
    ("ou", ["oʊ", "ʷo̜̽ʊ̯"]),
    ("iu", ["joʊ", "j͗ȏ̜ʊ", "j͗o̟͑ʊ̯", "j͗ʊ", "j͗o̟͑ʊ̯"]),  # 老派 j͗ʊ; 新派 j͗o̟͑ʊ̯
    ("an", ["an", "a̠n̚", "a̽n̚"]),                   # 新派 a̽n̚
    ("ian", ["jɛn", "jɛ̠n̚", "jen", "je̽n̚"]),        # 新派 [jen]
    ("uan", ["wan", "wa̠n̚", "wa̽n̚"]),               # 新派 wa̽n̚
    ("üan", ["ɥæn", "ɥʏ̯̈æ̠͗n̚", "ɥʏ̯̈ɛ̠͗n̚", "ɥɛ̠n̚"]),
    ("en", ["ən", "ə̟n̚"]),
    ("in", ["in", "ji̞n̚"]),
    ("un₁", ["wən", "wən̚"]),                        # 软腭音后
    ("un₂", ["wən", "uɘ̹̑˗n̚"]),                      # 舌冠音后
    ("ün", ["yn", "ɥy˕n̚", "ɥʏn̚"]),
    ("ang", ["ɑŋ", "ɑ̟ŋ̚", "ɑ̽ŋ̚"]),                 # 新派 ɑ̽ŋ̚
    ("iang", ["jɑŋ", "jɑ̟ŋ̚", "jɑ̽ŋ̚"]),             # 新派 jɑ̽ŋ̚
    ("uang", ["wɑŋ", "wɑ̟ŋ̚", "wɔ̜ŋ̚"]),             # 新派 wɔ̜ŋ̚
    ("eng", ["ɤŋ", "ɤ̽ŋ̚"]),
    ("ing", ["iŋ", "jɪŋ̚", "iɘ̯ŋ̚"]),
    ("ueng", ["wɤŋ", "wɤ̹̽ŋ̚"]),
    ("ong", ["ʊŋ", "ʷʊŋʷ̚"]),
    ("iong", ["jʊŋ", "ɥ͑ʊ̟ŋʷ̚", "j͗ʊ̟ŋʷ̚", "ɥʊ̟ŋʷ̚"]),  # 老派 j͗…; 新派 ɥ…
]
SYLLABIC = [
    ("er₁", ["ɚ", "ə̠ɻ˕", "ɚ̹"]),                    # ér ěr; 老派 ɚ̹~ə̠ɻ˕
    ("er₂", ["ɚ", "ɐɻ˕", "ɜɻ˕"]),                   # èr; 新派 ɜɻ˕
    ("m",  ["m̩", "m̩̚"]),
    ("n",  ["n̩", "n̩̚"]),
    ("ng", ["ŋ̍", "ŋ̍̚"]),
]
RHO_TOP = [
    ("ar",  ["a˞", "ä˞ɐ̯˞", "ä˞ɚ̯"]),               # 有些人独立
    ("iar", ["ja˞", "jä˞ɐ̯˞", "jä˞ɚ̯"]),
    ("uar", ["wa˞", "wä˞ɐ̯˞", "wä˞ɚ̯"]),
    ("or",  ["o˞", "ʷo̜̽˞", "ʷo̜˞ɝ̹̑"]),
    ("uor", ["wo˞", "wo̜̽˞", "wo̜˞ɝ̹̑", "ʊ̜˞ɝ̹̑"]),   # 新派 ʊ̜˞ɝ̹̑
    ("er",  ["ɤ˞", "ɤ̽˞", "ɤ˞ɝ̯", "ɯ̽˞ɝ̯"]),          # 新派 ɯ̽˞ɝ̯
    ("ier", ["jɛ˞", "jɚ", "jɚ̟ɝ̯", "jɝ", "jɝ̟ɝ̯",    # 老派 jɝ…
             "je˞", "jɘ˞", "jɘ̟˞ɝ̯"]),               # 新派 [je˞]
    ("üer", ["ɥɛ˞", "ɥɚ̹", "ɥɚ̟͗ɝ̯", "ɥɝ", "ɥɝ̟ɝ̯",  # 老派 ɥɝ…
             "ɥø˞", "ɥɵ̞͗˞", "ɥɵ̟͗˞ɝ̹̑"]),          # 新派 [ɥø˞]
    ("ur₁", ["ʊ˞", "ʊ˞"]),                          # 除 fur 外
    ("ur₂", ["ʊ˞ᶹ", "ʊ̜˞ᶹ"]),                        # fur 的韵母
]
RHO_BOTTOM = [
    ("anr",   ["ɐɚ", "ɐɻ˕", "ɜɻ˕"]),               # 新派 ɜɻ˕
    ("ianr",  ["jɐɚ", "jɐ̟ɻ˕", "jəɻ˕"]),            # 新派 jəɻ˕
    ("uanr",  ["wɐɚ", "wɐɻ˕", "wɜɻ˕"]),            # 新派 wɜɻ˕
    ("üanr",  ["ɥɐɚ", "ɥʏ̯̈ɐ̹ɻ˕", "ɥʏ̯̈ɜ̹ɻ˕", "ɥɐ̟ɻ˕"]),
    ("enr",   ["ɚ", "ə̠ɻ˕"]),
    ("inr",   ["iɚ", "ji̞ə̯ɻ˕"]),
    ("unr₁",  ["wɚ", "wə̠ɻ˕"]),                      # 软腭音后
    ("unr₂",  ["wɚ", "uɘ̹̑˗ɻ˕"]),                    # 舌冠音后
    ("ünr",   ["yɚ", "ɥʏɘ̹̑ɻ˕"]),
    # air uair eir ir uir ür 同 anr uanr enr inr unr ünr；ïr 同 enr
    ("air",   ["ɐɻ˕"]),  ("uair", ["wɐɻ˕"]),
    ("eir",   ["ə̠ɻ˕"]),  ("ir",  ["ji̞ə̯ɻ˕"]),
    ("uir",   ["uɘ̹̑˗ɻ˕"]), ("ür", ["ɥʏɘ̹̑ɻ˕"]),
    ("ïr",    ["ə̠ɻ˕"]),
    ("aor",   ["ɑ˞ʊ˞", "ɑ̹̽˞ʊ̯˞", "ɔ̟͑˞ʊ̯˞"]),        # 新派 ɔ̟͑˞ʊ̯˞
    ("iaor",  ["jɑ˞ʊ˞", "jɑ̹̽˞ʊ̯˞", "jɔ̟͑˞ʊ̯˞"]),    # 新派 jɔ̟͑˞ʊ̯˞
    ("our",   ["o˞ʊ˞", "ʷo̜̽˞ʊ̯˞"]),
    ("iur",   ["jo˞ʊ˞", "j͗ȏ̜˞ʊ˞", "j͗o̟͑˞ʊ̯˞"]),   # 新派 j͗o̟͑˞ʊ̯˞
    ("angr",  ["ɑ̃˞", "ɑ̽̃˞", "ɑ̽̃˞ɚ̯̃", "ɐ̃˞"]),       # 新派 ɐ̃˞
    ("iangr", ["jɑ̃˞", "jɑ̽̃˞", "jɑ̽̃˞ɚ̯̃", "jɐ̃˞"]),
    ("uangr", ["wɑ̃˞", "wɑ̽̃˞", "wɑ̽̃˞ɚ̯̃", "wɔ̜̃˞"]),
    ("engr",  ["ɤ̃˞", "ɤ̽̃˞", "ɤ̯̽˞ɚ̃"]),
    ("ingr",  ["iɘ̃˞", "iɘ̯̃˞", "jɘ̃˞"]),
    ("uengr", ["wɤ̃˞", "wɤ̜̽̃˞", "wɤ̹̽̑˞ɚ̃"]),
    ("ongr",  ["ʊ̃˞", "ʊ̃˞", "ʊ̃˞õ̯˞˖"]),
    ("iongr", ["jʊ̃˞", "ɥ͑ʊ̟̃˞", "ɥ͑ʊ̟̃˞õ̯˞˖",
               "j͗ʊ̟̃˞", "j͗ʊ̟̃˞õ̯˞˖", "ɥʊ̟̃˞"]),    # 老派 j͗…; 新派 ɥ…
]

# ------------------------------------------------------------------
# 1. inventory: supported forms must parse; gap forms are pinned
#    (each must FAIL so the suite still documents the article fully)
# ------------------------------------------------------------------
for label, forms in INITIALS + GLIDES + FINALS + SYLLABIC + RHO_TOP + RHO_BOTTOM:
    good = ok_forms(forms)
    bad = gap_forms(forms)
    if good:
        check_forms(f"supported {label}", good)
    if bad:
        for f in bad:
            check(f"gap (unsupported) {label} {f!r}", [f], expect_rc=1)

# ------------------------------------------------------------------
# 2. special conventions of the article (supported subset)
# ------------------------------------------------------------------
# 清化浊音 (voiceless ring on voiced plosives)
for f in ["b̥", "t̥", "ɡ̊", "d̥"]:
    check(f"voiceless-ring {f!r}", [f], expect_rc=0)
check("voiceless ring + tie = 1 segment", ["t̥͡ʑ̥"], expect_segs=1)
check("zh narrow = 1 segment", ["t̥͡ʐ̺̊"], expect_segs=1)
check("z narrow = 1 segment", ["t̥͡z̟̊"], expect_segs=1)
# 卷舌舌尖 (apical retroflex) and 齿–龈前移 (advanced denti-alveolar)
check("apical retroflex ʂ̺", ["ʂ̺"], expect_rc=0)
check("apical retroflex tʂ̺ʰ", ["tʂ̺ʰ"], expect_rc=0)
check("apical retroflex ɻ̺", ["ɻ̺"], expect_rc=0)
check("advanced denti-alveolar s̟", ["s̟"], expect_rc=0)
check("advanced denti-alveolar ts̟ʰ", ["ts̟ʰ"], expect_rc=0)
# 拼合型儿化韵尾 ɻ˕ (更松更开, 下移)
check("rhotacised tail ɻ˕", ["ɐɻ˕"], expect_segs=2)
check("er₂ = ɐɻ˕", ["ɐɻ˕"], expect_segs=2)
# 擦化 / 唇齿化上标 (accepted; superscript letters alias to bases today)
check("fricative-tint ᵝ (zero u)", ["uᵝ"], expect_rc=0)
check("fricative-tint ᶨ (zero i)", ["iᶨ"], expect_rc=0)
check("fricative-tint ᶨ (zero ü)", ["yᶨ"], expect_rc=0)
check("labiodental ᶹ (fur)", ["ʊ̜˞ᶹ"], expect_segs=1)
# 介音 secondary marks written preposed parse via the alias path
check("preposed ʲ before j", ["ʲj"], expect_rc=0)
check("preposed ʷ before w", ["ʷw"], expect_rc=0)
check("preposed ʷ before ɥ", ["ʷɥ"], expect_rc=0)
# postposed laminal+pal on the initial (t·d·n 后 ◌̻ʲj) — supported
check("laminal-palatalised glide after t", ["t̻ʲjɛ̠n̚"], expect_segs=4)
# ï₁ ï₂ narrow spellings (◌̍ accepted as a no-op tone mark)
check("ï₁ narrow ɹ̟̍", ["ɹ̟̍"], expect_segs=1)
check("ï₂ narrow ɻ̺̍", ["ɻ̺̍"], expect_segs=1)
check("ng syllabic ŋ̍", ["ŋ̍"], expect_segs=1)
# zero-initial ɰ convention
check("zero-initial before e = ɰ", ["ɰ"], expect_segs=1)

# ------------------------------------------------------------------
# 3. tones: 四声 and 轻声 (both 偏短偏弱 and 偏长偏强 readings)
# ------------------------------------------------------------------
TONES = [
    ("T1", "ma˥", "tone=(5,5)"),
    ("T2", "ma˧˥", "tone=(3,5)"),
    ("T3", "ma˨˩˦", "tone=(2,1,4)"),
    ("T4", "ma˥˩", "tone=(5,1)"),
    ("light short after T1", "mă˧", "tone=(3,3)"),
    ("light short after T2", "mă˦", "tone=(4,4)"),
    ("light short after T3", "mă˨", "tone=(2,2)"),
    ("light short after T4", "mă˩", "tone=(1,1)"),
    ("light strong after T1", "ma˦˩", "tone=(4,1)"),
    ("light strong after T2", "ma˥˨", "tone=(5,2)"),
    ("light strong after T3", "ma˧˦", "tone=(3,4)"),
    ("light strong after T4", "ma˨˩", "tone=(2,1)"),
]
for name, ipa, tone in TONES:
    check(f"tone {name}", [ipa], expect_tone=tone)

# ------------------------------------------------------------------
# 4. syllables & sentences in narrow transcription (中派), with
#    expected segment counts (catches accidental cross-boundary merges)
#    — precomposed ä is NFD-normalised (identical a+◌̈)
# ------------------------------------------------------------------
def nfd(s):
    return unicodedata.normalize("NFD", s)

# 「妈妈说，花儿是红色的，果子是甜的，我们去公园儿」
#  mā ma shuō huā ér shì hóng sè de guǒ zi shì tián de wǒ men qù gōng yuánr
SENTENCE = [
    ("妈 mā",   "mä˥", 2),              # a: ä
    ("妈 ma",   "mä̆˧", 2),              # 轻声(短弱) after T1
    ("说 shuō", "ʂ̺wo̜̽˥", 3),           # sh + uo [wo̜̽]
    ("花 huā",  "x̞wä˥", 3),             # h + ua [wä]
    ("儿 ér",   "ə̠ɻ˕˧˥", 2),            # er₁
    ("是 shì",  "ʂ̺ɻ̺̍˥˩", 2),           # sh + ï₂
    ("红 hóng", "x̞ʊŋʷ̚˧˥", 3),          # h + ong
    ("色 sè",   "s̟ɤ̽˥˩", 2),            # s + e [ɤ̽]（ɤʌ̟̑ 见 gap 节）
    ("的 de",   "tə˨˩", 2),              # 轻声虚语素 ə; 长强 after T4
    ("果 guǒ",  "kwo̜̽˨˩˦", 3),          # g + uo
    ("子 zi",   "t̥͡z̟̊ɹ̟̍˧˦", 2),         # z + ï₁; 长强 after T3
    ("是 shì",  "ʂ̺ɻ̺̍˥˩", 2),           # sh + ï₂
    ("甜 tián", "t̻ʲjɛ̠n̚˧˥", 4),         # t + ◌̻ʲj + ian
    ("的 de",   "tə̆˦", 2),              # 轻声虚语素 ə; 短弱 after T2
    ("我 wǒ",   "β̞o̜̽˨˩˦", 2),          # 零声母 uo: w~β̞
    ("们 men",  "mə̟n̆̚˨", 3),            # 轻声(短弱) after T3
    ("去 qù",   "tɕʰɥy˥˩", 3),          # q + ü [ɥ] + [y]
    ("公 gōng", "kʊŋʷ̚˥", 3),            # g + ong
    ("园儿 yuánr", "ɥʏ̯̈ɐ̹ɻ˕˧˥", 4),     # 零声母 üanr
]
sent_total = sum(segs for _, _, segs in SENTENCE)
sent_str = "".join(nfd(ipa) for _, ipa, _ in SENTENCE)
for name, ipa, segs in SENTENCE:
    check(f"sentence syllable {name}", [nfd(ipa)], expect_segs=segs)
check("sentence（妈妈说…）all syllables", [sent_str], expect_segs=sent_total)

# 老派 variant sentence（只用工具已支持的记号）: 「月儿夜」 yuè ér yè
OLD_SENT = [
    ("月 yuè 老派", "ɥɛ̠˥˩", 2),          # üe 老派 ɥɛ̠
    ("儿 ér 老派",  "ɚ̹˧˥", 1),           # er₁ 老派 ɚ̹
    ("夜 yè 老派",  "jɛ̠˥˩", 2),          # ie 老派 jɛ̠
]
old_total = sum(segs for _, _, segs in OLD_SENT)
old_str = "".join(ipa for _, ipa, _ in OLD_SENT)
for name, ipa, segs in OLD_SENT:
    check(f"old-school syllable {name}", [ipa], expect_segs=segs)
check("old-school sentence（月儿夜）", [old_str], expect_segs=old_total)

# 新派 variant sentence（只用工具已支持的记号）: 「新派小黄孩儿」
#  xīn pài xiǎo huáng háir
NEW_SENT = [
    ("新 xīn 新派",   "ɕji̞n̚˥", 4),      # in
    ("派 pài 新派",   "pa̽ɪ̯˥˩", 3),      # ai 新派 a̽ɪ̯
    ("小 xiǎo 新派",  "ɕjɑ̽ʊ̯˨˩˦", 4),   # iao 新派 jɑ̽ʊ̯
    ("黄 huáng 新派", "x̞wɔ̜ŋ̚˧˥", 4),    # uang 新派 wɔ̜ŋ̚
    ("孩儿 háir 新派", "x̞ɜɻ˕˧˥", 3),     # air=anr 新派 ɜɻ˕
]
new_total = sum(segs for _, _, segs in NEW_SENT)
new_str = "".join(ipa for _, ipa, _ in NEW_SENT)
for name, ipa, segs in NEW_SENT:
    check(f"new-school syllable {name}", [ipa], expect_segs=segs)
check("new-school sentence（新派小黄孩儿）", [new_str], expect_segs=new_total)

# 儿化 sentence: 「花儿门儿铃儿盆儿丝儿盖儿缸儿虫儿」
ERHUA_SENT = [
    ("花儿 huār",   "x̞wɐɻ˕˥", 4),       # anr
    ("门儿 ménr",   "mə̠ɻ˕˧˥", 3),       # enr
    ("铃儿 língr",  "l̠iɘ̯̃˞˧˥", 3),     # ingr
    ("盆儿 pénr",   "pə̠ɻ˕˧˥", 3),       # enr
    ("丝儿 sīr",    "s̟ə̠ɻ˕˥", 3),       # ïr = enr
    ("盖儿 gàir",   "kɐɻ˕˥˩", 3),       # air = anr
    ("缸儿 gāngr",  "kɑ̽̃˞˥", 2),        # angr
    ("虫儿 chóngr", "tʂ̺ʰʊ̃˞˧˥", 2),    # ongr
]
erhua_total = sum(segs for _, _, segs in ERHUA_SENT)
erhua_str = "".join(ipa for _, ipa, _ in ERHUA_SENT)
for name, ipa, segs in ERHUA_SENT:
    check(f"erhua syllable {name}", [ipa], expect_segs=segs)
check("erhua sentence（花儿门儿铃儿…）", [erhua_str], expect_segs=erhua_total)

# ------------------------------------------------------------------
# 5. all-round long IPA strings (全方位长组合)
# ------------------------------------------------------------------
# 5a. every 韵母 (宽式) once, in article order
FINALS_BROAD = [
    ("a",1),("ja",2),("wa",2),("o",1),("jo",2),("wo",2),("ɤ",1),("ɛ",1),
    ("jɛ",2),("ɥɛ",2),("i",1),("ɹ̩",1),("ɻ̍",1),("u",1),("ʋ̩",1),("y",1),
    ("aɪ",2),("waɪ",3),("eɪ",2),("weɪ",3),("ɑʊ",2),("jɑʊ",3),("oʊ",2),
    ("joʊ",3),("an",2),("jɛn",3),("wan",3),("ɥæn",3),("ən",2),("in",2),
    ("wən",3),("yn",2),("ɑŋ",2),("jɑŋ",3),("wɑŋ",3),("ɤŋ",2),("iŋ",2),
    ("wɤŋ",3),("ʊŋ",2),("jʊŋ",3),("ɚ",1),("m̩",1),("n̩",1),("ŋ̍",1),
]
finals_total = sum(n for _, n in FINALS_BROAD)
finals_str = "".join(ipa for ipa, _ in FINALS_BROAD)
check("all finals (broad) parse", [finals_str], expect_segs=finals_total)

# 5b. every 声母 + 介音 (窄式) once
#     standalone ʲj/ʷw/ʷɥ alias the leading mark to a w/ʝ base (2 segs);
#     in the chained string the marks instead attach postposed to the
#     previous segment, so the chain totals 26 segments
INIT_NARROW = [
    "b̥", "pʰ", "m", "f", "t̥", "tʰ", "n", "l̠",
    "ɡ̊", "kʰ", "x̞",
    "t̥͡ʑ̥", "tɕʰ", "ɕ",
    "t̥͡ʐ̺̊", "tʂ̺ʰ", "ʂ̺", "ɻ̺",
    "t̥͡z̟̊", "ts̟ʰ", "s̟",
    "ʲj", "ʷw", "ʷɥ", "ʋ̩ˠ", "u̜ᶹ",
]
INIT_SEGS = {
    "b̥":1,"pʰ":1,"m":1,"f":1,"t̥":1,"tʰ":1,"n":1,"l̠":1,
    "ɡ̊":1,"kʰ":1,"x̞":1,
    "t̥͡ʑ̥":1,"tɕʰ":1,"ɕ":1,
    "t̥͡ʐ̺̊":1,"tʂ̺ʰ":1,"ʂ̺":1,"ɻ̺":1,
    "t̥͡z̟̊":1,"ts̟ʰ":1,"s̟":1,
    "ʲj":2,"ʷw":2,"ʷɥ":2,"ʋ̩ˠ":1,"u̜ᶹ":1,
}
init_total = 26   # chained: 21 initials + j w ɥ ʋ̩ˠ u̜ᶹ (marks merge back)
init_str = "".join(INIT_NARROW)
for s in INIT_NARROW:
    check(f"initial/glide {s!r}", [s], expect_segs=INIT_SEGS[s])
check("all initials+glides (narrow) parse", [init_str], expect_segs=init_total)

# 5c. every 儿化韵母 (中派窄式) the tool supports, once
RHO_NARROW = [
    "ʷo̜̽˞", "wo̜̽˞", "ɤ̽˞", "jɚ", "ɥɚ̹", "ʊ˞", "ʊ̜˞ᶹ",
    "ɐɻ˕", "jɐ̟ɻ˕", "wɐɻ˕", "ɥʏ̯̈ɐ̹ɻ˕",
    "ə̠ɻ˕", "ji̞ə̯ɻ˕", "wə̠ɻ˕",
    "ɑ̹̽˞ʊ̯˞", "jɑ̹̽˞ʊ̯˞", "ʷo̜̽˞ʊ̯˞",
    "ɑ̽̃˞", "jɑ̽̃˞", "wɑ̽̃˞", "ɤ̽̃˞", "iɘ̯̃˞",
    "ʊ̃˞",
]
RHO_SEGS = {
    "ʷo̜̽˞":2, "wo̜̽˞":2, "ɤ̽˞":1, "jɚ":2, "ɥɚ̹":2, "ʊ˞":1, "ʊ̜˞ᶹ":1,
    "ɐɻ˕":2, "jɐ̟ɻ˕":3, "wɐɻ˕":3, "ɥʏ̯̈ɐ̹ɻ˕":4,
    "ə̠ɻ˕":2, "ji̞ə̯ɻ˕":4, "wə̠ɻ˕":3,
    "ɑ̹̽˞ʊ̯˞":2, "jɑ̹̽˞ʊ̯˞":3, "ʷo̜̽˞ʊ̯˞":3,
    "ɑ̽̃˞":1, "jɑ̽̃˞":2, "wɑ̽̃˞":2, "ɤ̽̃˞":1, "iɘ̯̃˞":2,
    "ʊ̃˞":1,
}
rho_total = 48   # chained: leading ʷ of ʷo̜̽˞ʊ̯˞ attaches to the previous
                 # segment (standalone alias counts differ; see per-item)
rho_str = "".join(RHO_NARROW)
for f in RHO_NARROW:
    check(f"rhotacised final {f!r}", [f], expect_segs=RHO_SEGS[f])
check("all rhotacised finals (narrow) parse", [rho_str], expect_segs=rho_total)

# 5d. 声调 all-round: 四声 + 轻声(短弱) + 轻声(长强)
tone_str = "a˥a˧˥a˨˩˦a˥˩ă˧ă˦ă˨ă˩a˦˩a˥˨a˧˦a˨˩"
check("all tones at once", [tone_str], expect_segs=12,
      expect_tone="tone=(2,1)")

# 5e. mega strings (each stays under the parser's 128-segment budget)
mega_a = sent_str + erhua_str + tone_str
mega_a_total = sent_total + erhua_total + 12
check("MEGA-A: 中派句子+儿化句+全部声调", [mega_a], expect_segs=mega_a_total)
mega_b = finals_str + init_str
mega_b_total = finals_total + init_total
check("MEGA-B: 全部韵母+全部声母", [mega_b], expect_segs=mega_b_total)
mega_c = rho_str + init_str + tone_str
mega_c_total = rho_total + init_total + 12
check("MEGA-C: 全部儿化韵母+全部声母+全部声调", [mega_c], expect_segs=mega_c_total)

# ------------------------------------------------------------------
# 6. gap section: article symbols the tool cannot parse yet.
#    These MUST fail today; when support is added, move them to the
#    supported sections above.
# ------------------------------------------------------------------
GAP_ITEMS = [
    ("semi-vowel ◌̑",       "ȃ"),
    ("spacing advanced ˖",  "a˖"),
    ("spacing retracted ˗", "a˗"),
    ("half-ring ◌͑",        "a͑"),
    ("half-ring ◌͗",        "a͗"),
    ("precomposed ȏ",       "ȏ"),
    ("precomposed ä",       "mä"),
    ("preposed laminal ◌̻", "̻a"),
    ("ï₂ 新派 preposed laminal", "̻ɻ̺̍͡ɻ̻̍"),
    ("glide preposed laminal",   "̻ʲj"),
    ("e 新派 ◌̑",            "ɯ̽ʌ̟̑"),
    ("io half-ring ◌͗",     "j͗ʏ̯̈o̜̽"),
    ("iu precomposed ȏ",    "j͗ȏ̜ʊ"),
    ("un₂ ˗",               "uɘ̹̑˗n̚"),
    ("ünr ◌̑",              "ɥʏɘ̹̑ɻ˕"),
    ("uengr ◌̑",            "wɤ̹̽̑˞ɚ̃"),
    ("aor 新派 ◌͑",         "ɔ̟͑˞ʊ̯˞"),
    ("iong half-ring ◌͑",   "ɥ͑ʊ̟ŋʷ̚"),
    ("uor 新派 ◌̑",         "ʊ̜˞ɝ̹̑"),
    ("ongr ˖",              "ʊ̃˞õ̯˞˖"),
]
for name, form in GAP_ITEMS:
    check(f"gap {name}", [form], expect_rc=1)

# ------------------------------------------------------------------
print(f"\n{_common.total - _common.fails}/{_common.total} checks passed")
sys.exit(1 if _common.fails else 0)
