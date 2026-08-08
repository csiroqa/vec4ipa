/*
 * vec4ipa_ui — single-file Win32 GUI for the vec4ipa tool suite.
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
 *   gcc -O2 -municode -mwindows -I../src -o vec4ipa_ui.exe \
 *       vec4ipa_ui.c app.res -lcomctl32 -lcomdlg32 -lshell32 -lole32
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <windowsx.h>
#include <commctrl.h>
#include <commdlg.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "../src/ipa2vec_core.h"
#include "../src/readme_embed.h"

#define APP_NAME      L"vec4ipa Workbench"
#define APP_VERSION   L"0.2.0"

/* control ids */
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
#define IDC_LBL_IPA   5014
#define IDC_LBL_VEC   5015
#define IDC_LBL_Q     5016
#define IDC_LBL_OUT   5017

/* keyboard button id ranges (unique per pane!) */
#define IDB_BASE   6000
#define IDB_EXTRA  7000
#define IDB_MOD    8000
#define IDB_TONE   9000
#define IDB_VOW    9500
/* largest button id actually used: the vowel group runs to IDB_VOW+NSEG-1 */
#define IDB_LAST   (IDB_VOW + NSEG - 1)

static HFONT g_font = NULL;        /* Gentium (UI text + IPA) */
static HFONT g_font_btn = NULL;    /* smaller for keyboard buttons */
static HWND g_hStatus = NULL;

/* keyboard buttons are direct children of the main window (no pane
 * nesting): WM_COMMAND arrives straight at WndProc, and MoveWindow
 * in layout() forces their repaint. Each group is a tab page. */
#define KB_GROUPS 4
#define KB_MAX_BTNS 160
static HWND g_kb_btn[KB_GROUPS][KB_MAX_BTNS];
static int   g_kb_n[KB_GROUPS];
static int   g_kb_x[KB_GROUPS][KB_MAX_BTNS];
static int   g_kb_y[KB_GROUPS][KB_MAX_BTNS];
static int   g_kb_w[KB_GROUPS][KB_MAX_BTNS];
static int   g_kb_h[KB_GROUPS][KB_MAX_BTNS];
static int   g_kb_sel = 0;

static const wchar_t *g_btn_sym[IDB_LAST - IDB_BASE + 1]; /* symbol per button id */
static wchar_t g_ipa_buf[4096];

static wchar_t *utf8_to_wide(const char *s, wchar_t *buf, size_t cap)
{
    if (!s) return NULL;
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, buf, (int)cap);
    if (n <= 0) buf[0] = L'\0';
    return buf;
}

/* vowels are the SEG_TABLE entries whose NAME_TABLE entry ends in ".vwl" */
static int is_vowel(const SegEntry *se)
{
    if (!se) return 0;
    ptrdiff_t idx = se - SEG_TABLE;
    if (idx < 0 || idx >= NSEG) return 0;
    return strstr(NAME_TABLE[idx], ".vwl") != NULL;
}

/* ------------------------------------------------------------------ */
/* keyboard construction (buttons are children of the main window)     */
/* ------------------------------------------------------------------ */

static int kb_add(HWND parent, int group, int id, const wchar_t *sym,
                  int x, int y, int w, int h)
{
    if (group < 0 || group >= KB_GROUPS || g_kb_n[group] >= KB_MAX_BTNS)
        return -1;
    HWND btn = CreateWindowW(L"BUTTON", sym,
        WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON | WS_TABSTOP,
        x, y, w, h, parent, (HMENU)(INT_PTR)id,
        GetModuleHandleW(NULL), NULL);
    if (!btn) return -1;
    SendMessageW(btn, WM_SETFONT, (WPARAM)g_font_btn, TRUE);
    g_kb_btn[group][g_kb_n[group]] = btn;
    g_kb_x[group][g_kb_n[group]] = x;
    g_kb_y[group][g_kb_n[group]] = y;
    g_kb_w[group][g_kb_n[group]] = w;
    g_kb_h[group][g_kb_n[group]] = h;
    g_kb_n[group]++;
    if (id >= IDB_BASE && id <= IDB_LAST)
        g_btn_sym[id - IDB_BASE] = sym;
    return id;
}

