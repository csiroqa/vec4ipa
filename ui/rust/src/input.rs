//! Sends IPA text to the foreground application.

use windows_sys::Win32::System::DataExchange::{
    CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData,
};
use windows_sys::Win32::System::Memory::{GMEM_MOVEABLE, GlobalAlloc, GlobalLock, GlobalUnlock};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, SendInput,
    VK_CONTROL, VK_V,
};

pub enum Delivery {
    Sent,
    Clipboard,
    Failed(String),
}

const CF_UNICODETEXT: u32 = 13;

pub fn inject(text: &str) -> Delivery {
    deliver(text, send_unicode, set_clipboard, send_ctrl_v)
}

fn deliver(
    text: &str,
    send: impl Fn(&[u16]) -> usize,
    clipboard: impl Fn(&str) -> bool,
    paste: impl Fn() -> bool,
) -> Delivery {
    let units = utf16_units(text);
    let expected = units.len() * 2;
    let sent = send(&units);
    if expected > 0 && sent == expected {
        return Delivery::Sent;
    }
    if clipboard(text) && paste() {
        return Delivery::Clipboard;
    }
    Delivery::Failed("Input was rejected.".to_string())
}

pub fn utf16_units(text: &str) -> Vec<u16> {
    text.encode_utf16().collect()
}

fn key_event(scan: u16, flags: u32) -> INPUT {
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: 0,
                wScan: scan,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    }
}

fn virtual_key(vk: u16, up: bool) -> INPUT {
    let mut event = key_event(0, if up { KEYEVENTF_KEYUP } else { 0 });
    event.Anonymous.ki.wVk = vk;
    event
}

fn send_unicode(units: &[u16]) -> usize {
    let mut events = Vec::with_capacity(units.len() * 2);
    for unit in units {
        events.push(key_event(*unit, KEYEVENTF_UNICODE));
        events.push(key_event(*unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP));
    }
    if events.is_empty() {
        return 0;
    }
    let size = std::mem::size_of::<INPUT>() as i32;
    unsafe { SendInput(events.len() as u32, events.as_ptr(), size) as usize }
}

fn send_ctrl_v() -> bool {
    let events = [
        virtual_key(VK_CONTROL, false),
        virtual_key(VK_V, false),
        virtual_key(VK_V, true),
        virtual_key(VK_CONTROL, true),
    ];
    let size = std::mem::size_of::<INPUT>() as i32;
    unsafe { SendInput(events.len() as u32, events.as_ptr(), size) as usize == events.len() }
}

fn set_clipboard(text: &str) -> bool {
    let wide = utf16_units(text)
        .into_iter()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    let bytes = wide.len() * std::mem::size_of::<u16>();
    unsafe {
        if OpenClipboard(std::ptr::null_mut()) == 0 {
            return false;
        }
        let _ = EmptyClipboard();
        let handle = GlobalAlloc(GMEM_MOVEABLE, bytes);
        if handle.is_null() {
            let _ = CloseClipboard();
            return false;
        }
        let target = GlobalLock(handle).cast::<u16>();
        if target.is_null() {
            let _ = CloseClipboard();
            return false;
        }
        std::ptr::copy_nonoverlapping(wide.as_ptr(), target, wide.len());
        let _ = GlobalUnlock(handle);
        let stored = !SetClipboardData(CF_UNICODETEXT, handle).is_null();
        let _ = CloseClipboard();
        stored
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encodes_bmp_text_one_unit_per_scalar() {
        assert_eq!(utf16_units("ʃa"), vec![0x0283, 0x0061]);
    }

    #[test]
    fn encodes_supplementary_text_as_a_surrogate_pair() {
        let units = utf16_units("\u{1D158}");
        assert_eq!(units.len(), 2);
        assert!((0xD800..=0xDBFF).contains(&units[0]));
        assert!((0xDC00..=0xDFFF).contains(&units[1]));
    }

    #[test]
    fn sends_when_every_event_lands() {
        let delivery = deliver("ʃ", |units| units.len() * 2, |_| false, || false);
        assert!(matches!(delivery, Delivery::Sent));
    }

    #[test]
    fn falls_back_to_the_clipboard_when_send_is_rejected() {
        let delivery = deliver("ʃ", |_| 0, |_| true, || true);
        assert!(matches!(delivery, Delivery::Clipboard));
    }

    #[test]
    fn reports_rejection_when_both_transports_fail() {
        let delivery = deliver("ʃ", |_| 0, |_| false, || false);
        assert!(matches!(delivery, Delivery::Failed(_)));
    }
}
