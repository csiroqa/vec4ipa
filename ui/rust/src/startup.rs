use crate::settings::ThemeChoice;

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Startup {
    pub input: Option<String>,
    pub reverse: Option<String>,
    pub query: Option<String>,
    pub narrowness: u8,
    pub theme: Option<ThemeChoice>,
    pub export_tools: Option<String>,
    pub scheme: Option<String>,
    pub metric: Option<String>,
    pub help: bool,
    pub version: bool,
}

impl Startup {
    pub fn parse() -> Self {
        let mut startup = Self {
            narrowness: 3,
            ..Self::default()
        };
        let args = std::env::args().skip(1).collect::<Vec<_>>();
        let mut index = 0;
        while index < args.len() {
            let arg = args[index].as_str();
            match arg {
                "-h" | "--help" => startup.help = true,
                "-v" | "--version" => startup.version = true,
                "-q" | "--query" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.query = Some(value.clone());
                        index += 1;
                    }
                }
                "-r" | "--reverse" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.reverse = Some(value.clone());
                        index += 1;
                    }
                }
                "-N" | "--narrowness" | "--width" => {
                    if let Some(value) = args.get(index + 1).and_then(|v| v.parse::<u8>().ok()) {
                        startup.narrowness = value.min(4);
                        index += 1;
                    }
                }
                "--theme" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.theme = match value.as_str() {
                            "light" => Some(ThemeChoice::Light),
                            "dark" => Some(ThemeChoice::Dark),
                            _ => Some(ThemeChoice::System),
                        };
                        index += 1;
                    }
                }
                "--export-tools" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.export_tools = Some(value.clone());
                        index += 1;
                    }
                }
                "-D" | "--scheme" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.scheme = Some(value.clone());
                        index += 1;
                    }
                }
                "-M" | "--metric" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.metric = Some(value.clone());
                        index += 1;
                    }
                }
                "--" => {
                    if let Some(value) = args.get(index + 1) {
                        startup.input = Some(value.clone());
                    }
                    break;
                }
                value if !value.starts_with('-') && startup.input.is_none() => {
                    startup.input = Some(value.to_string());
                }
                _ => {}
            }
            index += 1;
        }
        startup
    }

    pub fn help_text() -> &'static str {
        "vec4ipa_ui [OPTIONS] [IPA-STRING]\n\
         \n\
         --narrowness LEVEL  reverse fit width: broadest|broad|medium|narrow|narrowest (0-4)\n\
         --theme NAME        system|light|dark\n\
         -q, --query SYM     query one symbol on startup\n\
         -r, --reverse VEC   16-D vector -> IPA on startup\n\
         -D, --scheme FILE   load a custom dimension scheme\n\
         -M, --metric FILE   load metric weights and lambda\n\
         --export-tools DIR  write the bundled CLI tools to DIR\n\
         -h, --help          show this help\n\
         -v, --version       show the suite version\n"
    }
}

pub fn is_combining_mark(ch: char) -> bool {
    matches!(
        ch as u32,
        0x0300..=0x036F
            | 0x0483..=0x0489
            | 0x1AB0..=0x1AFF
            | 0x1DC0..=0x1DFF
            | 0x20D0..=0x20FF
            | 0xFE20..=0xFE2F
    )
}

pub fn is_modifier_symbol(symbol: &str) -> bool {
    let mut chars = symbol.chars().filter(|ch| *ch != '\u{25cc}');
    let Some(first) = chars.next() else {
        return false;
    };
    is_combining_mark(first) || chars.next().is_some_and(is_combining_mark)
}
