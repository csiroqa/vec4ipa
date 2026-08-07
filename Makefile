CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra -std=c11 -Wno-unused-function -Wno-unused-variable
PYTHON  ?= python
LDFLAGS :=
SRC     := src
VECTORS_H := $(SRC)/vectors.h

TARGETS := ipa2vec vec2ipa vec4ipa
ifeq ($(OS),Windows_NT)
TARGETS += ui/vec4ipa_ui
endif

# Windows: wmain-based UTF-8 argv handling needs -municode
ifeq ($(OS),Windows_NT)
LDFLAGS += -municode
endif

all: $(TARGETS)

ipa2vec: $(SRC)/ipa2vec_main.c $(VECTORS_H)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)/ipa2vec_main.c

vec2ipa: $(SRC)/vec2ipa_main.c $(VECTORS_H)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)/vec2ipa_main.c

vec4ipa: $(SRC)/vec4ipa_main.c $(SRC)/readme_embed.h $(VECTORS_H)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)/vec4ipa_main.c

# Win32 GUI wrapper (Windows only) — lives in ui/
ui/vec4ipa_ui: ui/vec4ipa_ui.c ui/app.res
	$(CC) $(CFLAGS) -mwindows -municode -o $@ ui/vec4ipa_ui.c ui/app.res \
	    -lcomctl32 -lcomdlg32 -lshlwapi -lshell32 -lole32

ui/app.res: ui/app.rc ui/vec_ipa.ico ipa2vec.exe vec2ipa.exe vec4ipa.exe
	windres ui/app.rc -O coff -o ui/app.res

$(SRC)/readme_embed.h: tools/gen_readme_embed.py README.md
	$(PYTHON) tools/gen_readme_embed.py

$(VECTORS_H): tools/gen_vectors_h.py IPA_VECTORS.md metric.json src/names.tsv
	$(PYTHON) tools/gen_vectors_h.py

gen: $(VECTORS_H)

clean:
	rm -f $(TARGETS)

.PHONY: all clean gen
