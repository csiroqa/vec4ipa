/*
 * ipa2vec_ui — single-file Win32 GUI for the vec4ipa tool suite.
 *
 * All logic (lex / canonicalise / layer2 / reverse fit / query) comes
 * from ../src/ipa2vec_core.h (header-only; src/ is not modified), so
 * the GUI is self-contained: no subprocess, no temp files.
 *
 * Features:
 *   - IPA string -> 16-D vectors (forward)
 *   - 16-D vector -> IPA (reverse fit, --width 0-4)
 *   - symbol query (base / extIPA / modifier / alias)
 *   - IPA on-screen keyboard (consonants / vowels / modifiers / tones)
 *   - File > Export command lines...  (copy / save .bat)
 *   - File > Export tools...         (embedded CLI executables)
 *   - Help > Documentation (embedded README), Help > About
 *
 * Fonts: Gentium Book Plus (text) + NewComputerModern10 (icon) are
 * bundled in ui/fonts/ (OFL) and loaded privately at startup.
 *
 * Build (ui/):
 *   windres app.rc -O coff -o app.res
 *   gcc -O2 -municode -mwindows -I../src -o ipa2vec_ui.exe \
 *       ipa2vec_ui.c app.res -lcomctl32 -lcomdlg32 -lshlwapi -lshell32 -lole32
 */

#ifndef _WIN32
#define UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <windowsx.h>
#include <commctrl.h>
#include <commdlg.h>
#include <shlwapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "../src/ipa2vec_core.h"
#include "../src/readme_embed.h"

#define APP_NAME      L"IPA2Vector Workbench"
#define APP_VERSION   L"0.2.0"

/* control ids */
#define IDC_INFO_EDIT 1001
#define IDC_EXPORT_TEXT 2001
#define IDC_EXPORT_COPY 2002
#define IDC_EXPORT_SAVE 2003
#define IDC_EXPORT_CLOSE 2004

#define ID_FILE_EXPORT 4001
#define ID_FILE_EXIT   4002
#define ID_HELP_ABOUT  4003
#define ID_FILE_EXPORT_TOOLS 4004
#define ID_HELP_DOCS   4005

#define IDI_APP        101

#define IDR_TOOL_IPA2VEC 201
#define IDR_TOOL_VEC2IPA 202
#define IDR_TOOL_VEC4IPA 203

/* main-window controls */
#define IDC_IPA_IN    5001
#define IDC_VEC_IN    5002
#define IDC_Q_IN      5003
#define IDC_BTN_FWD   5004
#define IDC_BTN_REV   5005
#define IDC_BTN_QUERY 5006
#define IDC_COMBO_W   5007
#define IDC_OUT       5008
#define IDC_TABS      5009
#define IDC_PANE_CONS 5010
#define IDC_PANE_VOW  5011
#define IDC_PANE_MOD  5012
#define IDC_PANE_TONE 5013

/* keyboard button id ranges */
#define IDB_BASE   6000
#define IDB_EXTRA  7000
#define IDB_MOD    8000
#define IDB_TONE   9000
#define IDB_MAX    10000

static HFONT g_font = NULL;        /* Gentium (UI text + IPA) */
static HFONT g_font_btn = NULL;    /* smaller for keyboard buttons */
static HWND g_hStatus = NULL;

static const wchar_t *g_btn_sym[IDB_MAX - IDB_BASE]; /* symbol per button id */
static wchar_t g_ipa_buf[4096];

/* ------------------------------------------------------------------ */
/* helpers                                                            */
/* ------------------------------------------------------------------ */

static wchar_t *utf8_to_wide(const char *s, wchar_t *buf, size_t cap)
{
    if (!s) return NULL;
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, buf, (int)cap);
    if (n <= 0) buf[0] = L'\0';
    return buf;
}

static void out_append(HWND out, const char *utf8)
{
    wchar_t buf[8192];
    utf8_to_wide(utf8, buf, 8192);
    size_t len = wcslen(buf);
    if (len && buf[len - 1] != L'\n')
        wcscat(buf, L"\r\n");
    int n = GetWindowTextLengthW(out);
    SendMessageW(out, EM_SETSEL, n, n);
    SendMessageW(out, EM_REPLACESEL, FALSE, (LPARAM)buf);
}

static void out_header(HWND out, const wchar_t *title)
{
    wchar_t buf[512];
    swprintf(buf, 512, L"\r\n=== %s ===\r\n", title);
    int n = GetWindowTextLengthW(out);
    SendMessageW(out, EM_SETSEL, n, n);
    SendMessageW(out, EM_REPLACESEL, FALSE, (LPARAM)buf);
}

/* ------------------------------------------------------------------ */
/* core operations (identical values to the CLI tools)                 */
/* ------------------------------------------------------------------ */

