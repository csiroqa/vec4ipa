use std::ffi::{CStr, CString, c_char, c_int};
use std::marker::PhantomData;
use std::rc::Rc;

const MAX_TOKS: usize = 512;
const NAME_LEN: usize = 48;
const AIRSTREAM_LABELS: [&str; 5] = [
    "pulmonic",
    "glottalic egressive",
    "glottalic ingressive",
    "lingual",
    "percussive",
];

unsafe extern "C" {
    fn ipa2v_ndim() -> c_int;
    fn ipa2v_forward(
        text: *const c_char,
        err: *mut c_char,
        errsz: usize,
        out: *mut f64,
        airstream: *mut c_int,
        names: *mut c_char,
    ) -> c_int;
    fn ipa2v_forward_tone(
        text: *const c_char,
        err: *mut c_char,
        errsz: usize,
        out: *mut f64,
        tone: *mut f64,
        tkind: *mut c_int,
    ) -> c_int;
    fn ipa2v_reverse(v: *const f64, width: c_int, out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_query(sym: *const c_char, out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_align(a: *const c_char, b: *const c_char, out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_distance(a: *const c_char, b: *const c_char, out: *mut f64) -> c_int;
    fn ipa2v_ir(text: *const c_char, out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_json(text: *const c_char, out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_ir_export(
        text: *const c_char,
        base: *const c_char,
        err: *mut c_char,
        errsz: usize,
    ) -> c_int;
    fn ipa2v_load_metric(path: *const c_char) -> c_int;
    fn ipa2v_set_args(n: c_int, argv: *const *const c_char) -> c_int;
    fn ipa2v_version() -> *const c_char;
    fn ipa2v_docs() -> *const c_char;
    fn ipa2v_modules_full(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_modules_all(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_set_modules(csv: *const c_char) -> c_int;
    fn ipa2v_enabled_modules(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_table(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_stats(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_weights_effective(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_dim_names(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_vowel_positions(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_cons(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_cons_np(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_vowels(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_mods(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_tones(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_cons_pos(out: *mut c_char, outsz: usize) -> c_int;
    fn ipa2v_kb_mod_tiers(out: *mut c_char, outsz: usize) -> c_int;
}

#[derive(Clone, Debug, Default)]
pub struct ToneGroup {
    pub kind: i32,
    pub values: [f64; 3],
}

#[derive(Clone, Debug, Default)]
pub struct Segment {
    pub values: Vec<f64>,
    pub airstream: usize,
    pub note: String,
    pub tones: [ToneGroup; 3],
}

impl Segment {
    pub fn airstream_label(&self) -> &'static str {
        AIRSTREAM_LABELS
            .get(self.airstream)
            .copied()
            .unwrap_or("unknown")
    }
}

#[derive(Clone, Debug)]
pub struct VowelKey {
    pub symbol: String,
    pub row: u8,
    pub column: u8,
}

#[derive(Clone, Debug)]
pub struct ConsonantKey {
    pub symbol: String,
    pub place: f64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModuleInfo {
    pub name: String,
    /// School modules can be toggled; always-on modules cannot.
    pub school: bool,
    pub symbols: usize,
}

/// The C engine keeps process-global scheme, metric, and module state. This
/// handle is deliberately not `Send` or `Sync`; use it only from the UI thread.
pub struct Engine {
    _not_send: PhantomData<Rc<()>>,
}

impl Default for Engine {
    fn default() -> Self {
        Self::new()
    }
}

impl Engine {
    pub fn new() -> Self {
        Self {
            _not_send: PhantomData,
        }
    }

    /// Applies CLI-style options (`-D`, `--metric`, school modules, width).
    pub fn set_args(&mut self, args: &[&str]) -> Result<(), String> {
        let owned = args
            .iter()
            .map(|arg| CString::new(*arg))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| "argument contains a NUL byte".to_string())?;
        let pointers = owned.iter().map(|arg| arg.as_ptr()).collect::<Vec<_>>();
        // SAFETY: every pointer is valid for the duration of the call, and the
        // C shim copies what it needs.
        unsafe {
            ipa2v_set_args(pointers.len() as c_int, pointers.as_ptr());
        }
        Ok(())
    }

    pub fn ndim(&self) -> usize {
        // SAFETY: no arguments; the C shim reads its process-global width.
        unsafe { ipa2v_ndim() as usize }
    }

    pub fn forward(&self, text: &str) -> Result<Vec<Segment>, String> {
        let text = CString::new(text).map_err(|_| "input contains a NUL byte".to_string())?;
        let ndim = self.ndim();
        let mut err = vec![0u8; 1024];
        let mut values = vec![0f64; ndim * MAX_TOKS];
        let mut airstream = vec![0 as c_int; MAX_TOKS];
        let mut names = vec![0u8; MAX_TOKS * NAME_LEN];

        // SAFETY: buffers are sized from the runtime width and the shim's
        // declared segment limit; the shim writes at most that many rows.
        let count = unsafe {
            ipa2v_forward(
                text.as_ptr(),
                err.as_mut_ptr().cast(),
                err.len(),
                values.as_mut_ptr(),
                airstream.as_mut_ptr(),
                names.as_mut_ptr().cast(),
            )
        };
        if count < 0 {
            return Err(c_string(&err));
        }
        let count = count as usize;
        if count > MAX_TOKS {
            return Err(format!("too many segments: {count}"));
        }

        let mut segments = Vec::with_capacity(count);
        for (index, airstream) in airstream.iter().enumerate().take(count) {
            let start = index * ndim;
            let note_start = index * NAME_LEN;
            segments.push(Segment {
                values: values[start..start + ndim].to_vec(),
                airstream: *airstream as usize,
                note: c_string(&names[note_start..note_start + NAME_LEN]),
                tones: Default::default(),
            });
        }
        Ok(segments)
    }

    pub fn forward_with_tone(&self, text: &str) -> Result<Vec<Segment>, String> {
        let text = CString::new(text).map_err(|_| "input contains a NUL byte".to_string())?;
        let ndim = self.ndim();
        let mut err = vec![0u8; 1024];
        let mut values = vec![0f64; ndim * MAX_TOKS];
        let mut tone = vec![0f64; 9 * MAX_TOKS];
        let mut tkind = vec![0 as c_int; 3 * MAX_TOKS];

        // SAFETY: see `forward`; the tone buffers match the shim contract.
        let count = unsafe {
            ipa2v_forward_tone(
                text.as_ptr(),
                err.as_mut_ptr().cast(),
                err.len(),
                values.as_mut_ptr(),
                tone.as_mut_ptr(),
                tkind.as_mut_ptr(),
            )
        };
        if count < 0 {
            return Err(c_string(&err));
        }
        let count = count as usize;
        if count > MAX_TOKS {
            return Err(format!("too many segments: {count}"));
        }

        let mut segments = Vec::with_capacity(count);
        for index in 0..count {
            let start = index * ndim;
            let mut groups = [
                ToneGroup::default(),
                ToneGroup::default(),
                ToneGroup::default(),
            ];
            for group in 0..3 {
                groups[group].kind = tkind[index * 3 + group];
                for slot in 0..3 {
                    groups[group].values[slot] = tone[index * 9 + group * 3 + slot];
                }
            }
            segments.push(Segment {
                values: values[start..start + ndim].to_vec(),
                airstream: 0,
                note: String::new(),
                tones: groups,
            });
        }
        Ok(segments)
    }

    pub fn reverse(&self, vector: &[f64]) -> Result<String, String> {
        if vector.iter().any(|value| !value.is_finite()) {
            return Err("vector must contain finite values".to_string());
        }
        let width = self.ndim();
        if vector.len() != width {
            return Err(format!("vector needs {width} values, got {}", vector.len()));
        }
        let mut out = vec![0u8; 1024];
        // SAFETY: the vector length matches the loaded width; the shim copies
        // at most that many values and writes to the supplied output buffer.
        let rc = unsafe {
            ipa2v_reverse(
                vector.as_ptr(),
                width as c_int,
                out.as_mut_ptr().cast(),
                out.len(),
            )
        };
        if rc == 0 {
            Ok(c_string(&out))
        } else {
            Err(c_string(&out))
        }
    }

    pub fn query(&self, symbol: &str) -> Result<String, String> {
        let symbol = CString::new(symbol).map_err(|_| "symbol contains a NUL".to_string())?;
        let mut out = vec![0u8; 2048];
        // SAFETY: output buffer is valid for the call.
        unsafe {
            ipa2v_query(symbol.as_ptr(), out.as_mut_ptr().cast(), out.len());
        }
        Ok(c_string(&out))
    }
    pub fn align(&self, a: &str, b: &str) -> Result<String, String> {
        let a = CString::new(a).map_err(|_| "input contains a NUL".to_string())?;
        let b = CString::new(b).map_err(|_| "input contains a NUL".to_string())?;
        let mut out = vec![0u8; 64 * 1024];
        // SAFETY: both strings and the output buffer are valid for the call.
        let rc = unsafe { ipa2v_align(a.as_ptr(), b.as_ptr(), out.as_mut_ptr().cast(), out.len()) };
        if rc == 0 {
            Ok(c_string(&out))
        } else {
            Err(c_string(&out))
        }
    }

    pub fn distance(&self, a: &str, b: &str) -> Result<f64, String> {
        let a = CString::new(a).map_err(|_| "input contains a NUL".to_string())?;
        let b = CString::new(b).map_err(|_| "input contains a NUL".to_string())?;
        let mut value = 0.0;
        // SAFETY: both strings are valid; `value` is a valid out pointer.
        let rc = unsafe { ipa2v_distance(a.as_ptr(), b.as_ptr(), &mut value) };
        match rc {
            0 => Ok(value),
            -1 => Err("could not parse one of the symbols".to_string()),
            -2 => Err("both inputs must contain exactly one segment".to_string()),
            _ => Err(format!("distance failed with code {rc}")),
        }
    }

    pub fn ir(&self, text: &str) -> String {
        self.text_call(text, ipa2v_ir, 256 * 1024)
    }

    pub fn json(&self, text: &str) -> String {
        self.text_call(text, ipa2v_json, 256 * 1024)
    }

    pub fn ir_export(&self, text: &str, base: &str) -> Result<(), String> {
        let text = CString::new(text).map_err(|_| "input contains a NUL".to_string())?;
        let base = CString::new(base).map_err(|_| "base path contains a NUL".to_string())?;
        let mut err = vec![0u8; 1024];
        // SAFETY: strings and error buffer are valid for the call.
        let rc = unsafe {
            ipa2v_ir_export(
                text.as_ptr(),
                base.as_ptr(),
                err.as_mut_ptr().cast(),
                err.len(),
            )
        };
        if rc == 0 { Ok(()) } else { Err(c_string(&err)) }
    }

    pub fn load_metric(&self, path: &str) -> Result<(), String> {
        let path = CString::new(path).map_err(|_| "path contains a NUL".to_string())?;
        // SAFETY: the path is a valid NUL-terminated UTF-8 string.
        let rc = unsafe { ipa2v_load_metric(path.as_ptr()) };
        if rc == 0 {
            Ok(())
        } else {
            Err(format!("metric load failed with code {rc}"))
        }
    }

    pub fn version(&self) -> String {
        // SAFETY: the shim returns a static NUL-terminated string.
        unsafe { CStr::from_ptr(ipa2v_version()) }
            .to_string_lossy()
            .into_owned()
    }

    pub fn docs(&self) -> String {
        // SAFETY: the shim returns a static NUL-terminated string.
        unsafe { CStr::from_ptr(ipa2v_docs()) }
            .to_string_lossy()
            .into_owned()
    }

    pub fn modules_full(&self) -> String {
        self.text_call_no_input(ipa2v_modules_full, 64 * 1024)
    }

    /// Every alias module the wrapper exposes, in core table order.
    pub fn modules_all(&self) -> Vec<ModuleInfo> {
        lines(&self.text_call_no_input(ipa2v_modules_all, 16 * 1024))
            .into_iter()
            .filter_map(|line| {
                let mut fields = line.split('\t');
                let name = fields.next()?.to_string();
                let school = match fields.next()? {
                    "school" => true,
                    "always" => false,
                    _ => return None,
                };
                let symbols = fields.next()?.parse().ok()?;
                Some(ModuleInfo {
                    name,
                    school,
                    symbols,
                })
            })
            .collect()
    }

    /// Replaces the enabled school modules with `names`, in priority order.
    /// Always-on modules are unaffected.
    pub fn set_modules(&self, names: &[String]) -> Result<(), String> {
        let csv = names.join(",");
        let csv = CString::new(csv).map_err(|_| "module name contains a NUL".to_string())?;
        // SAFETY: `csv` is a valid NUL-terminated UTF-8 string; the shim only
        // reads it and updates its own process-global module flags.
        unsafe {
            ipa2v_set_modules(csv.as_ptr());
        }
        Ok(())
    }

    /// Enabled school modules in enable (priority) order.
    #[allow(dead_code)]
    pub fn enabled_modules(&self) -> Vec<String> {
        lines(&self.text_call_no_input(ipa2v_enabled_modules, 16 * 1024))
    }

    pub fn table(&self) -> String {
        self.text_call_no_input(ipa2v_table, 256 * 1024)
    }

    pub fn stats(&self) -> String {
        self.text_call_no_input(ipa2v_stats, 16 * 1024)
    }

    pub fn weights_effective(&self) -> String {
        self.text_call_no_input(ipa2v_weights_effective, 16 * 1024)
    }

    pub fn dim_names(&self) -> Vec<String> {
        lines(&self.text_call_no_input(ipa2v_dim_names, 8 * 1024))
    }

    pub fn keyboard_consonants(&self) -> Vec<String> {
        lines(&self.text_call_no_input(ipa2v_kb_cons, 32 * 1024))
    }

    pub fn keyboard_non_pulmonic(&self) -> Vec<(String, i32)> {
        lines(&self.text_call_no_input(ipa2v_kb_cons_np, 16 * 1024))
            .into_iter()
            .filter_map(|line| {
                let mut parts = line.split('\t');
                let symbol = parts.next().unwrap_or_default().to_string();
                if symbol.is_empty() {
                    return None;
                }
                let class = parts
                    .next()
                    .and_then(|value| value.parse().ok())
                    .unwrap_or(4);
                Some((symbol, class))
            })
            .collect()
    }

    pub fn keyboard_vowels(&self) -> Vec<String> {
        lines(&self.text_call_no_input(ipa2v_kb_vowels, 16 * 1024))
    }

    pub fn keyboard_modifiers(&self) -> Vec<String> {
        lines(&self.text_call_no_input(ipa2v_kb_mods, 32 * 1024))
    }

    pub fn keyboard_tones(&self) -> Vec<String> {
        lines(&self.text_call_no_input(ipa2v_kb_tones, 16 * 1024))
    }

    pub fn vowel_positions(&self) -> Vec<VowelKey> {
        lines(&self.text_call_no_input(ipa2v_vowel_positions, 16 * 1024))
            .into_iter()
            .filter_map(|line| {
                let mut fields = line.split('\t');
                let symbol = fields.next()?.to_string();
                let row = fields.next()?.parse().ok()?;
                let column = fields.next()?.parse().ok()?;
                Some(VowelKey {
                    symbol,
                    row,
                    column,
                })
            })
            .collect()
    }

    pub fn consonant_positions(&self) -> Vec<ConsonantKey> {
        lines(&self.text_call_no_input(ipa2v_kb_cons_pos, 32 * 1024))
            .into_iter()
            .filter_map(|line| {
                let mut fields = line.split('\t');
                let symbol = fields.next()?.to_string();
                let place = fields.next()?.parse().ok()?;
                Some(ConsonantKey { symbol, place })
            })
            .collect()
    }

    pub fn modifier_tiers(&self) -> Vec<(String, i32)> {
        lines(&self.text_call_no_input(ipa2v_kb_mod_tiers, 32 * 1024))
            .into_iter()
            .filter_map(|line| {
                let mut fields = line.split('\t');
                let symbol = fields.next()?.to_string();
                let tier = fields.next()?.parse().ok()?;
                Some((symbol, tier))
            })
            .collect()
    }

    fn text_call(
        &self,
        text: &str,
        function: unsafe extern "C" fn(*const c_char, *mut c_char, usize) -> c_int,
        size: usize,
    ) -> String {
        let Ok(text) = CString::new(text) else {
            return "input contains a NUL byte".to_string();
        };
        let mut out = vec![0u8; size];
        // SAFETY: the input and output buffers are valid for the call.
        unsafe {
            function(text.as_ptr(), out.as_mut_ptr().cast(), out.len());
        }
        c_string(&out)
    }

    fn text_call_no_input(
        &self,
        function: unsafe extern "C" fn(*mut c_char, usize) -> c_int,
        size: usize,
    ) -> String {
        let mut out = vec![0u8; size];
        // SAFETY: the output buffer is valid for the call.
        unsafe {
            function(out.as_mut_ptr().cast(), out.len());
        }
        c_string(&out)
    }
}

fn c_string(bytes: &[u8]) -> String {
    let end = bytes
        .iter()
        .position(|&byte| byte == 0)
        .unwrap_or(bytes.len());
    String::from_utf8_lossy(&bytes[..end])
        .trim_end()
        .to_string()
}

fn lines(text: &str) -> Vec<String> {
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(str::to_string)
        .collect()
}

/// Splits a `query` result into the feature name and the airstream or tier
/// line, matching the two content rows of the hover card.
pub fn describe_query(raw: &str) -> (String, String) {
    let line = raw.lines().next().unwrap_or_default().trim();

    if let Some(rest) = line.strip_prefix("modifier:") {
        let mut parts = rest
            .split("  ")
            .map(str::trim)
            .filter(|part| !part.is_empty());
        let _glyph = parts.next();
        let name = parts.next().unwrap_or_default().to_string();
        let air = parts.collect::<Vec<_>>().join("  ");
        return (name, air);
    }

    let mut name = line.to_string();
    let mut air = String::new();
    if let (Some(open), Some(close)) = (line.rfind('('), line.rfind(')'))
        && close > open
    {
        air = line[open + 1..close].trim().to_string();
        name.replace_range(open..=close, "");
    }

    let name = name.trim();
    let name = name
        .strip_prefix("extIPA base:")
        .or_else(|| name.strip_prefix("base:"))
        .or_else(|| name.strip_prefix("alias:"))
        .unwrap_or(name)
        .trim();
    let name = if let Some(rest) = name.strip_prefix('/') {
        rest.find('/')
            .map(|end| rest[end + 1..].trim().to_string())
            .unwrap_or_else(|| name.to_string())
    } else {
        name.to_string()
    };

    (name, air)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::sync::Mutex;

    static TEST_LOCK: Mutex<()> = Mutex::new(());

    fn guard() -> std::sync::MutexGuard<'static, ()> {
        TEST_LOCK
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    fn data(name: &str) -> String {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .join("tools/data")
            .join(name)
            .to_string_lossy()
            .into_owned()
    }

    #[test]
    fn query_text_splits_into_name_and_airstream() {
        assert_eq!(
            describe_query("base: /k/  voiceless velar plosive  (pulmonic)\n  (-0.9, 0.1)"),
            (
                "voiceless velar plosive".to_string(),
                "pulmonic".to_string()
            )
        );
        assert_eq!(
            describe_query("modifier: \u{0303}  nasal  tier=5"),
            ("nasal".to_string(), "tier=5".to_string())
        );
        assert_eq!(
            describe_query("extIPA base: /\u{02e1}/  epiglottal plosive  (egressive)"),
            ("epiglottal plosive".to_string(), "egressive".to_string())
        );
        assert_eq!(
            describe_query("alias: \u{0261} -> g"),
            ("\u{0261} -> g".to_string(), String::new())
        );
        assert_eq!(
            describe_query("no entry for: Q"),
            ("no entry for: Q".to_string(), String::new())
        );
    }

    #[test]
    fn engine_contract() {
        let _guard = guard();
        let mut engine = Engine::new();
        engine
            .set_args(&["-D", &data("spec_next.scheme")])
            .expect("default scheme");
        assert_eq!(engine.ndim(), 16);

        let segments = engine.forward("sa").expect("forward");
        assert_eq!(segments.len(), 2);
        assert_eq!(segments[0].values.len(), 16);
        assert_eq!(segments[0].airstream_label(), "pulmonic");

        let reverse = engine.reverse(&segments[0].values).expect("reverse");
        assert!(reverse.contains("->"), "{reverse}");

        assert!(engine.query("t").unwrap().contains("base:"));
        assert!(engine.distance("t", "d").unwrap() > 0.0);
        assert!(engine.align("ta", "ta").is_ok());
        assert!(engine.ir("t").contains("layer1"));
        assert!(engine.json("t").contains("\"segments\""));
        let toned = engine
            .forward_with_tone("ma\u{02e9}\u{02e8}")
            .expect("tone");
        assert_eq!(toned.len(), 2);
        assert!(toned[1].tones.iter().any(|group| group.kind != 0));
        assert!(!engine.version().is_empty());
        assert!(engine.docs().contains("vec4ipa"));
        assert!(engine.modules_full().contains("["));
        assert!(engine.table().contains("pulmonic"));
        assert!(engine.stats().contains("dimensions"));
        assert!(engine.weights_effective().contains("lambda"));
        assert_eq!(engine.dim_names().len(), 16);
        assert!(!engine.keyboard_consonants().is_empty());
        assert!(!engine.keyboard_non_pulmonic().is_empty());
        assert!(!engine.keyboard_vowels().is_empty());
        assert!(!engine.keyboard_modifiers().is_empty());
        assert!(!engine.keyboard_tones().is_empty());
        assert!(
            engine
                .keyboard_non_pulmonic()
                .iter()
                .all(|(_, class)| (0..=4).contains(class))
        );
        for symbol in engine
            .keyboard_consonants()
            .into_iter()
            .chain(
                engine
                    .keyboard_non_pulmonic()
                    .into_iter()
                    .map(|(symbol, _)| symbol),
            )
            .chain(engine.keyboard_vowels())
            .chain(engine.keyboard_modifiers())
            .chain(engine.keyboard_tones())
        {
            assert!(!symbol.is_empty(), "empty keyboard label");
            assert!(
                !symbol.contains('\t'),
                "keyboard label kept its data suffix: {symbol:?}"
            );
        }
        assert!(!engine.vowel_positions().is_empty());
        assert!(!engine.consonant_positions().is_empty());
        assert!(!engine.modifier_tiers().is_empty());

        let base = std::env::temp_dir().join("vec4ipa-ir-test");
        engine
            .ir_export("t", &base.to_string_lossy())
            .expect("ir export");
        assert!(base.with_extension("layer1").exists());
        assert!(base.with_extension("layer2").exists());
        let _ = std::fs::remove_file(base.with_extension("layer1"));
        let _ = std::fs::remove_file(base.with_extension("layer2"));
    }

    #[test]
    fn module_inventory_and_exact_set_round_trip() {
        let _guard = guard();
        let mut engine = Engine::new();
        engine
            .set_args(&["-D", &data("spec_next.scheme")])
            .expect("default scheme");

        let modules = engine.modules_all();
        assert!(
            modules
                .iter()
                .any(|module| module.name == "generic" && !module.school)
        );
        assert!(
            modules
                .iter()
                .any(|module| module.name == "americanist" && module.school && module.symbols > 0)
        );

        engine.set_modules(&[]).expect("clear modules");
        assert!(engine.enabled_modules().is_empty());

        engine
            .set_modules(&["americanist".into(), "sinologist".into()])
            .expect("set modules");
        assert_eq!(
            engine.enabled_modules(),
            vec!["americanist".to_string(), "sinologist".to_string()]
        );

        // Always-on modules are not part of the toggleable set.
        engine.set_modules(&["generic".into()]).expect("set always");
        assert!(engine.enabled_modules().is_empty());

        engine.set_modules(&[]).expect("reset modules");
    }

    #[test]
    fn runtime_width_and_sequential_scheme_switch() {
        let _guard = guard();
        let mut engine = Engine::new();
        let tongue = data("tongue.scheme");
        engine
            .set_args(&["-D", &tongue])
            .expect("set tongue scheme");
        assert_eq!(engine.ndim(), 18);
        let segments = engine.forward("t").expect("forward tongue");
        assert_eq!(segments.len(), 1);
        assert_eq!(segments[0].values.len(), 18);
        assert!(engine.dim_names().contains(&"constriction_pos".to_string()));
        assert!(engine.dim_names().contains(&"constriction_gap".to_string()));
        assert!(engine.reverse(&segments[0].values).is_ok());

        let default = data("spec_next.scheme");
        engine
            .set_args(&["-D", &default])
            .expect("set default scheme");
        assert_eq!(engine.ndim(), 16);
        assert_eq!(
            engine.forward("t").expect("forward default")[0]
                .values
                .len(),
            16
        );
    }

    #[test]
    fn non_ascii_scheme_path() {
        let _guard = guard();
        let mut engine = Engine::new();
        let source = data("tongue.scheme");
        let target = std::env::temp_dir().join("vec4ipa-声调.scheme");
        std::fs::copy(&source, &target).expect("copy scheme");
        engine
            .set_args(&["-D", &target.to_string_lossy()])
            .expect("set non-ASCII scheme");
        assert_eq!(engine.ndim(), 18);
        let _ = std::fs::remove_file(target);
        engine
            .set_args(&["-D", &data("spec_next.scheme")])
            .expect("restore default scheme");
    }

    #[test]
    fn rejects_non_finite_and_bad_metric() {
        let _guard = guard();
        let engine = Engine::new();
        let vector = vec![f64::NAN; engine.ndim()];
        assert!(engine.reverse(&vector).is_err());

        let bad = std::env::temp_dir().join("vec4ipa-bad-metric.json");
        std::fs::write(&bad, r#"{"weights":[1,2,3],"lambda":1}"#).expect("write metric");
        assert!(engine.load_metric(&bad.to_string_lossy()).is_err());
        let _ = std::fs::remove_file(bad);
    }

    #[test]
    fn rejects_too_many_segments() {
        let _guard = guard();
        let engine = Engine::new();
        let input = "t".repeat(300);
        let error = engine.forward(&input).expect_err("segment limit");
        assert!(error.contains("too many"), "{error}");
    }

    #[test]
    fn parity_with_cli() {
        let _guard = guard();
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let vec4ipa = root.join("vec4ipa.exe");
        let vec2ipa = root.join("vec2ipa.exe");
        if !vec4ipa.exists() || !vec2ipa.exists() {
            eprintln!("SKIP: CLI binaries not built; run `make vec4ipa vec2ipa`");
            return;
        }

        let mut engine = Engine::new();
        for scheme in ["spec_next.scheme", "tongue.scheme"] {
            let path = data(scheme);
            engine.set_args(&["-D", path.as_str()]).expect("set scheme");
            let engine_rows = engine.forward("sa").expect("engine forward");
            let cli_rows = run_cli_forward(&vec4ipa, &path, "sa");
            assert_eq!(engine_rows.len(), cli_rows.len(), "{scheme}");
            for (row, (engine_row, cli_row)) in engine_rows.iter().zip(cli_rows).enumerate() {
                assert_eq!(engine_row.values.len(), cli_row.len(), "{scheme} row {row}");
                for (axis, (a, b)) in engine_row.values.iter().zip(cli_row).enumerate() {
                    assert!(
                        (a - b).abs() <= 5e-4,
                        "{scheme} row {row} axis {axis}: rust {a}, cli {b}"
                    );
                }
            }

            let vector = engine_rows[0]
                .values
                .iter()
                .map(|value| value.to_string())
                .collect::<Vec<_>>()
                .join(",");
            let cli_reverse = std::process::Command::new(&vec2ipa)
                .args(["-D", &path, &vector])
                .output()
                .expect("run vec2ipa");
            assert!(cli_reverse.status.success(), "{scheme}: vec2ipa failed");
            let cli_text = String::from_utf8_lossy(&cli_reverse.stdout);
            let engine_text = engine
                .reverse(&engine_rows[0].values)
                .expect("engine reverse");
            let cli_d = cli_text
                .split("d=")
                .nth(1)
                .and_then(|rest| rest.split_whitespace().next().map(str::to_string));
            let engine_d = engine_text
                .split("d=")
                .nth(1)
                .and_then(|rest| rest.split_whitespace().next().map(str::to_string));
            assert_eq!(engine_d, cli_d, "{scheme}: reverse distance");
        }
    }

    fn run_cli_forward(exe: &std::path::Path, scheme: &str, text: &str) -> Vec<Vec<f64>> {
        let output = std::process::Command::new(exe)
            .args(["-D", scheme, text])
            .output()
            .expect("run vec4ipa");
        assert!(output.status.success());
        String::from_utf8_lossy(&output.stdout)
            .lines()
            .filter_map(|line| {
                let start = line.find('(')?;
                let end = line[start..].find(')')?;
                let values = &line[start + 1..start + end];
                values
                    .split(',')
                    .map(|value| value.trim().parse::<f64>().ok())
                    .collect::<Option<Vec<_>>>()
            })
            .collect()
    }
}
