use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    windows_reactor_setup::as_self_contained();

    embed_resource::compile("app.rc", embed_resource::NONE)
        .manifest_required()
        .expect("embed the application icon");

    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let root = manifest.join("../..");

    let vectors = root.join("src/vectors.h");
    let readme = root.join("src/readme_embed.h");

    if needs_regen(
        &vectors,
        &[
            root.join("tools/data/spec_next.scheme"),
            root.join("src/names.tsv"),
            root.join("tools/gen_vectors_h.py"),
        ],
    ) {
        run_python(
            &root,
            &[
                "tools/gen_vectors_h.py",
                "--scheme",
                "tools/data/spec_next.scheme",
            ],
        );
    }

    if needs_regen(
        &readme,
        &[
            root.join("README.md"),
            root.join("tools/gen_readme_embed.py"),
        ],
    ) {
        run_python(&root, &["tools/gen_readme_embed.py"]);
    }

    for path in [
        "src/vectors.h",
        "src/readme_embed.h",
        "src/ipa2vec_core.h",
        "src/tongue_contour.h",
        "tools/data/spec_next.scheme",
        "src/names.tsv",
        "README.md",
        "ui/winui/core_wrap.c",
    ] {
        println!("cargo:rerun-if-changed={}", root.join(path).display());
    }

    let shim = fs::read_to_string(manifest.join("../winui/core_wrap.c"))
        .expect("read ui/winui/core_wrap.c");
    let mut shim = shim
        .replace("\r\n", "\n")
        .replace("#include \"../src/", "#include \"");

    // MSVC has no GCC nested functions. Hoist the one nested helper in
    // ipa2v_kb_cons_pos so the same shim compiles with cl.exe.
    let nested = r#"    double norm(const double v[MAXDIM])
    {
        double p = (v[place] + 0.9) / 1.8;   /* lips -0.9 .. glottis +0.9 -> 0..1 */
        return p < 0.0 ? 0.0 : (p > 1.0 ? 1.0 : p);
    }
"#;
    shim = shim.replace(nested, "");

    let helper = r#"static double kb_cons_norm(int place, const double v[MAXDIM])
{
    double p = (v[place] + 0.9) / 1.8;
    return p < 0.0 ? 0.0 : (p > 1.0 ? 1.0 : p);
}

"#;
    shim = shim.replace(
        "EXPORT int ipa2v_kb_cons_pos",
        &format!("{helper}EXPORT int ipa2v_kb_cons_pos"),
    );
    shim = shim.replace(
        "norm(SEG_TABLE[i].v)",
        "kb_cons_norm(place, SEG_TABLE[i].v)",
    );
    shim = shim.replace(
        "norm(EXTRA_BASE[i].v)",
        "kb_cons_norm(place, EXTRA_BASE[i].v)",
    );

    let out_dir = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    let shim_path = out_dir.join("core_wrap.c");
    fs::write(&shim_path, shim).expect("write adjusted core_wrap.c");

    cc::Build::new()
        .file(shim_path)
        .include(root.join("src"))
        .define("_CRT_SECURE_NO_WARNINGS", None)
        .define("_CRT_NONSTDC_NO_DEPRECATE", None)
        .flag_if_supported("/utf-8")
        .flag_if_supported("-Wno-unused-function")
        .flag_if_supported("-Wno-unused-variable")
        .flag_if_supported("-Wno-format-truncation")
        .compile("ipa2vec_core");
}

fn needs_regen(output: &Path, inputs: &[PathBuf]) -> bool {
    let Ok(output_time) = fs::metadata(output).and_then(|m| m.modified()) else {
        return true;
    };
    inputs.iter().any(|input| {
        fs::metadata(input)
            .and_then(|m| m.modified())
            .map_or(true, |time| time > output_time)
    })
}

fn run_python(root: &Path, args: &[&str]) {
    for (program, prefix) in [("python", None), ("py", Some("-3"))] {
        let mut command = Command::new(program);
        if let Some(prefix) = prefix {
            command.arg(prefix);
        }
        command.args(args).current_dir(root);
        if command.status().is_ok_and(|status| status.success()) {
            return;
        }
    }
    panic!(
        "could not generate C headers: Python 3 is required. \
         Run `make gen` from the repository root, or install Python."
    );
}