static void do_forward(HWND out, const char *str)
{
    ParseOut po;
    char err[256];
    if (lex(str, po.layer1, &po.n1, err, sizeof(err))) {
        out_append(out, "parse error: ");
        out_append(out, err);
        return;
    }
    canonicalise(po.layer1, po.n1, po.layer2, &po.n2);
    apply_layer2(po.layer2, po.n2, po.segs, &po.nsegs);

    for (int s = 0; s < po.nsegs; s++) {
        char line[512];
        snprintf(line, sizeof(line), "[%d] (", s);
        for (int i = 0; i < NDIM; i++) {
            char num[32];
            snprintf(num, sizeof(num), "%s%.4f", i ? ", " : "", po.segs[s].v[i]);
            strncat(line, num, sizeof(line) - strlen(line) - 1);
        }
        char tail[128];
        snprintf(tail, sizeof(tail), ")  %s%s%s",
                 AIRSTREAM_LABELS[po.segs[s].airstream],
                 po.segs[s].note[0] ? "  [" : "", po.segs[s].note);
        strncat(line, tail, sizeof(line) - strlen(line) - 1);
        out_append(out, line);
    }
}

static void do_reverse(HWND out, const char *vecstr)
{
    char buf[512];
    snprintf(buf, sizeof(buf), "%s", vecstr);
    double v[NDIM];
    char *tok = strtok(buf, ", \t");
    int i = 0;
    while (tok && i < NDIM) {
        char *endp = NULL;
        double x = strtod(tok, &endp);
        if (endp == tok) { out_append(out, "bad vector: numbers expected"); return; }
        v[i++] = x;
        tok = strtok(NULL, ", \t");
    }
    if (i != NDIM) {
        out_append(out, "bad vector: need 16 comma-separated values");
        return;
    }
    const SegEntry *b; double d;
    nearest_base(v, &b, &d);
    const ModRec *mods[IPA2VEC_FIT_MAX_MODS] = {0};
    int nm = fit_modifiers(v, b, mods);
    char ipa[128];
    build_ipa(b, mods, nm, ipa, sizeof(ipa));
    char line[256];
    snprintf(line, sizeof(line), "/%s/  (%s", b->ipa, base_name(b));
    for (int j = 0; j < nm; j++) {
        char m[64];
        snprintf(m, sizeof(m), " +%s", mods[j]->latin);
        strncat(line, m, sizeof(line) - strlen(line) - 1);
    }
    char tail[160];
    snprintf(tail, sizeof(tail), ")  d=%.4f  ->  /%s/", d, ipa);
    strncat(line, tail, sizeof(line) - strlen(line) - 1);
    out_append(out, line);
}

static void do_query(HWND out, const char *sym)
{
    for (int i = 0; i < NSEG; i++) {
        if (strcmp(SEG_TABLE[i].ipa, sym) == 0) {
            char line[512];
            snprintf(line, sizeof(line), "base: /%s/  %s  (%s)", SEG_TABLE[i].ipa,
                     NAME_TABLE[i], AIRSTREAM_LABELS[SEG_TABLE[i].airstream]);
            out_append(out, line);
            char v[512];
            snprintf(v, sizeof(v), "  (");
            for (int j = 0; j < NDIM; j++) {
                char num[32];
                snprintf(num, sizeof(num), "%s%.4f", j ? ", " : "", SEG_TABLE[i].v[j]);
                strncat(v, num, sizeof(v) - strlen(v) - 1);
            }
            strncat(v, ")", sizeof(v) - strlen(v) - 1);
            out_append(out, v);
            return;
        }
    }
    for (int i = 0; i < N_EXTRA; i++) {
        if (strcmp(EXTRA_BASE[i].ipa, sym) == 0) {
            char line[512];
            snprintf(line, sizeof(line), "extIPA base: /%s/  %s  (%s)",
                     EXTRA_BASE[i].ipa, EXTRA_NAMES[i],
                     AIRSTREAM_LABELS[EXTRA_BASE[i].airstream]);
            out_append(out, line);
            return;
        }
    }
    const unsigned char *u = (const unsigned char *)sym;
    unsigned long cp = 0;
    if (utf8_decode(u, &cp)) {
        const ModRec *m = find_mod(cp);
        if (m) {
            char line[256];
            snprintf(line, sizeof(line), "modifier: %s  %s  tier=%d%s%s",
                     m->ipa, m->latin, (int)m->tier,
                     m->air >= 0 ? "  [sets airstream]" : "",
                     m->infer ? "  [inference]" : "");
            out_append(out, line);
            return;
        }
    }
    const Alias *a = lookup_alias(sym, 0);
    if (a) {
        char line[256];
        snprintf(line, sizeof(line), "alias: %s -> %s%s%s", a->sym, a->repl,
                 a->note ? "  " : "", a->note ? a->note : "");
        out_append(out, line);
        return;
    }
    char line[128];
    snprintf(line, sizeof(line), "no entry for: %s", sym);
    out_append(out, line);
}

