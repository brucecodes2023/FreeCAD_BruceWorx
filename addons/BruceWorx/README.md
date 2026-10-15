# BruceWorx hooks

Headless FreeCAD commands and BruceWorx part numbers. This folder is a
self-contained add-on: it does not modify FreeCAD's C++ sources and it does
not have to be compiled. Copy the folder out of this repository when the
add-on is split into its own repo (FCB-P2-01/02 is still open; see below).

Part numbers look like `LE-01001-A`: `{PROG}-{NNNNN}-{REV}`.

## Layout

| Path | Role |
|---|---|
| `hooks.py` | CLI entry point (FCB-P2-14) |
| `bruceworx/` | Library: numbering, JSON source, tree, STEP export |
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
# Allocate the next number. Writes config/numbering.json on first use.
python3 addons/BruceWorx/hooks.py next --program LE

# Show the next number and leave the counter alone.
python3 addons/BruceWorx/hooks.py preview --program LE --config path/to/numbering.json

# Export STEP (FCB-P2-11).
FreeCADCmd -- addons/BruceWorx/hooks.py export-step \
  --input part.FCStd --output part.step

# List the document tree as JSON (FCB-P2-12).
FreeCADCmd -- addons/BruceWorx/hooks.py list-tree \
  --input part.FCStd --output tree.json

# Number labels and save <part-number>.FCStd (FCB-P2-13).
FreeCADCmd -- addons/BruceWorx/hooks.py rename \
  --input part.FCStd --program LE
```

The same commands with the environment variable, which never goes through
FreeCAD's flag parser:

```sh
BW_HOOKS_ARGS='export-step --input part.FCStd --output part.step' \
  FreeCADCmd addons/BruceWorx/hooks.py

BW_HOOKS_ARGS='list-tree --input part.FCStd --output tree.json' \
  FreeCADCmd addons/BruceWorx/hooks.py

BW_HOOKS_ARGS='rename --input part.FCStd --program LE --config config/numbering.json' \
  FreeCADCmd addons/BruceWorx/hooks.py
```

`python3 -m bruceworx ...` works when `addons/BruceWorx` is on `PYTHONPATH`.

Every command prints one machine-readable line:

```text
BW_RESULT {"command":"next","config":".../numbering.json","ok":true,"part_number":"LE-01001-A","program":"LE"}
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

`rename --input FILE.FCStd --program LE [--config FILE] [--revision A]`
`[--objects Name,Label] [--output FILE.FCStd]`

Allocates one number per solid root, sets each object's `Label`, and saves.
With no `--output`, the file is `<directory>/<part-number>.FCStd` using the
first number (`LE-01001-A.FCStd`).

FreeCAD 1.1 will not rename a document's internal `Name`
(`Application::renameDocument` throws). `saveAs` and the next `openDocument`
set `Document.Label` from the file name, so saving as `<part-number>.FCStd`
is how the visible document name sticks (`LE-01001-A`). The internal `Name`
is that stem with FreeCAD's identifier rules applied, so the hyphens become
underscores (`LE_01001_A`). A custom `--output` uses that file's stem as the
document label instead. Object labels are stored in the file either way.

`next --program LE [--config FILE] [--revision A]`

Reserves the next number and advances the counter.

`preview --program LE [--config FILE] [--revision A]`

Prints the next number. Does not write.

Exit codes: `0` success, `2` usage, `1` error.

## Part numbers

`{PROG}-{NNNNN}-{REV}`

| Field | Rule | Example |
|---|---|---|
| PROG | 1–8 characters, a letter then letters or digits | `LE` |
| NNNNN | Five digits, `00000`–`99999` | `01001` |
| REV | 1–3 letters | `A` |

`LE-01001-A` is program `LE`, sequence `1001`, revision `A`. Codes and
revisions are uppercased. `--revision` overrides the revision for that call
and does not change the revision stored in the file.

Which objects are numbered, for both `rename` and the macro:

1. `--objects` or the GUI selection, if there is one.
2. Otherwise objects that own a solid, excluding anything that is a child of
   another selected solid. A sketch (no solids) is skipped.
3. If nothing qualifies, only the document is named and no object label changes.

### Numbering file

`config/numbering.example.json`:

```json
{
  "source": "json",
  "format": "{PROG}-{NNNNN}-{REV}",
  "number_width": 5,
  "programs": {
    "LE": {"description": "optional", "revision": "A", "next": 1001}
  }
}
```

`format` must be `{PROG}-{NNNNN}-{REV}` and `number_width` must be `5`.
`next` is the next sequence integer to issue. The file is rewritten
atomically (`os.replace`) and is a single-writer counter.

Resolution when `--config` is omitted:

* `config/numbering.json` if it exists
* otherwise the example, for `preview`
* `next` and `rename` copy the example to `config/numbering.json` on first use

Pass `--config` to keep a counter somewhere else. Do not allocate against the
example file if you want it to stay at `LE-01001-A`.

### Ops API later (FCB-P2-03)

Callers use `bruceworx.sources.NumberSource`:

* `allocate(program, revision=None) -> str`
* `preview(program, revision=None) -> str`
* `programs() -> list[str]`

`open_number_source(path)` reads JSON. `open_number_source({"source": "ops",
"base_url": "https://ops.example/api", "token_env": "BW_OPS_TOKEN"})` returns
`OpsApiNumberSource`. Building that object is allowed. `allocate` and
`preview` raise `NotImplementedError` and do not make a network call.

The intended request, for the reader that replaces those two methods:

```http
POST {base_url}/part-numbers
{"program": "LE", "revision": "A"}

{"part_number": "LE-01001-A"}
```

Bearer token from the `token_env` variable (default `BW_OPS_TOKEN`).

## Macro

`macros/PartNumber.FCMacro` numbers the active document. It uses the GUI
selection when there is one. Program and config can be set with
`BW_PROGRAM`, `BW_REVISION` and `BW_NUMBERING_CONFIG`.

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
volume, writes the tree, renames to `LE-01001-A`, then runs `hooks.py` both
via `BW_HOOKS_ARGS` and via `FreeCADCmd --`.

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
