#!/usr/bin/env python3
"""Fetch CONSONANT acoustic measurements, and report honestly when there are none.

WHAT IS MEASURED AND WHY
------------------------
The nine formant datasets already in tools/data/ are vowel-only, so the new
tongue coordinates (tip/blade/dorsum/root, x and y) have never been tested
against a consonant. Until that happens nobody can tell whether some of those
eight coordinates are DEAD AXES -- coordinates no measurement in the corpus
constrains. This script is the evidence-gathering half of that test: it pulls
real, published consonant acoustics (formants, burst/spectral cues) with
articulatory labels, and records exactly which sources answered and which
did not.

WHAT IS DELIBERATELY NOT DONE
-----------------------------
Vowel data is never substituted for consonant data. A source that answers with
only vowels is reported as a negative result, not converted into something
consonant-shaped. Nothing here is interpolated or filled in.

SOURCES, in the order they are tried
------------------------------------
  1. Direct reachability probes of the sources named in the task brief
     (phonTools, PhoneticBank, UCI, OpenSLR, CRAN, GitHub, Zenodo, HuggingFace).
     These are cheap and their failure modes are the evidence for why the
     other two strategies were chosen.
  2. DataverseNO (dataverse.no). It is the one public repository that answered
     every request and that indexes a lot of phonetics replication data.
     Small tabular files are downloaded and screened for formant/spectral
     columns plus an explicit consonant label.
  3. The emudata R package (richardbeare/emudata on GitHub). This is the only
     reachable source found that ships measured consonant SPECTRA with
     phoneme labels: German and Australian English stop bursts and fricatives.
  4. Europe PMC open-access full text. Phonetics papers publish their measured
     consonant tables as real HTML tables in the full-text XML, so the tables
     can be mined rather than guessed at.

Run: python tools/fetch_consonant_data.py
"""

import io
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'data', 'consonant')
RAW = os.path.join(OUT, 'raw')

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

# Anything bigger than this in a phonetics replication package is audio, not a
# formant table. 2 MB is the largest published consonant table seen in these
# repositories by a wide margin (the biggest so far is 87 kB), so the cap costs
# nothing and keeps the sweep from pulling gigabytes of .wav.
MAX_TEXT_BYTES = 2_000_000

# emudata's whole data/ directory is about 23 MB and it is the only reachable
# source of measured consonant spectra, so it gets its own cap instead of
# sharing MAX_TEXT_BYTES, which is tuned to DataverseNO's formant tables.
EMUDATA_MAX_BYTES = 32_000_000

# 12 s per request: Europe PMC full-text XML over a slow link takes ~4 s.
TIMEOUT = 60

# Delay between requests. 0.4 s keeps the sweep polite and stops either host
# from throttling us into silent truncation (which would look like a negative
# result but would be an artefact).
POLITE_S = 0.4

# ---------------------------------------------------------------------------
# Consonant symbols
# ---------------------------------------------------------------------------
# The IPA consonant inventory used only to decide "is this table about a
# consonant". Vowel symbols are subtracted explicitly, because a table that
# mentions /i/ and /a/ next to a form of /t/ is still consonant evidence, but a
# table with only vowels is not.
CONSONANTS = set(
    '\u0254\u0255\u0257\u0259\u025b\u0260\u0263\u0268\u026b\u0270\u0272\u0279'
    '\u027c\u027d\u027e\u0281\u028b\u0290\u0294'          # labial, uvular, retroflex
    '\u02a0\u02a1\u02a6\u02a7\u02a9\u02ab\u02ac\u02ad\u02ae\u02af'  # affricates
    '\u02b0\u02b1\u02b2\u0271\u0273\u0275\u0276\u0278\u027a\u027b\u0291'
    '\u0292\u0295\u0296\u029d\u029e\u029f'                # other fricatives
    'ptkbdgcqfx'                                          # pulmonic stops/fricatives
    '\u0266\u026f\u0287\u0288\u0289\u028a\u028d\u028e'   # rounded/implosive
    '\u0262\u0265\u0267'                                  # implosives
    '\u0280\u0282\u0283\u0284\u0285\u0286'                # retroflex flaps/rhotic
)
VOWEL_SYMBOLS = set('aeiouy\u0251\u026a\u00e6\u00e8\u00ea\u00eb\u00ec\u00ed'
                    '\u00ee\u00ef\u00f8\u00f9\u00fa\u00fb\u00fc\u00fd\u014b'
                    # IPA vowel symbols outside the basic Latin block. Leaving
                    # these in cost 12 of 18 mined rows: tables of /ɛ/, /ə/ and
                    # /ʊ/ were being filed as consonant evidence.
                    '\u0252\u0254\u0259\u025b\u0268\u026a\u0265\u026f'
                    '\u028a\u028c\u028f\u029e\u03b1\u03b2\u03b8'
                    '\u03d5\u0250\u0253')
CONSONANTS -= VOWEL_SYMBOLS
# 'c' and 'g' are only consonants in the velar sense; tables use them as letter
# names too. Keep them: every hit is screened by the acoustic-column rule as
# well, and dropping them would lose /k/ /g/ data written in ASCII.

# A table cell that is only an IPA/ASCII symbol label, short enough to be a row
# key rather than prose. /t/, [t], ʃ, t͡ʃ, and "t d" all qualify.
SYMBOL_CELL = re.compile(r'^[\s\[\]\/\(\)\u0250-\u02ff\u0361\.]+$')

# Acoustic columns: the thing that makes a table acoustic rather than
# articulatory or statistical. 'formant' must not match inside "Informant
# code", which is a subject id, so the look-behind is load-bearing.
ACOUSTIC_HEAD = re.compile(
    r'(?<!\bin)(?<!\bim)formants?\b|(?:^|[^a-z0-9])f[1-5](?:[^a-z0-9]|$)|'
    r'\bhz\b|burst|centroid|spectr|bandwidth|noise\s*spec', re.I)
STAT_TABLE = re.compile(
    r'model|glmm|mixed.effect|regression|anova|agreement|classif|accura|'
    r'predict|correlat|effect of|estimate|variance|likelihood|significan|'
    r'listeners?|participants?', re.I)