static void set_width(int level)
{
    static const int maxmods[5] = { 2, 3, 4, 6, 10 };
    static const double mingain[5] = { 0.25, 0.10, 0.04, 0.015, 0.001 };
    if (level < 0) level = 0;
    if (level > 4) level = 4;
    g_fit_max_mods = maxmods[level];
    g_fit_min_gain = mingain[level];
}

/* ------------------------------------------------------------------ */
/* keyboard construction                                              */
/* ------------------------------------------------------------------ */

/* add a keyboard button on pane; returns the button id */
static int kb_add(HWND pane, int id, const wchar_t *sym, int x, int y, int w, int h)
{
    CreateWindowW(L"BUTTON", sym,
        WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON | WS_TABSTOP,
        x, y, w, h, pane, (HMENU)(INT_PTR)id,
        GetModuleHandleW(NULL), NULL);
    SendMessageW(GetDlgItem(pane, id), WM_SETFONT, (WPARAM)g_font_btn, TRUE);
    if (id >= IDB_BASE && id < IDB_MAX)
        g_btn_sym[id - IDB_BASE] = sym;
    return id;
}

static int is_vowel(const SegEntry *e)
{
    return e->airstream == 1; /* AIRSTREAM_VWL */
}

static void build_consonant_pane(HWND pane)
{
    /* pulmonic + other consonants from SEG_TABLE (skip vowels), then EXTRA */
    static const int per_row = 8;
    int x0 = 4, y0 = 4, bw = 34, bh = 28, gap = 3;
    int x = x0, y = y0, n = 0;
    for (int i = 0; i < NSEG; i++) {
        if (is_vowel(&SEG_TABLE[i])) continue;
        wchar_t sym[8];
        utf8_to_wide(SEG_TABLE[i].ipa, sym, 8);
        kb_add(pane, IDB_BASE + i, sym, x, y, bw, bh);
        n++;
        if (n % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }
    x = x0; y += bh + 6;
    for (int i = 0; i < N_EXTRA; i++) {
        wchar_t sym[8];
        utf8_to_wide(EXTRA_BASE[i].ipa, sym, 8);
        kb_add(pane, IDB_EXTRA + i, sym, x, y, bw, bh);
        n++;
        if (n % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }
}

static void build_vowel_pane(HWND pane)
{
    /* vowel trapezium: rows = height (close..open), cols = position (front..back) */
    static const double pos_steps[8] = {0.0, 0.14, 0.28, 0.42, 0.56, 0.70, 0.84, 1.0};
    int x0 = 8, y0 = 6, bw = 36, bh = 30, gap = 4;
    int placed = 0;
    for (int i = 0; i < NSEG; i++) {
        if (!is_vowel(&SEG_TABLE[i])) continue;
        double tt = SEG_TABLE[i].v[2];   /* tt_pos: front..back */
        double th = SEG_TABLE[i].v[3];   /* tt_height: high..low */
        int col = 0;
        for (int c = 0; c < 8; c++)
            if (tt >= pos_steps[c]) col = c;
        int row = (int)((1.0 - th) * 4.0 + 0.5);
        if (row < 0) row = 0;
        if (row > 4) row = 4;
        int px = x0 + col * (bw + gap);
        int py = y0 + row * (bh + gap);
        wchar_t sym[8];
        utf8_to_wide(SEG_TABLE[i].ipa, sym, 8);
        kb_add(pane, IDB_BASE + i, sym, px, py, bw, bh);
        placed++;
    }
    (void)placed;
}

static void build_modifier_pane(HWND pane)
{
    static const int per_row = 7;
    int x0 = 4, y0 = 4, bw = 34, bh = 28, gap = 3;
    int x = x0, y = y0, n = 0;
    for (int i = 0; i < NMODS; i++) {
        wchar_t sym[8];
        utf8_to_wide(MODS[i].ipa, sym, 8);
        kb_add(pane, IDB_MOD + i, sym, x, y, bw, bh);
        n++;
        if (n % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }
}

static void build_tone_pane(HWND pane)
{
    /* tone letters, sandhi diacritics, arrows, digit superscripts, separators */
    static const wchar_t *tone_syms[] = {
        L"\u02E5", L"\u02E6", L"\u02E7", L"\u02E8", L"\u02E9",   /* ˥˦˧˨˩ */
        L"\uA712", L"\uA713", L"\uA714", L"\uA715", L"\uA716",   /* ꜒꜓꜔꜕꜖ */
        L"\u2197", L"\u2198", L"\uA71B", L"\uA71C",              /* ↗↘ꜛꜜ */
        L"\u2070", L"\u00B9", L"\u00B2", L"\u00B3", L"\u2074",   /* ⁰¹²³⁴ */
        L"\u2075", L"\u2076", L"\u2077", L"\u2078", L"\u2079",   /* ⁵⁶⁷⁸⁹ */
        L"\u203F", L" ",                                        /* ‿ space */
    };
    static const int per_row = 6;
    int x0 = 4, y0 = 4, bw = 36, bh = 30, gap = 3;
    int x = x0, y = y0;
    for (int i = 0; i < (int)(sizeof(tone_syms) / sizeof(tone_syms[0])); i++) {
        kb_add(pane, IDB_TONE + i, tone_syms[i], x, y, bw, bh);
        if ((i + 1) % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }
}

/* ------------------------------------------------------------------ */
/* command-line export (unchanged from previous build)                 */
/* ------------------------------------------------------------------ */

static void build_export_text(wchar_t *buf, size_t cap)
{
    wchar_t dir[MAX_PATH];
    GetCurrentDirectoryW(MAX_PATH, dir);

    swprintf(buf, cap,
        L"# IPA2Vector CLI commands (generated by %s)\r\n"
        L"# working directory: %s\r\n"
        L"\r\n"
        L":: ipa2vec  - IPA -> 16-D vectors (with IR + rebuilt demo)\r\n"
        L"\"D:\\2-OGP\\IPA2Vector\\ipa2vec.exe\" --width 3 -i \"\\\"\\u02c8t\\u02b0a\\\"\"\r\n"
        L"\r\n"
        L":: vec2ipa  - 16-D vector -> IPA (reverse fit)\r\n"
        L"\"D:\\2-OGP\\IPA2Vector\\vec2ipa.exe\" --width 3 \"0.0,0.0,0.55,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0,0.0,0.0,1.0\"\r\n"
        L"\r\n"
        L":: vec4ipa - inventory / query / reverse\r\n"
        L"\"D:\\2-OGP\\IPA2Vector\\vec4ipa.exe\" -q \u02b0\r\n"
        L"\"D:\\2-OGP\\IPA2Vector\\vec4ipa.exe\" --width 3 -r \"0.0,0.0,0.55,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0,0.0,0.0,1.0\"\r\n",
        APP_VERSION, dir);
}

static void copy_to_clipboard(HWND owner, const wchar_t *text)
{
    if (!OpenClipboard(owner)) return;
    EmptyClipboard();
    size_t n = (wcslen(text) + 1) * sizeof(wchar_t);
    HGLOBAL h = GlobalAlloc(GMEM_MOVEABLE, n);
    if (h) {
        wchar_t *dst = (wchar_t *)GlobalLock(h);
        wcscpy_s(dst, n / sizeof(wchar_t), text);
        GlobalUnlock(h);
        SetClipboardData(CF_UNICODETEXT, h);
    }
    CloseClipboard();
}

static void save_bat_dialog(HWND owner, const wchar_t *text)
{
    wchar_t path[MAX_PATH] = L"ipa2vec-commands.bat";
    OPENFILENAMEW ofn;
    ZeroMemory(&ofn, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = owner;
    ofn.lpstrFilter = L"Batch file (*.bat)\0*.bat\0All files (*.*)\0*.*\0";
    ofn.lpstrFile = path;
    ofn.nMaxFile = MAX_PATH;
    ofn.lpstrDefExt = L"bat";
    ofn.Flags = OFN_OVERWRITEPROMPT;
    if (!GetSaveFileNameW(&ofn)) return;

    FILE *f = _wfopen(path, L"w, ccs=UTF-8");
    if (!f) {
        MessageBoxW(owner, L"Could not write the file.", APP_NAME, MB_ICONERROR);
        return;
    }
    fwprintf(f, L"@echo off\r\n");
    fwprintf(f, L"%s\r\n", text);
    fclose(f);
    MessageBoxW(owner, path, L"Saved", MB_ICONINFORMATION);
}

static void export_embedded_tool(HINSTANCE hInst, const wchar_t *dir,
                                 int resid, const wchar_t *fname, int *ok,
                                 int *fail, int *missing)
{
    HRSRC hr = FindResourceW(hInst, MAKEINTRESOURCEW(resid), RT_RCDATA);
    if (!hr) { (*missing)++; return; }
    HGLOBAL hg = LoadResource(hInst, hr);
    void *p = LockResource(hg);
    DWORD sz = SizeofResource(hInst, hr);
    if (!p || sz == 0) { (*missing)++; return; }

    wchar_t path[MAX_PATH];
    swprintf(path, MAX_PATH, L"%s\\%s", dir, fname);
    HANDLE f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) { (*fail)++; return; }
    DWORD written = 0;
    BOOL okb = WriteFile(f, p, sz, &written, NULL);
    CloseHandle(f);
    if (okb && written == sz) (*ok)++;
    else (*fail)++;
}

static void export_tools_dialog(HWND owner)
{
    HINSTANCE hInst = GetModuleHandleW(NULL);
    wchar_t dir[MAX_PATH];
    BROWSEINFOW bi;
    ZeroMemory(&bi, sizeof(bi));
    bi.hwndOwner = owner;
    bi.lpszTitle = L"Choose a folder to export the CLI tools into";
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    PIDLIST_ABSOLUTE pidl = SHBrowseForFolderW(&bi);
    if (!pidl) return;
    if (!SHGetPathFromIDListW(pidl, dir)) { CoTaskMemFree(pidl); return; }
    CoTaskMemFree(pidl);

    int ok = 0, fail = 0, missing = 0;
    export_embedded_tool(hInst, dir, IDR_TOOL_IPA2VEC, L"ipa2vec.exe",
                         &ok, &fail, &missing);
    export_embedded_tool(hInst, dir, IDR_TOOL_VEC2IPA, L"vec2ipa.exe",
                         &ok, &fail, &missing);
    export_embedded_tool(hInst, dir, IDR_TOOL_VEC4IPA, L"vec4ipa.exe",
                         &ok, &fail, &missing);
    wchar_t msg[640];
    swprintf(msg, 640,
        L"Exported %d of 3 tools to:\r\n%s\r\n\r\n%s",
        ok, dir,
        fail ? L"Some files could not be written."
             : missing ? L"Some tools are not embedded in this build."
                       : L"All three CLI tools are ready to use.");
    MessageBoxW(owner, msg, L"Export tools", MB_ICONINFORMATION);
}

/* ------------------------------------------------------------------ */
/* export dialog                                                      */
/* ------------------------------------------------------------------ */

static HWND g_dlg = NULL;
static WNDPROC g_dlg_proc = NULL;

static LRESULT CALLBACK export_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CREATE: {
        wchar_t text[2048];
        build_export_text(text, 2048);

        CreateWindowW(L"BUTTON", L"&Copy to clipboard",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            12, 10, 130, 26, hwnd, (HMENU)IDC_EXPORT_COPY,
            GetModuleHandleW(NULL), NULL);
        CreateWindowW(L"BUTTON", L"&Save as .bat",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            150, 10, 120, 26, hwnd, (HMENU)IDC_EXPORT_SAVE,
            GetModuleHandleW(NULL), NULL);
        CreateWindowW(L"BUTTON", L"&Close",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            280, 10, 90, 26, hwnd, (HMENU)IDC_EXPORT_CLOSE,
            GetModuleHandleW(NULL), NULL);

        HWND ed = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_AUTOVSCROLL |
            ES_AUTOHSCROLL,
            12, 44, 0, 0, hwnd, (HMENU)IDC_EXPORT_TEXT,
            GetModuleHandleW(NULL), NULL);
        SendMessageW(ed, WM_SETFONT, (WPARAM)g_font, TRUE);
        SetWindowTextW(ed, text);
        return 0;
    }
    case WM_SIZE: {
        int w = LOWORD(lp), h = HIWORD(lp);
        SetWindowPos(GetDlgItem(hwnd, IDC_EXPORT_TEXT), NULL,
                     12, 44, w - 24, h - 56, SWP_NOZORDER);
        break;
    }
    case WM_COMMAND:
        switch (LOWORD(wp)) {
        case IDC_EXPORT_COPY: {
            wchar_t text[2048];
            GetDlgItemTextW(hwnd, IDC_EXPORT_TEXT, text, 2048);
            copy_to_clipboard(hwnd, text);
            break;
        }
        case IDC_EXPORT_SAVE: {
            wchar_t text[2048];
            GetDlgItemTextW(hwnd, IDC_EXPORT_TEXT, text, 2048);
            save_bat_dialog(hwnd, text);
            break;
        }
        case IDC_EXPORT_CLOSE:
            DestroyWindow(hwnd);
            break;
        }
        break;
    case WM_CLOSE:
        DestroyWindow(hwnd);
        break;
    case WM_DESTROY:
        g_dlg = NULL;
        break;
    default:
        return DefWindowProcW(hwnd, msg, wp, lp);
    }
    return 0;
}

static void show_export_dialog(HWND owner)
{
    if (g_dlg) {
        SetForegroundWindow(g_dlg);
        return;
    }
    g_dlg = CreateWindowExW(WS_EX_DLGMODALFRAME, L"IPA2VecExportDlg",
        L"Export command lines", WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT, CW_USEDEFAULT, 460, 320,
        owner, NULL, GetModuleHandleW(NULL), NULL);
    if (g_dlg)
        ShowWindow(g_dlg, SW_SHOW);
}

/* ------------------------------------------------------------------ */
/* main window                                                        */
/* ------------------------------------------------------------------ */

static void layout(HWND hwnd)
{
    RECT cr;
    GetClientRect(hwnd, &cr);
    int w = cr.right, h = cr.bottom;

    /* status bar height */
    SendMessageW(g_hStatus, WM_SIZE, 0, 0);
    RECT sr;
    GetWindowRect(g_hStatus, &sr);
    int sbh = sr.bottom - sr.top;
    int usable = h - sbh;

    int left_w = 430;
    int x = 8, y = 8;
    const int lw = left_w - 16;

    /* IPA input row */
    CreateWindowW(L"STATIC", L"IPA input (click keyboard buttons or type):",
        WS_CHILD | WS_VISIBLE, x, y, lw, 18, hwnd, NULL,
        GetModuleHandleW(NULL), NULL);
    y += 20;
    HWND ipa = GetDlgItem(hwnd, IDC_IPA_IN);
    SetWindowPos(ipa, NULL, x, y, lw - 84, 24, SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_BTN_FWD), NULL, x + lw - 76, y, 76, 24,
                 SWP_NOZORDER);
    y += 34;

    /* vector input row */
    CreateWindowW(L"STATIC", L"16-D vector (comma separated) -> reverse fit:",
        WS_CHILD | WS_VISIBLE, x, y, lw, 18, hwnd, NULL,
        GetModuleHandleW(NULL), NULL);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_VEC_IN), NULL, x, y, lw - 152, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_BTN_REV), NULL, x + lw - 144, y, 64, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_COMBO_W), NULL, x + lw - 72, y, 64, 24,
                 SWP_NOZORDER);
    y += 34;

    /* query row */
    CreateWindowW(L"STATIC", L"Query one symbol:",
        WS_CHILD | WS_VISIBLE, x, y, lw, 18, hwnd, NULL,
        GetModuleHandleW(NULL), NULL);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_Q_IN), NULL, x, y, lw - 84, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_BTN_QUERY), NULL, x + lw - 76, y, 76, 24,
                 SWP_NOZORDER);
    y += 36;

    /* output */
    CreateWindowW(L"STATIC", L"Output:", WS_CHILD | WS_VISIBLE, x, y, lw, 18,
                  hwnd, NULL, GetModuleHandleW(NULL), NULL);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_OUT), NULL, x, y, lw, usable - y - 8,
                 SWP_NOZORDER);

    /* keyboard area: right side */
    int kx = left_w + 4;
    int kw = w - kx - 8;
    SetWindowPos(GetDlgItem(hwnd, IDC_TABS), NULL, kx, 8, kw, usable - 16,
                 SWP_NOZORDER);
    RECT tr;
    GetWindowRect(GetDlgItem(hwnd, IDC_TABS), &tr);
    /* tab control display area (approx: adjust by tab header height) */
    RECT tcr;
    TabCtrl_GetItemRect(GetDlgItem(hwnd, IDC_TABS), 0, &tcr);
    int header = tcr.bottom - tcr.top + 4;
    int px = kx + 4, py = 8 + header + 4;
    int pw = kw - 16, ph = usable - 16 - header - 12;
    HWND panes[4] = {
        GetDlgItem(hwnd, IDC_PANE_CONS), GetDlgItem(hwnd, IDC_PANE_VOW),
        GetDlgItem(hwnd, IDC_PANE_MOD), GetDlgItem(hwnd, IDC_PANE_TONE),
    };
    for (int i = 0; i < 4; i++)
        SetWindowPos(panes[i], NULL, px, py, pw, ph, SWP_NOZORDER);
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CREATE: {
        HWND ed;

        ed = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP,
            0, 0, 0, 0, hwnd, (HMENU)IDC_IPA_IN,
            GetModuleHandleW(NULL), NULL);
        SetWindowFont(ed, g_font, TRUE);

        ed = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP,
            0, 0, 0, 0, hwnd, (HMENU)IDC_VEC_IN,
            GetModuleHandleW(NULL), NULL);
        SetWindowFont(ed, g_font, TRUE);

        ed = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP,
            0, 0, 0, 0, hwnd, (HMENU)IDC_Q_IN,
            GetModuleHandleW(NULL), NULL);
        SetWindowFont(ed, g_font, TRUE);

        CreateWindowW(L"BUTTON", L"&Convert", WS_CHILD | WS_VISIBLE,
            0, 0, 0, 0, hwnd, (HMENU)IDC_BTN_FWD,
            GetModuleHandleW(NULL), NULL);
        CreateWindowW(L"BUTTON", L"&Reverse", WS_CHILD | WS_VISIBLE,
            0, 0, 0, 0, hwnd, (HMENU)IDC_BTN_REV,
            GetModuleHandleW(NULL), NULL);
        CreateWindowW(L"BUTTON", L"&Query", WS_CHILD | WS_VISIBLE,
            0, 0, 0, 0, hwnd, (HMENU)IDC_BTN_QUERY,
            GetModuleHandleW(NULL), NULL);

        HWND combo = CreateWindowW(L"COMBOBOX", L"",
            WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_TABSTOP,
            0, 0, 0, 0, hwnd, (HMENU)IDC_COMBO_W,
            GetModuleHandleW(NULL), NULL);
        SendMessageW(combo, WM_SETFONT, (WPARAM)g_font, TRUE);
        for (int i = 0; i < 5; i++) {
            wchar_t item[32];
            swprintf(item, 32, L"width %d", i);
            SendMessageW(combo, CB_ADDSTRING, 0, (LPARAM)item);
        }
        SendMessageW(combo, CB_SETCURSEL, 3, 0); /* default width 3 */

        ed = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_AUTOVSCROLL |
            ES_AUTOHSCROLL | ES_READONLY,
            0, 0, 0, 0, hwnd, (HMENU)IDC_OUT,
            GetModuleHandleW(NULL), NULL);
        SetWindowFont(ed, g_font, TRUE);

        /* IPA keyboard */
        HWND tabs = CreateWindowW(WC_TABCONTROLW, L"",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP,
            0, 0, 0, 0, hwnd, (HMENU)IDC_TABS,
            GetModuleHandleW(NULL), NULL);
        SetWindowFont(tabs, g_font, TRUE);

        TCITEMW ti;
        ZeroMemory(&ti, sizeof(ti));
        ti.mask = TCIF_TEXT;
        const wchar_t *tabnames[4] = { L"Consonants", L"Vowels",
                                       L"Modifiers", L"Tones" };
        for (int i = 0; i < 4; i++) {
            ti.pszText = (LPWSTR)tabnames[i];
            TabCtrl_InsertItem(tabs, i, &ti);
        }

        const wchar_t *panes[4] = { L"PANE_CONS", L"PANE_VOW",
                                    L"PANE_MOD", L"PANE_TONE" };
        int ids[4] = { IDC_PANE_CONS, IDC_PANE_VOW,
                       IDC_PANE_MOD, IDC_PANE_TONE };
        HWND pv[4];
        for (int i = 0; i < 4; i++) {
            pv[i] = CreateWindowW(L"STATIC", L"",
                WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                0, 0, 0, 0, hwnd, (HMENU)(INT_PTR)ids[i],
                GetModuleHandleW(NULL), NULL);
            (void)panes;
        }
        build_consonant_pane(pv[0]);
        build_vowel_pane(pv[1]);
        build_modifier_pane(pv[2]);
        build_tone_pane(pv[3]);
        ShowWindow(pv[1], SW_HIDE);
        ShowWindow(pv[2], SW_HIDE);
        ShowWindow(pv[3], SW_HIDE);

        /* status bar */
        g_hStatus = CreateWindowExW(0, STATUSCLASSNAMEW, L"",
            WS_CHILD | WS_VISIBLE | SBARS_SIZEGRIP,
            0, 0, 0, 0, hwnd, (HMENU)1,
            GetModuleHandleW(NULL), NULL);
        SetWindowTextW(g_hStatus, L"Ready");
        break;
    }
    case WM_SIZE:
        layout(hwnd);
        break;
    case WM_NOTIFY: {
        if (LOWORD(wp) == IDC_TABS) {
            NMHDR *nm = (NMHDR *)lp;
            if (nm->code == TCN_SELCHANGE) {
                int sel = TabCtrl_GetCurSel(GetDlgItem(hwnd, IDC_TABS));
                int ids[4] = { IDC_PANE_CONS, IDC_PANE_VOW,
                               IDC_PANE_MOD, IDC_PANE_TONE };
                for (int i = 0; i < 4; i++)
                    ShowWindow(GetDlgItem(hwnd, ids[i]),
                               i == sel ? SW_SHOW : SW_HIDE);
            }
        }
        break;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        switch (id) {
        case IDC_BTN_FWD: {
            GetDlgItemTextW(hwnd, IDC_IPA_IN, g_ipa_buf, 4096);
            char utf8[8192];
            int n = WideCharToMultiByte(CP_UTF8, 0, g_ipa_buf, -1,
                                        utf8, 8192, NULL, NULL);
            if (n > 1) {
                HWND out = GetDlgItem(hwnd, IDC_OUT);
                out_header(out, L"IPA -> vectors");
                do_forward(out, utf8);
            }
            break;
        }
        case IDC_BTN_REV: {
            wchar_t wbuf[4096];
            GetDlgItemTextW(hwnd, IDC_VEC_IN, wbuf, 4096);
            char utf8[8192];
            WideCharToMultiByte(CP_UTF8, 0, wbuf, -1, utf8, 8192, NULL, NULL);
            int sel = (int)SendMessageW(GetDlgItem(hwnd, IDC_COMBO_W),
                                        CB_GETCURSEL, 0, 0);
            set_width(sel < 0 ? 3 : sel);
            HWND out = GetDlgItem(hwnd, IDC_OUT);
            out_header(out, L"Vector -> IPA (reverse fit)");
            do_reverse(out, utf8);
            break;
        }
        case IDC_BTN_QUERY: {
            wchar_t wbuf[4096];
            GetDlgItemTextW(hwnd, IDC_Q_IN, wbuf, 4096);
            char utf8[8192];
            WideCharToMultiByte(CP_UTF8, 0, wbuf, -1, utf8, 8192, NULL, NULL);
            HWND out = GetDlgItem(hwnd, IDC_OUT);
            out_header(out, L"Query");
            do_query(out, utf8);
            break;
        }
        case ID_FILE_EXPORT:
            show_export_dialog(hwnd);
            break;
        case ID_FILE_EXPORT_TOOLS:
            export_tools_dialog(hwnd);
            break;
        case ID_HELP_ABOUT:
            MessageBoxW(hwnd,
                L"IPA2Vector Workbench " APP_VERSION L"\r\n"
                L"Single-file Win32 GUI for the vec4ipa tool suite.\r\n"
                L"https://github.com/csiroqa/vec4ipa",
                L"About", MB_ICONINFORMATION);
            break;
        case ID_HELP_DOCS: {
            HWND out = GetDlgItem(hwnd, IDC_OUT);
            SetWindowTextW(out, L"");
            out_append(out, EMBEDDED_README);
            break;
        }
        default:
            if (id >= IDB_BASE && id < IDB_MAX && g_btn_sym[id - IDB_BASE]) {
                /* keyboard button: append symbol to IPA input */
                GetDlgItemTextW(hwnd, IDC_IPA_IN, g_ipa_buf, 4096);
                size_t len = wcslen(g_ipa_buf);
                size_t n = wcslen(g_btn_sym[id - IDB_BASE]);
                if (len + n < 4096) {
                    wcscat(g_ipa_buf, g_btn_sym[id - IDB_BASE]);
                    SetWindowTextW(GetDlgItem(hwnd, IDC_IPA_IN), g_ipa_buf);
                    int e = (int)(len + n);
                    SendMessageW(GetDlgItem(hwnd, IDC_IPA_IN), EM_SETSEL,
                                 e, e);
                }
            }
            break;
        }
        break;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        break;
    default:
        return DefWindowProcW(hwnd, msg, wp, lp);
    }
    return 0;
}

