# BruceWorx hooks

Headless FreeCAD commands and BruceWorx part numbers. This folder is a
self-contained add-on: it does not modify FreeCAD's C++ sources and it does
not have to be compiled. Copy the folder out of this repository when the
add-on is split into its own repo (FCB-P2-01/02 is still open; see below).

Part numbers look like `LE-01-01001-001-A`: `{PROG}-{DT}-{PPPPP}-{SSS}-{REV}`.

## Layout

| Path | Role |
|---|---|
| `hooks.py` | CLI entry point (FCB-P2-14) |
| `bruceworx/` | Library: numbering, JSON source, tree, STEP export |
| `config/document_types.json` | Editable document-type codes (placeholders until Bruce fills them in) |
| `config/numbering.example.json` | Committed counter template |
| `config/numbering.json` | Local counter, created on first `next` or `rename` (not committed) |
| `macros/PartNumber.FCMacro` | GUI / macro entry (FCB-P2-04/05) |
| `tests/` | Unit tests, plus a FreeCADCmd smoke test |
| `package.xml` | FreeCAD add-on metadata, for a later split |

## CLI

From the repository root. `next` and `preview` run with plain Python.
`export-step`, `list-tree` and `rename` need FreeCADCmd.

FreeCAD's own parser rejects unknown flags such as `--input`. Put `--` before
the script, or pass the command in `BW_HOOKS_ARGS`. Both are supported.
`hooks.py` must be the first file FreeCAD is asked to open: it exits after
the command, so later paths are not opened a second time.

```sh
# Allocate the next parent drawing (sub 001). Writes config/numbering.json
# on first use. --dt is an alias for --document-type.
python3 addons/BruceWorx/hooks.py next --program LE --document-type 01

# Next sub-assembly under an existing parent. Does not take a new PPPPP.
python3 addons/BruceWorx/hooks.py next --program LE --document-type 01 --parent 01001

# Show the next number and leave the counter alone.
python3 addons/BruceWorx/hooks.py preview --program LE --document-type 01 \
  --config path/to/numbering.json

# Export STEP (FCB-P2-11).
FreeCADCmd -- addons/BruceWorx/hooks.py export-step \
  --input part.FCStd --output part.step

# List the document tree as JSON (FCB-P2-12).
FreeCADCmd -- addons/BruceWorx/hooks.py list-tree \
  --input part.FCStd --output tree.json

# Number labels and save <part-number>.FCStd (FCB-P2-13).
FreeCADCmd -- addons/BruceWorx/hooks.py rename \
  --input part.FCStd --program LE --document-type 01
```

The same commands with the environment variable, which never goes through
FreeCAD's flag parser:

```sh
BW_HOOKS_ARGS='export-step --input part.FCStd --output part.step' \
  FreeCADCmd addons/BruceWorx/hooks.py

BW_HOOKS_ARGS='list-tree --input part.FCStd --output tree.json' \
  FreeCADCmd addons/BruceWorx/hooks.py

BW_HOOKS_ARGS='rename --input part.FCStd --program LE --document-type 01' \
  FreeCADCmd addons/BruceWorx/hooks.py
```

`python3 -m bruceworx ...` works when `addons/BruceWorx` is on `PYTHONPATH`.

Every command prints one machine-readable line:

```text
BW_RESULT {"command":"next","config":".../numbering.json","document_type":"01","ok":true,"parent":"01001","part_number":"LE-01-01001-001-A","program":"LE","sub":"001"}
```

FreeCADCmd also writes its own log lines. Grep for `BW_RESULT`, or pass
`--output` and read that file. `list-tree --output` writes the tree document
itself (pretty JSON). The `BW_RESULT` line then only points at the file.

### Commands

`export-step --input FILE.FCStd --output FILE.step [--objects Name,Label]`

Recomputes, exports solid root objects (a PartDesign Body, not the Pad inside
it) to STEP. `--objects` limits the export to those Name or Label values.
`.stp` is accepted. The writer tries `Import.export`, then `Part.export`.

`list-tree --input FILE.FCStd [--output tree.json]`