MEASURE_TABLE = re.compile(
    r'formant|spectr|frequenc|\bhz\b|\bdB\b|moment|centroid|peak|bandwidth|'
    r'energy', re.I)

# A column counts as naming a consonant only if its VALUES are consonants.
# Screening on the column NAME alone let vowel formant tables through, because
# vowel datasets carry a "vowel" column that no consonant filter rejected.
PLACE_WORDS = {'bilabial', 'labiodental', 'dental', 'alveolar', 'postalveolar',
               'retroflex', 'palatal', 'velar', 'uvular', 'pharyngeal',
               'glottal', 'labial', 'apical', 'laminal'}
MANNER_WORDS = {'stop', 'stops', 'plosive', 'fricative', 'fricatives',
                'affricate', 'affricates', 'nasal', 'nasals', 'liquid',
                'liquids', 'glide', 'glides', 'tap', 'trill', 'approximant'}
ASCII_CONS = {'p', 'b', 't', 'd', 'k', 'g', 'q', '\u0294', 'f', 'v', 'th',
              'dh', 's', 'z', '\u0283', '\u0292', 'x', '\u0263', 'h', 'm', 'n',
              '\u014B', 'l', 'r', '\u0279', 'w', 'j', 'l\u02D0', 'r\u02D0',
              't\u0361\u0283', 't\u0361\u0282', 'd\u0361\u0292', 'p\u0361'}
CONSONANT_HEADER = re.compile(
    r'consonant|segment|phone|poa|place_of_art|articulation|phoneme|'
    r'symbol|ipa', re.I)
# A title that names an IPA consonant is provenance in its own right. The
# clear/dark /l/ datasets carry no consonant column at all -- the /l/ is stated
# only in the dataset title -- and rejecting them would discard real consonant
# formants, while accepting on a column name alone would admit vowel tables.
# The IPA block also holds the vowel symbols, so the character class is built
# from the consonant inventory rather than from the whole U+0250..U+02FF range.
_BRACKETED_CONS = r'(?<![A-Za-z])[\[\/](?:t\u0361\u0283|d\u0361\u0292|p\u0361|[ptkbdgqfvsz\u0283\u0292x\u0263hmn\u014Blr\u0279wj\u0294])[\]\/](?![A-Za-z])'
# Only the non-ASCII part of the inventory may match freely: the ASCII letters
# in CONSONANTS are there for column-value matching, and letting them match
# bare text would make every title containing the letter "p" qualify.
CONSONANT_TITLE = re.compile(
    '[%s]|%s' % (re.escape(''.join(sorted(c for c in CONSONANTS if ord(c) > 127))),
                 _BRACKETED_CONS))

# Screen for downloaded tabular files: header must name an acoustic quantity,
# and the file must name a CONSONANT somewhere. Without the second condition a
# vowel formant table would pass and would silently become "consonant evidence".
CONSONANT_HEADER = re.compile(
    r'consonant|segment|phone|poa|place_of_art|articulation|phoneme|'
    r'symbol|ipa|stop|plosive|fricative|affricate|nasal|liquid|glide', re.I)

RESULTS = []


def note(source, url, ok, detail='', nbytes=0, elapsed=0.0):
    """Record one attempt. Every failure is kept, never swallowed."""
    RESULTS.append({'source': source, 'url': url, 'ok': bool(ok),
                    'bytes': int(nbytes), 'detail': detail,
                    'seconds': round(elapsed, 2)})
    print('  %-22s %-4s %s' % (source, 'OK' if ok else 'FAIL',
                               detail[:110]))
    return ok


def fetch(url, accept='*/*', max_bytes=None):
    """GET a URL. Returns (body, status, elapsed). Raises on transport error."""
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT, 'Accept': accept})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = r.read() if max_bytes is None else r.read(max_bytes)
        return body, r.status, time.time() - t0


def fetch_json(url, accept='application/json'):
    body, status, dt = fetch(url, accept)
    return json.loads(body.decode('utf-8', 'replace')), status, dt


def looks_binary_or_error(body, content_type=''):
    """True if the payload is not the tabular text we asked for."""
    if not body:
        return True
    if body[:2] == b'PK' or body[:2] == b'\x1f\x8b':
        return False                      # archive: unpackable, not an error
    head = body[:400].lower()
    if b'<html' in head or b'<!doctype' in head:
        return True
    if content_type and 'text' not in content_type and \
            'csv' not in content_type and 'json' not in content_type:
        return True
    return False


# ---------------------------------------------------------------------------
# 1. Direct probes of the sources named in the brief
# ---------------------------------------------------------------------------
DIRECT_PROBES = [
    # (label, url, why it matters)
    ('phonTools-home', 'https://www.phontools.com/',
     'named first in the brief; the 9 vowel rda files came from it'),
    ('phonTools-cran-data', 'https://api.github.com/repos/cran/phonTools/contents/data',
     'read-only CRAN mirror of phonTools; does it ship anything but vowels?'),
    ('PhoneticBank', 'https://www.phoneticbank.info/',
     'multi-language fricative/affricate spectra, named in the brief'),
    ('UCI-datasets-api', 'https://archive.ics.uci.edu/api/datasets?search=consonant',
     'named in the brief'),
    ('UCI-home', 'https://archive.ics.uci.edu/', 'is UCI reachable at all?'),
    ('Zenodo', 'https://zenodo.org/api/records?q=consonant&size=1',
     'large open phonetics archive, not named in the brief but worth one try'),
    ('HuggingFace', 'https://huggingface.co/', 'mirrors of speech datasets live here'),
    ('Harvard-Dataverse', 'https://dataverse.harvard.edu/api/search?q=consonant+formant',
     'the DOI host the brief points at; the data may live on DataverseNO'),
    ('CRAN-home', 'https://cran.r-project.org/', 'R phonetics packages ship data'),
    ('GitHub-raw', 'https://raw.githubusercontent.com/', 'fallback code host'),
    ('Wayback-CDX-phontools',
     'https://web.archive.org/cdx/search/cdx?url=phontools.com&matchType=domain&limit=20',
     'archived phonTools data files'),
    ('Wayback-CDX-phoneticbank',
     'https://web.archive.org/cdx/search/cdx?url=phoneticbank.info&matchType=domain&limit=20',
     'archived PhoneticBank spectra'),
]