static void init_menu(HWND hwnd)
{
    HMENU bar = CreateMenu();
    HMENU file = CreatePopupMenu();
    AppendMenuW(file, MF_STRING, ID_FILE_EXPORT, L"&Export command lines...");
    AppendMenuW(file, MF_STRING, ID_FILE_EXPORT_TOOLS,
                L"Export &tools (ipa2vec/vec2ipa/vec4ipa)...");
    AppendMenuW(file, MF_SEPARATOR, 0, NULL);
    AppendMenuW(file, MF_STRING, ID_FILE_EXIT, L"E&xit");
    AppendMenuW(bar, MF_POPUP, (UINT_PTR)file, L"&File");

    HMENU help = CreatePopupMenu();
    AppendMenuW(help, MF_STRING, ID_HELP_DOCS, L"&Documentation");
    AppendMenuW(help, MF_STRING, ID_HELP_ABOUT, L"&About");
    AppendMenuW(bar, MF_POPUP, (UINT_PTR)help, L"&Help");

    SetMenu(hwnd, bar);
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int nCmdShow)
{
    INITCOMMONCONTROLSEX icc;
    icc.dwSize = sizeof(icc);
    icc.dwICC = ICC_BAR_CLASSES | ICC_TAB_CLASSES;
    InitCommonControlsEx(&icc);

    /* Load the bundled fonts (OFL-licensed, ui/fonts/) from the folder
     * beside the executable so a shipped copy needs no font install. */
    {
        wchar_t exe[MAX_PATH], fontpath[MAX_PATH];
        if (GetModuleFileNameW(NULL, exe, MAX_PATH) &&
            wcsrchr(exe, L'\\')) {
            *(wcsrchr(exe, L'\\') + 1) = L'\0';
            const wchar_t *fonts[] = {
                L"fonts\\GentiumBookPlus-Regular.ttf",
                L"fonts\\NewCM10-Bold.otf",
            };
            for (int i = 0; i < 2; i++) {
                swprintf(fontpath, MAX_PATH, L"%s%s", exe, fonts[i]);
                AddFontResourceExW(fontpath, FR_PRIVATE, 0);
            }
        }
    }

    g_font = CreateFontW(-16, 0, 0, 0, FW_NORMAL, 0, 0, 0,
        DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0,
        L"Gentium Book Plus");
    g_font_btn = CreateFontW(-15, 0, 0, 0, FW_NORMAL, 0, 0, 0,
        DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0,
        L"Gentium Book Plus");

    WNDCLASSEXW wc = {0};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_APP));
    wc.hIconSm = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_APP));
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = L"IPA2VectorWorkbench";
    RegisterClassExW(&wc);

    WNDCLASSEXW wd = {0};
    wd.cbSize = sizeof(wd);
    wd.lpfnWndProc = export_wndproc;
    wd.hInstance = hInst;
    wd.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_APP));
    wd.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wd.lpszClassName = L"IPA2VecExportDlg";
    RegisterClassExW(&wd);

    set_width(3);

    HWND hwnd = CreateWindowExW(0, L"IPA2VectorWorkbench", APP_NAME,
        WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, 980, 640,
        NULL, NULL, hInst, NULL);
    if (!hwnd) return 0;
    init_menu(hwnd);
    ShowWindow(hwnd, nCmdShow);
    UpdateWindow(hwnd);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return (int)msg.wParam;
}