```json
{
  "schema": "bruceworx.document-tree.v1",
  "document": {"name": "BoxDoc", "label": "box", "file": "/path/box.FCStd"},
  "tree": [
    {"name": "Box", "label": "Box", "typeid": "Part::Box", "children": []}
  ]
}
```

Roots are objects that are not in another object's `OutList`. A cycle is a
child with `"cycle": true` and no further children.

`rename --input FILE.FCStd --program LE --document-type 01 [--config FILE]`
`[--revision A] [--parent PPPPP] [--objects Name,Label] [--output FILE.FCStd]`

Allocates one number per solid root, sets each object's `Label`, and saves.
With no `--output`, the file is `<directory>/<part-number>.FCStd` using the
first number (`LE-01-01001-001-A.FCStd`).

With no `--parent`, the first object takes a new parent drawing and
sub-assembly `001`. Further objects in that same run are `002`, `003`, ...
under that parent. `--parent 01001` numbers every object as the next
sub-assembly of drawing `01001` and does not consume a new `PPPPP`. The
document label and the default file name are the first number.

FreeCAD 1.1 will not rename a document's internal `Name`
(`Application::renameDocument` throws). `saveAs` and the next `openDocument`
set `Document.Label` from the file name, so saving as `<part-number>.FCStd`
is how the visible document name sticks (`LE-01-01001-001-A`). The internal
`Name` is that stem with FreeCAD's identifier rules applied, so the hyphens
become underscores (`LE_01_01001_001_A`). A custom `--output` uses that
file's stem as the document label instead. Object labels are stored in the
file either way.

`next --program LE --document-type 01 [--config FILE] [--revision A] [--parent PPPPP]`

Reserves the next number and advances the counter. Omit `--parent` to take
the next parent drawing for that program and document type (sub `001`).
Pass `--parent` to take the next sub-assembly under that drawing.

`preview --program LE --document-type 01 [--config FILE] [--revision A] [--parent PPPPP]`

Prints the next number. Does not write.

Exit codes: `0` success, `2` usage, `1` error.

## Part numbers

`{PROG}-{DT}-{PPPPP}-{SSS}-{REV}`

| Field | Rule | Example |
|---|---|---|
| PROG | 1–8 characters, a letter then letters or digits | `LE` |
| DT | Two digits, `00`–`99`. `1` is accepted and stored as `01` | `01` |
| PPPPP | Five digits, `00000`–`99999`. Next value is per program and document type | `01001` |
| SSS | Three digits, `000`–`999`. Next value is per parent drawing | `001` |
| REV | 1–3 letters | `A` |

`LE-01-01001-001-A` is program `LE`, document type `01`, parent drawing
`01001`, sub-assembly `001`, revision `A`. Program codes and revisions are
uppercased. `--revision` overrides the revision for that call and does not
change the revision stored in the file.

`OW` and `SI` are the same kind of program code as `LE`. The example counter
only defines `LE`. Add a program to the numbering file before allocating it.

Which objects are numbered, for both `rename` and the macro:

1. `--objects` or the GUI selection, if there is one.
2. Otherwise objects that own a solid, excluding anything that is a child of
   another selected solid. A sketch (no solids) is skipped.
3. If nothing qualifies, only the document is named and no object label changes.

### Document types

`config/document_types.json` is the code table. The shipped file is
placeholder data: `placeholder` is true, and codes `01` and `02` are named
`PLACEHOLDER`. They are not real BruceWorx document types. Bruce replaces
the entries. Placeholder codes are usable so `LE-01-01001-001-A` can be
issued before the real table exists. An unknown code is an error.

The numbering file points at that table with `document_types_file`
(default `document_types.json`, resolved next to the numbering file). A
copied `numbering.json` in `config/` therefore picks up edits to the type
table. An embedded `document_types` object overrides the file.

### Numbering file

`config/numbering.example.json`:

```json
{
  "source": "json",
  "format": "{PROG}-{DT}-{PPPPP}-{SSS}-{REV}",
  "document_types_file": "document_types.json",
  "programs": {
    "LE": {
      "revision": "A",
      "counters": {
        "01": {"next_parent": 1001, "parents": {}}
      }
    }
  }
}
```

`format` must be `{PROG}-{DT}-{PPPPP}-{SSS}-{REV}`. The old
`{PROG}-{NNNNN}-{REV}` form and the `number_width` key are rejected.