# OpenSLR ids scanned for TIMIT. TIMIT is the standard phone-labelled American
# English corpus; if it were reachable it would settle the dead-axis question
# outright, so its absence is worth recording rather than assuming.
OPENSLR_SCAN = list(range(1, 60)) + list(range(90, 146))


def probe_direct():
    print('== direct source probes ==')
    for label, url, why in DIRECT_PROBES:
        try:
            body, status, dt = fetch(url, accept='*/*', max_bytes=4096)
            note(label, url, True, 'HTTP %d, %d B read -- %s'
                 % (status, len(body), why), len(body), dt)
        except urllib.error.HTTPError as e:
            note(label, url, False, 'HTTP %d %s -- %s' % (e.code, e.reason, why))
        except Exception as e:
            note(label, url, False, '%s: %s -- %s'
                 % (type(e).__name__, str(e)[:90], why))
        time.sleep(POLITE_S)

    # phonTools CRAN mirror: list the data files and count how many are named
    # after a vowel dataset. This is the direct test of "is phonTools a
    # consonant source at all".
    try:
        d, status, dt = fetch_json(
            'https://api.github.com/repos/cran/phonTools/contents/data')
        names = [f['name'] for f in d]
        print('  phonTools data dir holds %d files: %s'
              % (len(names), ' '.join(names)))
    except Exception as e:
        print('  phonTools data dir listing failed: %s: %s'
              % (type(e).__name__, str(e)[:90]))

    print('\n== OpenSLR scan for TIMIT (phone-labelled American English) ==')
    found = []
    for rid in OPENSLR_SCAN:
        try:
            body, _, _ = fetch('https://www.openslr.org/resources/%d/info.txt' % rid,
                               max_bytes=400)
            name = body.decode('utf-8', 'replace')
            nm = [l for l in name.splitlines() if l.startswith('name:')]
            nm = nm[0][5:].strip() if nm else '?'
            if 'timit' in nm.lower():
                found.append((rid, nm))
        except Exception:
            pass                                   # 404 = resource absent
        time.sleep(0.05)
    note('OpenSLR-TIMIT-scan',
         'https://www.openslr.org/resources/1..59,90..145/info.txt',
         bool(found),
         'TIMIT %s; scanned %d resource descriptors, no TIMIT'
         % ('found at ' + str(found) if found else 'ABSENT', len(OPENSLR_SCAN)))


# ---------------------------------------------------------------------------
# 2. DataverseNO sweep
# ---------------------------------------------------------------------------
# Query terms chosen because DataverseNO is a linguistics repository: every
# term below is a word that appeared in a published dataset title or abstract
# for consonant acoustics there.
DVN_QUERIES = [
    'consonant formant', 'clear dark l formant', 'sibilant acoustic',
    'fricative acoustic', 'stop burst acoustic', 'plosive acoustic',
    'spectral centroid fricative', 'formant frequency consonant',
    'nasal formant acoustic', 'affricate acoustic', 'spectral peak sibilant',
    'consonant acoustics', 'burst frequency', 'noise spectrum consonant',
]

DVN_PAGESIZE = 20


def dvn_candidates():
    dois = {}
    for q in DVN_QUERIES:
        url = ('https://dataverse.no/api/search?q=%s&type=dataset&per_page=%d'
               % (urllib.parse.quote(q), DVN_PAGESIZE))
        try:
            d, status, dt = fetch_json(url)
        except Exception as e:
            note('DataverseNO-search', url, False,
                 '%s: %s' % (type(e).__name__, str(e)[:90]))
            continue
        items = d.get('data', {}).get('items', [])
        for it in items:
            gid = it.get('global_id', '')
            if gid.startswith('doi:') and gid not in dois:
                dois[gid] = it.get('name', '')
        note('DataverseNO-search', url, True,
             '%d hits, %d datasets so far' % (d.get('data', {}).get('total_count', 0),
                                              len(dois)), 0, dt)
        time.sleep(POLITE_S)
    return dois


def dvn_files(doi):
    url = ('https://dataverse.no/api/datasets/:persistentId/?persistentId=%s'
           % urllib.parse.quote(doi, safe=''))
    try:
        d, status, dt = fetch_json(url)
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, str(e)[:80])
    ver = d['data']['latestVersion']
    title = ''
    for f in ver.get('metadataBlocks', {}).get('citation', {}).get('fields', []):
        if f.get('typeName') == 'title':
            title = f.get('value', '')
            break
    files = []
    for f in ver.get('files', []):
        df = f['dataFile']
        files.append({'id': df['id'], 'label': f.get('label') or df.get('filename', ''),
                      'bytes': df.get('filesize', 0),
                      'ctype': df.get('contentType', ''),
                      'format': df.get('originalFormatLabel', '')})
    return {'title': title, 'files': files}, ''


def split_rows(text):
    """Rows and the delimiter of a delimited text file, or (None, None)."""
    rows = [ln for ln in text.splitlines() if ln.strip()]
    if len(rows) < 3:
        return None, None
    counts = {';': text.count(';'), '\t': text.count('\t'),
              ',': text.count(','), '|': text.count('|')}
    sep = max(counts, key=counts.get)
    if counts[sep] < 2:
        return None, None
    return [r.split(sep) for r in rows], sep


