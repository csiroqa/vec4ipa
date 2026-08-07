CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra -std=c11 -Wno-unused-function -Wno-unused-variable
LDFLAGS :=
SRC     := src
VECTORS_H := $(SRC)/vectors.h

TARGETS := ipa2vec vec2ipa vec4ipa
ifeq ($(OS),Windows_NT)
TARGETS += ipa2vec_ui
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
ipa2vec_ui: ui/ipa2vec_ui.c
	$(CC) $(CFLAGS) -mwindows -municode -o $@ ui/ipa2vec_ui.c \
	    -lcomctl32 -lcomdlg32 -lshlwapi

$(SRC)/readme_embed.h: tools/gen_readme_embed.py README.md
	python3 tools/gen_readme_embed.py

$(VECTORS_H): tools/gen_vectors_h.py IPA_VECTORS.md metric.json src/names.tsv
	python3 tools/gen_vectors_h.py

gen: $(VECTORS_H)

clean:
	rm -f $(TARGETS)

.PHONY: all clean gen
