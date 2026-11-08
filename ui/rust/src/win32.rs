use std::path::{Path, PathBuf};

use windows_sys::Win32::Foundation::HWND;
use windows_sys::Win32::Graphics::Gdi::{AddFontResourceExW, FR_PRIVATE};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    GetForegroundWindow, HWND_NOTOPMOST, HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SetWindowPos,
};

pub fn set_always_on_top(on: bool) -> bool {
    let hwnd: HWND = unsafe { GetForegroundWindow() };
    if hwnd.is_null() {
        return false;
    }
    let insert_after = if on { HWND_TOPMOST } else { HWND_NOTOPMOST };
    unsafe { SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE) != 0 }
}

pub fn load_private_font(path: &Path) -> bool {
    let Some(path) = path.to_str() else {
        return false;
    };
    let wide = path
        .encode_utf16()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    unsafe { AddFontResourceExW(wide.as_ptr(), FR_PRIVATE, std::ptr::null()) != 0 }
}

pub fn bundled_font() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../fonts/GentiumBookPlus-Regular.ttf")
}

pub fn copy_tools(destination: &Path) -> Result<usize, String> {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| PathBuf::from("."));
    let sources = [
        exe_dir.join("tools"),
        exe_dir.clone(),
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."),
    ];
    std::fs::create_dir_all(destination)
        .map_err(|error| format!("create {}: {error}", destination.display()))?;
    let mut copied = 0;
    for name in ["ipa2vec.exe", "vec2ipa.exe", "vec4ipa.exe"] {
        let Some(source) = sources
            .iter()
            .map(|dir| dir.join(name))
            .find(|path| path.exists())
        else {
            return Err(format!("bundled tool not found: {name}"));
        };
        let target = destination.join(name);
        std::fs::copy(&source, &target)
            .map_err(|error| format!("copy {}: {error}", source.display()))?;
        copied += 1;
    }
    Ok(copied)
}