def consonant_column(columns):
    """Names of columns that both LOOK like a segment label and CARRY one.

    Requiring the header to match as well as the values is what keeps vowel
    datasets out: their 'word' and 'gender' columns contain consonants by
    accident, and their 'prec_detailed' column really does hold consonant
    segments -- but the formants measured on that row belong to the vowel, not
    to the consonant in the next column.
    """
    good = []
    head = [h.strip() for h in columns[0]]
    for i, name in enumerate(head):
        if not CONSONANT_HEADER.search(name):
            continue
        vals = [r[i].strip() for r in columns[1:] if i < len(r) and r[i].strip()]
        if not vals:
            continue
        hits = 0
        for v in vals:
            low = v.lower()
            if (len(v) <= 3 and set(v) & CONSONANTS) or low in ASCII_CONS \
                    or low in PLACE_WORDS or low in MANNER_WORDS:
                hits += 1
        if hits >= 0.6 * len(vals):
            good.append(name)
    return good


def sniff_tabular(text, title=''):
    """Does this text hold MEASURED CONSONANT acoustics?

    Returns (ok, info, reason_not). Three things must hold together: a real
    acoustic measurement column, a consonant label that actually carries
    consonants, and enough rows to be a measurement rather than a dictionary.
    A vowel formant table fails the second test; a VOT duration table fails the
    first. Accepting on the dataset TITLE instead of a column is allowed, and is
    recorded separately, because some consonant datasets name the segment only
    in their title.
    """
    table, sep = split_rows(text)
    if table is None:
        return False, {}, 'fewer than 3 delimited rows'
    head = [h.strip() for h in table[0]]
    if len(head) < 3:
        return False, {}, 'fewer than 3 columns'
    body = table[1:]
    aco = [h for h in head if ACOUSTIC_HEAD.search(h)]
    con = consonant_column(table)
    title_evidence = bool(CONSONANT_TITLE.search(title or ''))
    info = {'acoustic_columns': aco, 'consonant_columns': con,
            'rows': len(body), 'delimiter': repr(sep),
            'consonant_evidence': ('column' if con else
                                   ('dataset title' if title_evidence else 'none'))}
    if not aco:
        return False, info, 'no acoustic measurement column'
    if not con and not title_evidence:
        return False, info, 'no column carries consonant labels'
    if len(body) < 20:
        return False, info, 'fewer than 20 data rows'
    return True, info, ''


def sweep_dataverse(dois):
    if not os.path.isdir(RAW):
        os.makedirs(RAW)
    kept, scanned, files_ok = [], 0, 0
    for i, doi in enumerate(sorted(dois), 1):
        meta, err = dvn_files(doi)
        scanned += 1
        if meta is None:
            note('DataverseNO-meta', doi, False, err)
            time.sleep(POLITE_S)
            continue
        for f in meta['files']:
            if f['bytes'] > MAX_TEXT_BYTES:
                continue
            if f['ctype'] and not re.search(r'text|csv|tsv|tab|json', f['ctype']):
                continue
            if not re.search(r'\.(txt|csv|tsv|tab|dat|asc)$', f['label'], re.I):
                continue
            url = 'https://dataverse.no/api/access/datafile/%d' % f['id']
            try:
                body, status, dt = fetch(url, accept='text/plain')
            except Exception as e:
                note('DataverseNO-file', url, False,
                     '%s: %s' % (type(e).__name__, str(e)[:80]))
                time.sleep(POLITE_S)
                continue
            files_ok += 1
            text = body.decode('utf-8', 'replace')
            ok, info, why = sniff_tabular(text, meta['title'])
            label = doi.rsplit('/', 1)[-1] + '_' + re.sub(r'\W+', '_', f['label'])
            name = label[:80] + '.txt'
            with io.open(os.path.join(RAW, name), 'w', encoding='utf-8') as fh:
                fh.write(text)
            note('DataverseNO-file', url, ok,
                 '%s | %d B | %s | acoustic=%s consonant=%s rows=%d%s'
                 % (doi.rsplit('/', 1)[-1], len(body), f['label'][:34],
                    ','.join(info['acoustic_columns'])[:40] or '-',
                    ','.join(info['consonant_columns'])[:30] or '-',
                    info.get('rows', 0),
                    '' if ok else ' | rejected: ' + why),
                 len(body), dt)
            if ok:
                rec = {'source': 'DataverseNO', 'doi': doi,
                       'title': meta['title'], 'file': name, 'url': url,
                       'bytes': len(body), 'original_label': f['label']}
                rec.update(info)
                kept.append(rec)
            time.sleep(POLITE_S)
    print('  scanned %d datasets, opened %d tabular files, kept %d'
          % (scanned, files_ok, len(kept)))
    return kept


# ---------------------------------------------------------------------------
# 3. emudata: measured consonant spectra with phoneme labels
# ---------------------------------------------------------------------------
EMUDATA_RAW = 'https://raw.githubusercontent.com/richardbeare/emudata/master/'
EMUDATA_TREE = ('https://api.github.com/repos/richardbeare/emudata/git/trees/'
                'master?recursive=1')

# R documentation files worth fetching: they are the only place the frequency
# axis of a spectral object is stated, and an unlabelled spectrum is not usable
# evidence. Whichever object has no documented axis is recorded as unlabelled
# rather than given an invented one.
EMUDATA_DOCS = ['stops10.Rd', 'stops10.lab.Rd', 'stops.dft.Rd', 'stops.bark.Rd',
                'keng.Rd', 'keng.dft.5.Rd', 'keng.l.Rd', 'dorfric.Rd',
                'sib.Rd', 'plos.Rd', 'dorsal.Rd', 'fr.Rd', 'stops.l.Rd']


def _rda_objects(path):
    """Objects inside an R data file, or the exact reason it cannot be read.

    pyreadr cannot load EMU trackdata (a trackdata object mixes a segment list
    with tier matrices in one SEXP). That limitation is reported per file
    rather than hidden, so the file is still worth storing for anyone with R.
    """
    try:
        import pyreadr
    except ImportError:
        return None, 'pyreadr not installed'
    try:
        return pyreadr.read_r(path), ''
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, str(e)[:110])


