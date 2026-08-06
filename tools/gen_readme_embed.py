#!/usr/bin/env python3
"""Generate src/readme_embed.h: README.md embedded as a C string."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
src = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
out = ['/* Auto-generated from README.md — do not edit. */',
       '#ifndef IPA2VEC_README_EMBED_H',
       '#define IPA2VEC_README_EMBED_H',
       '',
       'static const char *EMBEDDED_README =',
       '"' + '\\n"\n"'.join(
           l.replace('\\', '\\\\').replace('"', '\\"') for l in src.split('\n')) + '\\n";',
       '',
       '#endif /* IPA2VEC_README_EMBED_H */']
with open(os.path.join(ROOT, 'src', 'readme_embed.h'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(out) + '\n')
print('readme_embed.h written')
