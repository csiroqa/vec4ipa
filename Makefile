CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra -std=c11 -Wno-unused-function -Wno-unused-variable
# Windows: many setups only have the Python launcher 'py' on PATH; prefer
# it (Python 3) when it works, else fall back to 'python'.
ifeq ($(OS),Windows_NT)
PYTHON  ?= $(shell py -3 -c "import sys" >/dev/null 2>&1 && echo py -3 || echo python)
else
PYTHON  ?= python
endif
LDFLAGS :=
SRC     := src
VECTORS_H := $(SRC)/vectors.h

# Windows: gcc emits <name>.exe, so the targets must carry the .exe
# suffix or make re-links them on every run.
ifeq ($(OS),Windows_NT)
EXE_SUFFIX := .exe
else
EXE_SUFFIX :=
endif

TARGETS := ipa2vec$(EXE_SUFFIX) vec2ipa$(EXE_SUFFIX) vec4ipa$(EXE_SUFFIX)
ifeq ($(OS),Windows_NT)
TARGETS += ui/vec4ipa_ui$(EXE_SUFFIX)
endif

# Windows: wmain-based UTF-8 argv handling needs -municode
ifeq ($(OS),Windows_NT)
LDFLAGS += -municode
endif

all: $(TARGETS)

CORE := $(SRC)/ipa2vec_core.h
SCHEME ?= tools/data/spec_next.scheme   # default build = SPEC-NEXT 16-D scheme

ipa2vec$(EXE_SUFFIX): $(SRC)/ipa2vec_main.c $(SRC)/readme_embed.h $(VECTORS_H) $(CORE)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)/ipa2vec_main.c

vec2ipa$(EXE_SUFFIX): $(SRC)/vec2ipa_main.c $(SRC)/readme_embed.h $(VECTORS_H) $(CORE)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)/vec2ipa_main.c

vec4ipa$(EXE_SUFFIX): $(SRC)/vec4ipa_main.c $(SRC)/readme_embed.h $(VECTORS_H) $(CORE)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)/vec4ipa_main.c

# Win32 GUI wrapper (Windows only) — lives in ui/
ui/vec4ipa_ui$(EXE_SUFFIX): ui/vec4ipa_ui.c ui/app.res $(SRC)/ipa2vec_core.h $(SRC)/readme_embed.h
	$(CC) $(CFLAGS) -mwindows -municode -o $@ ui/vec4ipa_ui.c ui/app.res \
	    -lcomctl32 -lcomdlg32 -lshell32 -lole32

ui/app.res: ui/app.rc ui/vec_ipa.ico ipa2vec$(EXE_SUFFIX) vec2ipa$(EXE_SUFFIX) vec4ipa$(EXE_SUFFIX)
	@if ! command -v windres >/dev/null 2>&1; then \
		echo "error: windres not found (ui/vec4ipa_ui needs it) - install binutils or build the CLI tools only" >&2; \
		exit 1; \
	fi
	windres ui/app.rc -O coff -o ui/app.res

$(SRC)/readme_embed.h: tools/gen_readme_embed.py README.md
	$(PYTHON) tools/gen_readme_embed.py

$(VECTORS_H): tools/gen_vectors_h.py IPA_VECTORS.md metric.json src/names.tsv $(SCHEME)
	$(PYTHON) tools/gen_vectors_h.py $(if $(SCHEME),--scheme $(SCHEME),)

gen: $(VECTORS_H) $(SRC)/readme_embed.h

ifeq ($(OS),Windows_NT)
DEL_CMD = cmd /c del /Q /F
DEL_TARGETS = $(subst /,\,$(TARGETS))
else
DEL_CMD = rm -f
DEL_TARGETS = $(TARGETS) $(addsuffix .exe,$(TARGETS))
endif

clean:
	-$(DEL_CMD) $(DEL_TARGETS)

.PHONY: all clean gen