def _describe_object(v):
    """Shape and label vocabulary of one R object, as a short string."""
    try:
        shape = getattr(v, 'shape', None)
        if shape is not None and len(shape):
            head = '%dx%d' % (shape[0], shape[1]) if len(shape) > 1 else str(shape[0])
        else:
            head = type(v).__name__
        if hasattr(v, 'columns'):
            head += ' cols=%s' % list(v.columns)[:6]
        uniq = ''
        try:
            vals = list(v)
            flat = set()
            for x in vals[:400]:
                flat.update(str(x).split())
            if 0 < len(flat) <= 40:
                uniq = ' labels=%s' % ' '.join(sorted(flat))[:110]
        except Exception:
            pass
        return head + uniq
    except Exception as e:
        return 'undescribable: %s' % str(e)[:60]


def fetch_emudata():
    outdir = os.path.join(RAW, 'emudata')
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    docs, files, parsed = {}, [], 0
    try:
        tree, status, dt = fetch_json(EMUDATA_TREE)
    except Exception as e:
        note('emudata-tree', EMUDATA_TREE, False,
             '%s: %s' % (type(e).__name__, str(e)[:90]))
        return {'objects': {}, 'files': [], 'docs': {}}
    for blob in tree.get('tree', []):
        if blob['type'] != 'blob':
            continue
        p = blob['path']
        if p.startswith('data/') and p.endswith('.rda') \
                and blob.get('size', 0) <= EMUDATA_MAX_BYTES:
            files.append((p, blob.get('size', 0)))
    print('  emudata data/ holds %d .rda files under the cap' % len(files))

    for doc in EMUDATA_DOCS:
        url = EMUDATA_RAW + 'man/' + doc
        try:
            body, status, dt = fetch(url, accept='text/plain')
            txt = re.sub(r'\s+', ' ', body.decode('utf-8', 'replace'))
            t = re.search(r'\\title\{(.+?)\}\s*\\', txt + '\\')
            docs[doc] = (t.group(1).strip() if t else txt[:300])[:400]
        except Exception as e:
            docs[doc] = 'FETCH FAILED: %s: %s' % (type(e).__name__, str(e)[:60])
        time.sleep(0.1)

    for p, size in sorted(files):
        url = EMUDATA_RAW + p
        name = os.path.basename(p)
        local = os.path.join(outdir, name)
        try:
            body, status, dt = fetch(url, accept='application/octet-stream')
        except Exception as e:
            note('emudata-file', url, False,
                 '%s: %s' % (type(e).__name__, str(e)[:90]))
            continue
        with open(local, 'wb') as fh:
            fh.write(body)
        if body[:2] != b'\x1f\x8b':
            note('emudata-file', url, False,
                 '%s: %d B is not gzipped RDX2' % (name, len(body)))
            continue
        objs, err = _rda_objects(local)
        if objs is None:
            note('emudata-file', url, False,
                 '%s: %d B downloaded and stored, but NOT parsed here: %s'
                 % (name, len(body), err), len(body), dt)
        else:
            parsed += 1
            desc = '; '.join('%s = %s' % (k, _describe_object(v))
                             for k, v in sorted(objs.items()))
            note('emudata-file', url, True,
                 '%s: %d B | %s' % (name, len(body), desc[:200]), len(body), dt)
        time.sleep(POLITE_S)
    print('  parsed %d of %d emudata files in pure Python' % (parsed, len(files)))
    return {'objects': docs, 'files': [f for f, _ in sorted(files)],
            'docs': docs, 'parsed': parsed, 'total': len(files)}


def export_emudata_csv(outdir):
    """Write the emudata objects pyreadr can read as plain CSVs.

    Only stops10 and keng can be read without R, so only those two are
    exported. The frequency axis of both spectral objects is NOT stated in the
    package documentation, so the CSV keeps the raw T1..Tn column names and the
    manifest says the axis is unknown. Inventing an axis from the column count
    would turn a measurement into a fabrication.
    """
    try:
        import pyreadr
    except ImportError:
        print('  pyreadr missing; emudata CSVs not written')
        return []
    written = []
    jobs = [('stops10.rda', 'stops10', 'stops10.lab', 'stops10.lab',
             'emudata_stops10_b_d_g_spectra.csv',
             'German b/d/g, spectral matrix 10 ms after burst onset'),
            ('keng.rda', 'keng.dft.5', 'keng', 'labels',
             'emudata_keng_aspiration_spectra.csv',
             'Australian English /k/ aspiration noise, spectral matrix at midpoint')]
    for rda, matrix, segobj, segcol, name, desc in jobs:
        local = os.path.join(outdir, rda)
        if not os.path.exists(local):
            note('emudata-csv', name, False, '%s not downloaded yet' % rda)
            continue
        try:
            d = pyreadr.read_r(local)
            df = d[matrix].reset_index(drop=True)
            seg = [str(v) for v in d[segobj][segcol].tolist()]
            if len(seg) != len(df):
                raise ValueError('label row %d != spectrum row %d'
                                 % (len(seg), len(df)))
            df.insert(0, 'label', seg)
            if segobj == 'keng':
                # keng.l says whether the following vowel was front or back;
                # that is the only variation in this file, so keep it.
                df.insert(1, 'following_vowel',
                          [str(v) for v in d['keng.l']['keng.l'].tolist()])
            path = os.path.join(OUT, name)
            df.to_csv(path, index=False, encoding='utf-8')
            written.append({'file': name, 'rows': len(df),
                            'spectrum_columns': len(df.columns) - 1,
                            'labels': sorted(set(seg)), 'contents': desc})
            note('emudata-csv', name, True,
                 '%d rows x %d spectrum columns | labels %s | %s'
                 % (len(df), len(df.columns) - 1, ' '.join(sorted(set(seg))),
                    desc), os.path.getsize(path))
        except Exception as e:
            note('emudata-csv', name, False,
                 '%s: %s' % (type(e).__name__, str(e)[:90]))
    return written