static void kb_build_all(HWND parent)
{
    int i;
    for (i = 0; i < KB_GROUPS; i++)
        g_kb_n[i] = 0;

    /* group 0: consonants from SEG_TABLE (skip vowels), then EXTRA */
    static const int per_row = 10;
    int x0 = 0, y0 = 0, bw = 30, bh = 24, gap = 2;
    int x = x0, y = y0, n = 0;
    for (i = 0; i < NSEG; i++) {
        if (is_vowel(&SEG_TABLE[i])) continue;
        wchar_t sym[8];
        utf8_to_wide(SEG_TABLE[i].ipa, sym, 8);
        kb_add(parent, 0, IDB_BASE + i, sym, x, y, bw, bh);
        n++;
        if (n % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }
    x = x0; y += bh + 4;
    for (i = 0; i < N_EXTRA; i++) {
        wchar_t sym[8];
        utf8_to_wide(EXTRA_BASE[i].ipa, sym, 8);
        kb_add(parent, 0, IDB_EXTRA + i, sym, x, y, bw, bh);
        n++;
        if (n % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }

    /* group 1: vowels on the trapezium */
    static const double pos_steps[8] = {0.0, 0.14, 0.28, 0.42,
                                        0.56, 0.70, 0.84, 1.0};
    int vx0 = 8, vy0 = 6, vbw = 36, vbh = 30, vgap = 4;
    for (i = 0; i < NSEG; i++) {
        if (!is_vowel(&SEG_TABLE[i])) continue;
        double tt = SEG_TABLE[i].v[2];
        double th = SEG_TABLE[i].v[3];
        int col = 0;
        for (int c = 0; c < 8; c++)
            if (tt >= pos_steps[c]) col = c;
        int row = (int)((1.0 - th) * 4.0 + 0.5);
        if (row < 0) row = 0;
        if (row > 4) row = 4;
        wchar_t sym[8];
        utf8_to_wide(SEG_TABLE[i].ipa, sym, 8);
        kb_add(parent, 1, IDB_VOW + i, sym, vx0 + col * (vbw + vgap),
               vy0 + row * (vbh + vgap), vbw, vbh);
    }

    /* group 2: modifiers */
    x = x0; y = y0; n = 0;
    for (i = 0; i < NMODS; i++) {
        wchar_t sym[8];
        utf8_to_wide(MODS[i].ipa, sym, 8);
        kb_add(parent, 2, IDB_MOD + i, sym, x, y, bw, bh);
        n++;
        if (n % per_row == 0) { x = x0; y += bh + gap; } else x += bw + gap;
    }

    /* group 3: tones */
    static const wchar_t *tone_syms[] = {
        L"\u02E5", L"\u02E6", L"\u02E7", L"\u02E8", L"\u02E9",
        L"\uA712", L"\uA713", L"\uA714", L"\uA715", L"\uA716",
        L"\u2197", L"\u2198", L"\uA71B", L"\uA71C",
        L"\u2070", L"\u00B9", L"\u00B2", L"\u00B3", L"\u2074",
        L"\u2075", L"\u2076", L"\u2077", L"\u2078", L"\u2079",
        L"\u203F", L" ",
    };
    static const int trow = 6;
    x = x0; y = y0; n = 0;
    for (i = 0; i < (int)(sizeof(tone_syms) / sizeof(tone_syms[0])); i++) {
        kb_add(parent, 3, IDB_TONE + i, tone_syms[i], x, y, 36, 30);
        n++;
        if (n % trow == 0) { x = x0; y += 33; } else x += 39;
    }

    for (i = 1; i < KB_GROUPS; i++) {
        for (int j = 0; j < g_kb_n[i]; j++)
            ShowWindow(g_kb_btn[i][j], SW_HIDE);
    }
}

/* move the keyboard buttons into the tab display area (base = client
 * coords of the display area top-left) */
static void kb_layout(int bx, int by)
{
    for (int g = 0; g < KB_GROUPS; g++) {
        for (int i = 0; i < g_kb_n[g]; i++) {
            MoveWindow(g_kb_btn[g][i], bx + g_kb_x[g][i], by + g_kb_y[g][i],
                       g_kb_w[g][i], g_kb_h[g][i], TRUE);
        }
    }
}

/* ------------------------------------------------------------------ */
/* helpers                                                            */
/* ------------------------------------------------------------------ */

static void out_append(HWND out, const char *utf8)
{
    wchar_t buf[8192];
    /* cap 8190 so the possible L"\r\n" suffix always fits */
    utf8_to_wide(utf8, buf, 8190);
    size_t len = wcslen(buf);
    if (len && buf[len - 1] != L'\n')
        wcscat(buf, L"\r\n");
    int n = GetWindowTextLengthW(out);
    /* ES_READONLY blocks EM_REPLACESEL; lift it temporarily */
    SendMessageW(out, EM_SETREADONLY, FALSE, 0);
    SendMessageW(out, EM_SETSEL, n, n);
    SendMessageW(out, EM_REPLACESEL, FALSE, (LPARAM)buf);
    SendMessageW(out, EM_SETREADONLY, TRUE, 0);
}

/* wide_to_utf8() (malloc'd UTF-8 copy of a wide string) comes from
 * ipa2vec_core.h */

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
    if (tok)
        out_append(out, "warning: extra values beyond 16 were ignored");
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
/* command-line export (File > Export command lines...)                */
/* ------------------------------------------------------------------ */

static void build_export_text(wchar_t *buf, size_t cap)
{
    /* the CLI tools live beside this executable */
    wchar_t dir[MAX_PATH];
    DWORD dn = GetModuleFileNameW(NULL, dir, MAX_PATH);
    if (dn == 0 || dn >= MAX_PATH) {
        buf[0] = L'\0';
        return;
    }
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) slash[1] = L'\0';

    swprintf(buf, cap,
        L"# vec4ipa CLI commands (generated by %s)\r\n"
        L"# tools directory: %s\r\n"
        L"\r\n"
        L":: ipa2vec  - IPA -> 16-D vectors (with IR + rebuilt demo)\r\n"
        L"\"%sipa2vec.exe\" --width 3 -i \"\\\"\\u02c8t\\u02b0a\\\"\"\r\n"
        L"\r\n"
        L":: vec2ipa  - 16-D vector -> IPA (reverse fit)\r\n"
        L"\"%svec2ipa.exe\" --width 3 \"0.0,0.0,0.55,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0,0.0,0.0,1.0\"\r\n"
        L"\r\n"
        L":: vec4ipa - inventory / query / reverse\r\n"
        L"\"%svec4ipa.exe\" -q \u02b0\r\n"
        L"\"%svec4ipa.exe\" --width 3 -r \"0.0,0.0,0.55,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0,0.0,0.0,1.0\"\r\n",
        APP_VERSION, dir, dir, dir, dir, dir);
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
    SetWindowPos(GetDlgItem(hwnd, IDC_LBL_IPA), NULL, x, y, lw, 18,
                 SWP_NOZORDER);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_IPA_IN), NULL, x, y, lw - 84, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_BTN_FWD), NULL, x + lw - 76, y, 76, 24,
                 SWP_NOZORDER);
    y += 34;

    /* vector input row */
    SetWindowPos(GetDlgItem(hwnd, IDC_LBL_VEC), NULL, x, y, lw, 18,
                 SWP_NOZORDER);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_VEC_IN), NULL, x, y, lw - 152, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_BTN_REV), NULL, x + lw - 144, y, 64, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_COMBO_W), NULL, x + lw - 72, y, 64, 24,
                 SWP_NOZORDER);
    y += 34;

    /* query row */
    SetWindowPos(GetDlgItem(hwnd, IDC_LBL_Q), NULL, x, y, lw, 18,
                 SWP_NOZORDER);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_Q_IN), NULL, x, y, lw - 84, 24,
                 SWP_NOZORDER);
    SetWindowPos(GetDlgItem(hwnd, IDC_BTN_QUERY), NULL, x + lw - 76, y, 76, 24,
                 SWP_NOZORDER);
    y += 36;

    /* output */
    SetWindowPos(GetDlgItem(hwnd, IDC_LBL_OUT), NULL, x, y, lw, 18,
                 SWP_NOZORDER);
    y += 20;
    SetWindowPos(GetDlgItem(hwnd, IDC_OUT), NULL, x, y, lw, usable - y - 8,
                 SWP_NOZORDER);

    /* keyboard area: right side */
    int kx = left_w + 4;
    int kw = w - kx - 8;
    SetWindowPos(GetDlgItem(hwnd, IDC_TABS), NULL, kx, 8, kw, usable - 16,
                 SWP_NOZORDER);
    RECT tcr;
    TabCtrl_GetItemRect(GetDlgItem(hwnd, IDC_TABS), 0, &tcr);
    int header = tcr.bottom - tcr.top + 4;
    int px = kx + 4, py = 8 + header + 4;
    kb_layout(px, py);
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CREATE: {
        HWND ed;
        const wchar_t *labels[4] = {
            L"IPA input (click keyboard buttons or type):",
            L"16-D vector (comma separated) -> reverse fit:",
            L"Query one symbol:", L"Output:",
        };
        int label_ids[4] = { IDC_LBL_IPA, IDC_LBL_VEC, IDC_LBL_Q, IDC_LBL_OUT };
        for (int i = 0; i < 4; i++) {
            CreateWindowW(L"STATIC", labels[i],
                WS_CHILD | WS_VISIBLE, 0, 0, 0, 0, hwnd,
                (HMENU)(INT_PTR)label_ids[i], GetModuleHandleW(NULL), NULL);
        }

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

        kb_build_all(hwnd);

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
    case WM_GETMINMAXINFO: {
        /* keep the layout from producing negative control sizes */
        MINMAXINFO *mmi = (MINMAXINFO *)lp;
        DefWindowProcW(hwnd, msg, wp, lp);
        mmi->ptMinTrackSize.x = 560;
        mmi->ptMinTrackSize.y = 420;
        break;
    }
    case WM_NOTIFY: {
        if (LOWORD(wp) == IDC_TABS) {
            NMHDR *nm = (NMHDR *)lp;
            if (nm->code == TCN_SELCHANGE) {
                int sel = TabCtrl_GetCurSel(GetDlgItem(hwnd, IDC_TABS));
                if (sel != g_kb_sel) {
                    for (int i = 0; i < g_kb_n[g_kb_sel]; i++)
                        ShowWindow(g_kb_btn[g_kb_sel][i], SW_HIDE);
                    g_kb_sel = sel;
                    for (int i = 0; i < g_kb_n[g_kb_sel]; i++)
                        ShowWindow(g_kb_btn[g_kb_sel][i], SW_SHOW);
                }
            }
        }
        break;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        switch (id) {
        case IDC_BTN_FWD: {
            GetDlgItemTextW(hwnd, IDC_IPA_IN, g_ipa_buf, 4096);
            char *utf8 = wide_to_utf8(g_ipa_buf);
            if (utf8 && utf8[0]) {
                HWND out = GetDlgItem(hwnd, IDC_OUT);
                out_header(out, L"IPA -> vectors");
                do_forward(out, utf8);
            }
            free(utf8);
            break;
        }
        case IDC_BTN_REV: {
            wchar_t wbuf[4096];
            GetDlgItemTextW(hwnd, IDC_VEC_IN, wbuf, 4096);
            char *utf8 = wide_to_utf8(wbuf);
            if (utf8) {
                int sel = (int)SendMessageW(GetDlgItem(hwnd, IDC_COMBO_W),
                                            CB_GETCURSEL, 0, 0);
                set_width(sel < 0 ? 3 : sel);
                HWND out = GetDlgItem(hwnd, IDC_OUT);
                out_header(out, L"Vector -> IPA (reverse fit)");
                do_reverse(out, utf8);
            }
            free(utf8);
            break;
        }
        case IDC_BTN_QUERY: {
            wchar_t wbuf[4096];
            GetDlgItemTextW(hwnd, IDC_Q_IN, wbuf, 4096);
            char *utf8 = wide_to_utf8(wbuf);
            if (utf8) {
                HWND out = GetDlgItem(hwnd, IDC_OUT);
                out_header(out, L"Query");
                do_query(out, utf8);
            }
            free(utf8);
            break;
        }
        case ID_FILE_EXPORT:
            show_export_dialog(hwnd);
            break;
        case ID_FILE_EXPORT_TOOLS:
            export_tools_dialog(hwnd);
            break;
        case ID_FILE_EXIT:
            DestroyWindow(hwnd);
            break;
        case ID_HELP_ABOUT:
            MessageBoxW(hwnd,
                L"vec4ipa Workbench " APP_VERSION L"\r\n"
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
            if (id >= IDB_BASE && id <= IDB_LAST && g_btn_sym[id - IDB_BASE]) {
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
                if (AddFontResourceExW(fontpath, FR_PRIVATE, 0) == 0)
                    MessageBoxW(NULL, fontpath, L"Font not loaded",
                                MB_ICONWARNING);
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
    wc.lpszClassName = L"Vec4ipaWorkbench";
    if (!RegisterClassExW(&wc)) {
        MessageBoxW(NULL, L"Failed to register the main window class.",
                    APP_NAME, MB_ICONERROR);
        return 1;
    }

    WNDCLASSEXW wd = {0};
    wd.cbSize = sizeof(wd);
    wd.lpfnWndProc = export_wndproc;
    wd.hInstance = hInst;
    wd.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_APP));
    wd.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wd.lpszClassName = L"IPA2VecExportDlg";
    if (!RegisterClassExW(&wd)) {
        MessageBoxW(NULL, L"Failed to register the export dialog class.",
                    APP_NAME, MB_ICONERROR);
        return 1;
    }

    set_width(3);

    HWND hwnd = CreateWindowExW(0, L"Vec4ipaWorkbench", APP_NAME,
        WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, 980, 640,
        NULL, NULL, hInst, NULL);
    if (!hwnd) {
        MessageBoxW(NULL, L"Failed to create the main window.", APP_NAME,
                    MB_ICONERROR);
        return 1;
    }
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