Counters are scoped:

* `counters[<DT>].next_parent` is the next `PPPPP` for that program and
  document type. A new top-level allocation issues that parent with
  sub-assembly `001`, then advances `next_parent`. Document types do not
  share the sequence: `LE` / `02` starts at `1001` even after `LE` / `01`
  has moved on.
* `counters[<DT>].parents[<PPPPP>].next_sub` is the next `SSS` under that
  parent. `--parent` (or `BW_PARENT`) only advances that sub counter.
  The parent must already have been issued.

The file is rewritten atomically (`os.replace`) and is a single-writer
counter. The first issued parent in the example is `01001` (`next_parent`
`1001`) and the first sub-assembly is `001`.

Resolution when `--config` is omitted:

* `config/numbering.json` if it exists
* otherwise the example, for `preview`
* `next` and `rename` copy the example to `config/numbering.json` on first use

Pass `--config` to keep a counter somewhere else. Do not allocate against the
example file if you want it to stay at `LE-01-01001-001-A`.

### Ops API later (FCB-P2-03)

Callers use `bruceworx.sources.NumberSource`:

* `allocate(program, document_type, revision=None, parent=None) -> str`
* `preview(program, document_type, revision=None, parent=None) -> str`
* `programs() -> list[str]`
* `document_types() -> list[str]`

`parent` omitted or `None` reserves the next parent drawing and its first
sub-assembly. A five-digit parent reserves only the next sub-assembly under
that drawing.

`open_number_source(path)` reads JSON. `open_number_source({"source": "ops",
"base_url": "https://ops.example/api", "token_env": "BW_OPS_TOKEN"})` returns
`OpsApiNumberSource`. Building that object is allowed. `allocate` and
`preview` raise `NotImplementedError` and do not make a network call.

The intended request, for the reader that replaces those two methods:

```http
POST {base_url}/part-numbers
{"program": "LE", "document_type": "01", "revision": "A", "parent": null}

{"part_number": "LE-01-01001-001-A"}
```

`parent` is `"01001"` when the caller wants the next sub-assembly only.
Bearer token from the `token_env` variable (default `BW_OPS_TOKEN`).

## Macro

`macros/PartNumber.FCMacro` numbers the active document. It uses the GUI
selection when there is one. Program, document type, parent and config can
be set with `BW_PROGRAM`, `BW_DOCUMENT_TYPE` (or `BW_DT`), `BW_PARENT`,
`BW_REVISION` and `BW_NUMBERING_CONFIG`.

The shipped type table has more than one code, so the macro requires
`BW_DOCUMENT_TYPE` (or `BW_DT`) until the table has exactly one type. One
run with several objects shares a new parent (`001`, `002`, ...).
`BW_PARENT` continues an existing drawing instead.

To show up as a FreeCAD add-on, symlink or copy this folder into the FreeCAD
`Mod` directory (the folder name `BruceWorx` matches `package.xml`). Headless
use does not need that.

## Tests

Unit tests use the system Python. They do not import FreeCAD:

```sh
python3 -m unittest discover -s addons/BruceWorx/tests -v
```

With a pixi-installed FreeCADCmd on `PATH`:

```sh
pixi run bash addons/BruceWorx/tests/run_freecad_smoke.sh
```

That creates a box, exports STEP, imports the STEP back, checks the solid
volume, writes the tree, renames to `LE-01-01001-001-A` (internal name
`LE_01_01001_001_A`), then runs `hooks.py` both via `BW_HOOKS_ARGS` and via
`FreeCADCmd --`.

Linux CI runs the unit tests in the `hooks-python` job and the smoke script
after the Linux install step. The self-hosted macOS runner is unchanged.

## Extracting this folder

FCB-P2-01/02 (ship the add-on inside this fork, or as a separate repo) is
still open. Until Bruce decides, the add-on lives here at `addons/BruceWorx`
so a later split is a copy, not a rewrite:

```sh
cp -a addons/BruceWorx /path/to/BruceWorx
```

Nothing under `src/` imports this package. There is no CMake target and no
C++ change. `package.xml` is the FreeCAD add-on manifest. The license is
LGPL-2.1-or-later (`LICENSE` in this folder).