# ---------------------------------------------------------------------------
# 4. Re-screening what is already on disk
# ---------------------------------------------------------------------------
def build_raw_index():
    """Map every file already in raw/ back to its dataset and title.

    The download stage already wrote the bytes; re-running it to change a
    screening rule would re-download 150 MB for nothing. The title matters to
    the screen (some consonant datasets name the segment only in the title), so
    it is recovered from the DataverseNO metadata API and cached.
    """
    index_path = os.path.join(RAW, 'raw_index.json')
    if os.path.exists(index_path):
        with io.open(index_path, encoding='utf-8') as fh:
            return json.load(fh)
    index = {}
    prefixes = sorted({fn.split('_')[0] for fn in os.listdir(RAW)
                       if fn.endswith('.txt')})
    for p in prefixes:
        meta, err = dvn_files('doi:10.18710/' + p)
        index[p] = {'title': meta['title'] if meta else '',
                    'files': [fn for fn in os.listdir(RAW)
                              if fn.endswith('.txt') and fn.startswith(p + '_')],
                    'error': err}
        note('raw-index', 'doi:10.18710/' + p, meta is not None,
             (meta['title'][:90] if meta else err))
        time.sleep(POLITE_S)
    with io.open(index_path, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(index, ensure_ascii=False, indent=1))
    return index


def screen_raw():
    """Apply the current screen to every downloaded file, offline.

    Records for files that are no longer on disk (deleted by the prune stage)
    are carried over from the previous report. Without that, re-screening after
    a prune would silently shrink the record from 914 files to the 2 that
    remain, which reads as "only 2 files were ever examined".
    """
    index = build_raw_index()
    report_path = os.path.join(OUT, 'screen_report.json')
    previous = {}
    if os.path.exists(report_path):
        with io.open(report_path, encoding='utf-8') as fh:
            previous = {r['file']: r for r in json.load(fh)}
    on_disk, kept = [], []
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith('.txt'):
            continue
        meta = index.get(fn.split('_')[0], {})
        with io.open(os.path.join(RAW, fn), encoding='utf-8',
                     errors='replace') as fh:
            text = fh.read()
        ok, info, why = sniff_tabular(text, meta.get('title', ''))
        rec = {'file': fn, 'title': meta.get('title', ''), 'accepted': ok,
               'reason': why, 'on_disk': True}
        rec.update(info)
        on_disk.append(rec)
        if ok:
            kept.append(rec)
    gone = []
    for fn, rec in previous.items():
        if fn not in {r['file'] for r in on_disk}:
            stale = dict(rec)
            stale['on_disk'] = False
            gone.append(stale)
    report = on_disk + gone
    print('  screened %d files on disk, %d accepted, %d rejected; '
          '%d earlier records carried over for deleted files'
          % (len(on_disk), len(kept), len(on_disk) - len(kept), len(gone)))
    for r in kept:
        print('    ACCEPT %-34s %-24s rows=%-5d acoustic=%s'
              % (r['file'][:34], r['consonant_evidence'], r.get('rows', 0),
                 ','.join(r['acoustic_columns'])[:40]))
    with io.open(report_path, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=1))
    with io.open(os.path.join(OUT, 'consonant_measurements.json'), 'w',
                 encoding='utf-8') as fh:
        fh.write(json.dumps(kept, ensure_ascii=False, indent=1))
    return {'screened': len(report), 'accepted': kept}


def measure_target(caption):
    """What the measured formants belong to: the consonant, or a vowel next to it.

    Several tables are keyed by a consonant but measure VOWEL formants in that
    consonant's context. That is real acoustic evidence about a consonant, and
    it is also exactly the kind of row that gets mistaken for consonant formants
    if the distinction is not recorded, so it is labelled rather than dropped.
    """
    has_vowel = bool(re.search(r'vowel', caption, re.I))
    has_cons = bool(re.search(r'consonant|fricative|plosive|stop|nasal|liquid',
                              caption, re.I))
    if has_vowel and has_cons:
        return 'consonant-conditioned (vowel formants keyed by consonant)'
    if has_cons:
        return 'consonant-internal'
    return 'unlabelled'


def classify_saved_rows():
    """Add measure_target to rows already written, without re-mining."""
    path = os.path.join(OUT, 'epmc_consonant_table_rows.json')
    if not os.path.exists(path):
        return 0
    with io.open(path, encoding='utf-8') as fh:
        rows = json.load(fh)
    for r in rows:
        r['measure_target'] = measure_target(r.get('caption', ''))
    with io.open(path, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(rows, ensure_ascii=False, indent=1))
    counts = {}
    for r in rows:
        counts[r['measure_target']] = counts.get(r['measure_target'], 0) + 1
    for k, v in sorted(counts.items()):
        print('  %-55s %d rows' % (k, v))
    return len(rows)


def prune_rejected():
    """Delete the raw files the screen rejected, keeping the audit record.

    The DataverseNO sweep pulls about 155 MB to find two files worth having.
    screen_report.json already records why each rejected file was rejected, so
    the bytes add nothing except disk. The accepted files and everything under
    raw/emudata/ are left alone.
    """
    report_path = os.path.join(OUT, 'screen_report.json')
    if not os.path.exists(report_path):
        print('  no screen_report.json; nothing pruned')
        return {'pruned': 0, 'bytes': 0}
    with io.open(report_path, encoding='utf-8') as fh:
        report = json.load(fh)
    gone, freed = 0, 0
    for r in report:
        if r['accepted']:
            continue
        path = os.path.join(RAW, r['file'])
        if os.path.exists(path):
            freed += os.path.getsize(path)
            os.remove(path)
            gone += 1
    print('  deleted %d rejected files, freed %.1f MB; %d files kept'
          % (gone, freed / 1e6, len(os.listdir(RAW))))
    return {'pruned': gone, 'bytes': freed}


