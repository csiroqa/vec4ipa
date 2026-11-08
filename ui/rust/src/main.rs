mod app;
mod engine;
mod layout;
mod settings;
mod startup;
mod win32;

use windows_reactor::*;

fn log_runtime_error(kind: &str, detail: &str) {
    let dir = std::env::temp_dir().join("vec4ipa");
    let _ = std::fs::create_dir_all(&dir);
    let _ = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("rust-crash.log"))
        .and_then(|mut file| {
            use std::io::Write;
            writeln!(file, "{kind}: {detail}")
        });
}

fn main() {
    std::panic::set_hook(Box::new(|info| {
        log_runtime_error("panic", &info.to_string());
        eprintln!("{info}");
    }));

    if std::env::args().any(|arg| arg == "--engine-smoke") {
        println!("ndim={}", engine::Engine::new().ndim());
        return;
    }

    let startup = startup::Startup::parse();
    if startup.help {
        print!("{}", startup::Startup::help_text());
        return;
    }
    if startup.version {
        let engine = engine::Engine::new();
        println!("vec4ipa_ui {} ({} D)", engine.version(), engine.ndim());
        return;
    }

    if let Err(error) = App::run_component::<app::Workbench>(startup) {
        log_runtime_error("app", &format!("{error:?}"));
    }
}