# ---------------------------------------------------------------------------
# 5. Europe PMC open-access table mining
# ---------------------------------------------------------------------------
# One query per language. Tagging the language by the query rather than by
# guessing from the title is honest about provenance: the article is only
# labelled with a language we searched for, and the article title is stored
# next to every row so a reader can check whether the article really is about
# that language.
EPMC_QUERIES = [
    ('English', 'consonant AND "formant frequencies" AND OPEN_ACCESS:Y'),
    ('Hindi', '"Hindi" AND consonant AND formant AND OPEN_ACCESS:Y'),
    ('Bengali', '"Bengali" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Tamil', '"Tamil" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Telugu', '"Telugu" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Kannada', '"Kannada" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Malayalam', '"Malayalam" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Korean', '"Korean" AND stop AND (burst OR formant) AND OPEN_ACCESS:Y'),
    ('Mandarin', '"Mandarin" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Spanish', '"Spanish" AND fricative AND (spectral OR formant) AND OPEN_ACCESS:Y'),
    ('Arabic', '"Arabic" AND fricative AND (spectral OR formant) AND OPEN_ACCESS:Y'),
    ('Persian', '"Persian" AND fricative AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Greek', '"Greek" AND fricative AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Thai', '"Thai" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Hausa', '"Hausa" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Igbo', '"Igbo" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Zulu', '"Zulu" AND consonant AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Hebrew', '"Hebrew" AND fricative AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Turkish', '"Turkish" AND fricative AND (formant OR spectral) AND OPEN_ACCESS:Y'),
    ('Dutch', '"Dutch" AND fricative AND (formant OR spectral) AND OPEN_ACCESS:Y'),
]

EPMC_PAGE = 20


def clean(s):
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', s).replace('\u2212', '-').replace('\u2009', ' ') \
        .replace('\u00a0', ' ').strip()


NUMBER = re.compile(r'^-?\d{1,6}(?:\.\d+)?$')


def epmc_tables(pmcid):
    """Consonant acoustic rows in one open-access article."""
    url = ('https://www.ebi.ac.uk/europepmc/webservices/rest/%s/fullTextXML'
           % pmcid)
    try:
        body, status, dt = fetch(url, accept='application/xml')
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, str(e)[:80]), 0
    xml = body.decode('utf-8', 'replace')
    out, ncap = [], 0
    for m in re.finditer(r'<table-wrap\b.*?</table-wrap>', xml, re.S):
        tw = m.group(0)
        cm = re.search(r'<caption>.*?</caption>', tw, re.S)
        cap = clean(cm.group(0)) if cm else ''
        if not cap:
            continue
        # A caption about a statistical model is not a measurement table even
        # when the numbers inside it look like frequencies.
        if not MEASURE_TABLE.search(cap) or STAT_TABLE.search(cap):
            continue
        ncap += 1
        kind = 'hz' if re.search(r'\bHz\b|formant|frequenc', cap, re.I) else (
            'db' if re.search(r'dB', cap) else 'other')
        for tr in re.findall(r'<tr\b.*?</tr>', tw, re.S):
            cells = [clean(c) for c in
                     re.findall(r'<t[hd]\b.*?</t[hd]>', tr, re.S)]
            if len(cells) < 2:
                continue
            lab = [i for i, c in enumerate(cells)
                   if c and len(c) <= 10 and SYMBOL_CELL.match(c)
                   and (set(c) & CONSONANTS)]
            if not lab:
                continue
            vals = []
            for j, c in enumerate(cells):
                if j in lab:
                    continue
                c2 = c.replace(',', '')
                if NUMBER.match(c2):
                    vals.append(float(c2))
            if len(vals) < 2:
                continue
            if kind == 'hz' and not any(80 <= v <= 12000 for v in vals):
                continue
            if kind == 'db' and not any(-100 <= v <= 40 for v in vals):
                continue
            out.append({'symbols': ' '.join(cells[i] for i in lab),
                        'values': vals, 'row': cells[:10], 'kind': kind,
                        'caption': cap[:200]})
    return out, '', ncap


def mine_europepmc():
    rows, arts, caps = [], 0, 0
    seen = set()
    for lang, q in EPMC_QUERIES:
        url = ('https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%s'
               '&format=json&pageSize=%d&resultType=core'
               % (urllib.parse.quote(q), EPMC_PAGE))
        try:
            d, status, dt = fetch_json(url)
        except Exception as e:
            note('EPMC-search', url, False,
                 '%s: %s' % (type(e).__name__, str(e)[:80]))
            continue
        note('EPMC-search', url, True,
             '%s: %d hits' % (lang, d.get('hitCount', 0)), 0, dt)
        for it in d.get('resultList', {}).get('result', []):
            pmcid = it.get('pmcid')
            if not pmcid or pmcid in seen:
                continue
            seen.add(pmcid)
            got, err, ncap = epmc_tables(pmcid)
            if got is None:
                continue
            arts += 1
            caps += ncap
            if not got:
                continue
            note('EPMC-article', pmcid, True,
                 '%s | %d consonant rows from %d measurement tables | %s'
                 % (lang, len(got), ncap, (it.get('title') or '')[:60]))
            for g in got:
                g.update({'pmcid': pmcid, 'doi': it.get('doi', ''),
                          'title': (it.get('title') or '')[:180],
                          'journal': it.get('journalTitle', '')[:80],
                          'year': it.get('pubYear', ''),
                          'query_language': lang})
                rows.append(g)
            time.sleep(POLITE_S)
        time.sleep(POLITE_S)
    print('  read %d open-access articles, %d measurement captions, '
          '%d consonant rows' % (arts, caps, len(rows)))
    return rows


def write_epmc(rows):
    if not rows:
        return
    path = os.path.join(OUT, 'epmc_consonant_table_rows.json')
    with io.open(path, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(rows, ensure_ascii=False, indent=1))
    print('  wrote tools/data/consonant/epmc_consonant_table_rows.json '
          '(%d rows)' % len(rows))


def main():
    # --stage lets one stage be re-run without repeating the network sweep that
    # precedes it; the stages are independent because each one records its own
    # outcome in RESULTS.
    stages = ('probe', 'dataverse', 'screen', 'prune', 'emudata', 'epmc', 'classify')
    want = stages
    if len(sys.argv) > 2 and sys.argv[1] == '--stage':
        want = tuple(s.strip() for s in sys.argv[2].split(',') if s.strip())
        bad = [s for s in want if s not in stages]
        if bad:
            print('unknown stage(s): %s (choose from %s)'
                  % (','.join(bad), ','.join(stages)))
            return 2

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    socket.setdefaulttimeout(TIMEOUT)

    print('== fetch_consonant_data ==')
    kept, emu, rows, screen = [], {}, [], {'screened': 0, 'accepted': []}
    classified = 0
    pruned = {}
    if 'probe' in want:
        probe_direct()
    if 'dataverse' in want:
        print('\n== DataverseNO sweep ==')
        dois = dvn_candidates()
        print('  %d candidate datasets' % len(dois))
        kept = sweep_dataverse(dois)
    if 'screen' in want:
        print('\n== re-screen everything on disk ==')
        screen = screen_raw()
    if 'emudata' in want:
        print('\n== emudata (measured consonant spectra) ==')
        emu = fetch_emudata()
        emu['csvs'] = export_emudata_csv(os.path.join(RAW, 'emudata'))
    if 'classify' in want:
        print('\n== label what each mined row actually measures ==')
        classified = classify_saved_rows()
    if 'prune' in want:
        print('\n== delete rejected downloads ==')
        pruned = prune_rejected()
    if 'epmc' in want:
        print('\n== Europe PMC open-access tables ==')
        rows = mine_europepmc()
        write_epmc(rows)

    # Each stage writes its own file and the top-level manifest is rebuilt from
    # whatever stage files exist, so re-running one stage with --stage cannot
    # erase the record of the stages that already ran.
    stage_files = {'probe': 'stage_probe.json', 'dataverse': 'stage_dataverse.json',
                   'screen': 'stage_screen.json',
                   'emudata': 'stage_emudata.json', 'epmc': 'stage_epmc.json',
                   'prune': 'stage_prune.json',
                   'classify': 'stage_classify.json'}
    payload = {'probe': {'probes': RESULTS}, 'dataverse': {'dataverse_no_kept': kept},
               'screen': {'screen_screened': screen['screened'],
                          'screen_accepted': screen['accepted']},
               'emudata': {'emudata': emu},
               'classify': {'classified_rows': classified},
               'prune': {'pruned': pruned if 'prune' in want else {}},
               'epmc': {'epmc_rows': len(rows),
                        'epmc_languages_queried': len(EPMC_QUERIES)}}
    for st in want:
        with io.open(os.path.join(OUT, stage_files[st]), 'w',
                     encoding='utf-8') as fh:
            fh.write(json.dumps(payload[st], ensure_ascii=False, indent=1))

    merged = {'probes': [], 'dataverse_no_kept': [], 'emudata': {},
              'epmc_rows': 0, 'epmc_languages_queried': 0,
              'screen_screened': 0, 'screen_accepted': [], 'stages_present': []}
    for st, fn in stage_files.items():
        path = os.path.join(OUT, fn)
        if not os.path.exists(path):
            # An earlier full run wrote a single manifest with no per-stage
            # split. Adopt its results instead of losing the record of a stage
            # that already ran and whose network sweep is expensive.
            legacy = os.path.join(OUT, 'fetch_manifest.json')
            if os.path.exists(legacy):
                with io.open(legacy, encoding='utf-8') as fh:
                    old = json.load(fh)
                if st == 'probe':
                    merged['probes'].extend(old.get('probes', []))
                    merged['stages_present'].append(st)
                elif st == 'dataverse':
                    merged['dataverse_no_kept'].extend(old.get('dataverse_no_kept', []))
                    merged['stages_present'].append(st)
                elif st == 'emudata' and old.get('emudata'):
                    merged['emudata'] = old['emudata']
                    merged['stages_present'].append(st)
                elif st == 'epmc' and old.get('epmc_rows') is not None:
                    merged['epmc_rows'] = old.get('epmc_rows', 0)
                    merged['epmc_languages_queried'] = old.get('epmc_languages_queried', 0)
                    merged['stages_present'].append(st)
            continue
        with io.open(path, encoding='utf-8') as fh:
            got = json.load(fh)
        merged['stages_present'].append(st)
        merged['probes'].extend(got.get('probes', []))
        merged['dataverse_no_kept'].extend(got.get('dataverse_no_kept', []))
        if got.get('screen_accepted') is not None:
            merged['screen_screened'] = got.get('screen_screened', 0)
            merged['screen_accepted'] = got.get('screen_accepted', [])
        if got.get('emudata'):
            merged['emudata'] = got['emudata']
        merged['epmc_rows'] += got.get('epmc_rows', 0)
        merged['epmc_languages_queried'] = max(
            merged['epmc_languages_queried'], got.get('epmc_languages_queried', 0))
    RESULTS[:] = merged['probes']
    kept = merged['dataverse_no_kept']
    emu = merged['emudata']
    with io.open(os.path.join(OUT, 'fetch_manifest.json'), 'w',
                 encoding='utf-8') as fh:
        fh.write(json.dumps(merged, ensure_ascii=False, indent=1))

    ok = [r for r in RESULTS if r['ok']]
    bad = [r for r in RESULTS if not r['ok']]
    print('\n== summary ==')
    print('  attempts           : %d (%d ok, %d failed)'
          % (len(RESULTS), len(ok), len(bad)))
    print('  bytes retrieved    : %d' % sum(r['bytes'] for r in RESULTS))
    print('  first-pass sweep kept   : %d (superseded by the offline screen)'
          % len(kept))
    print('  files screened offline  : %d, accepted %d'
          % (merged['screen_screened'], len(merged['screen_accepted'])))
    print('  emudata files stored     : %d (%d parsed, %d CSVs written)'
          % (len(emu.get('files', [])), emu.get('parsed', 0),
             len(emu.get('csvs', []))))
    print('  consonant table rows    : %d' % merged['epmc_rows'])
    print('  stages recorded     : %s' % ', '.join(merged['stages_present']))
    if not kept and not merged['epmc_rows'] and not emu.get('parsed', 0):
        print('\n  NO CONSONANT ACOUSTIC DATA WAS OBTAINED.')
        print('  This is a negative result, not a licence to substitute vowel')
        print('  data. See fetch_manifest.json for every attempt and error.')
    print('\nwrote tools/data/consonant/')


if __name__ == '__main__':
    sys.exit(main())