# Building FreeCAD BruceWorx

BruceWorx is a lightly modified FreeCAD distribution. The `main` branch is
FreeCAD **1.1.4** plus our `[BW]` commits, and it builds the same way upstream
FreeCAD does: with [pixi](https://pixi.sh) (conda-forge dependencies) and CMake
presets. Every command below is a task defined in the repository's own
`pixi.toml`, which uses the presets in `CMakePresets.json`. We have not added
any tasks of our own.

Supported targets:

| Platform | pixi platform | CMake preset (release / debug) |
|---|---|---|
| macOS, Apple Silicon (arm64), Qt6 | `osx-arm64` | `conda-macos-release` / `conda-macos-debug` |
| Linux x86_64, Qt6 | `linux-64` | `conda-linux-release` / `conda-linux-debug` |

Qt6 is the only Qt version used. `pixi.toml` pins `qt6-main >=6.8,<6.9` and
`pyside6`, and adds `noqt5`.

## Rule: BruceWorx features ship on by default

Everything built for BruceWorx is installed by the normal build and enabled
by default, with an off switch on **Preferences → BruceWorx** (also reachable
from **BruceWorx → BruceWorx Preferences…**). Nothing needs a manual copy,
symlink, or "apply" step after `pixi run build-release`.

| Feature | Where it lives | Default | Off switch |
|---|---|---|---|
| Unified title bar + toolbar (macOS) | `src/Gui/MainWindow.cpp` | on | Preferences → BruceWorx → macOS window |
| Overlay (floating) model tree | `src/Mod/BruceWorx` | on | Preferences → BruceWorx → Floating model tree |
| BruceWorx preference pack | `src/Gui/PreferencePacks`, `src/Mod/BruceWorx/bruceworx_defaults.py` | applied once on first start | Preferences → BruceWorx → BruceWorx preference pack (restores your previous values) |
| History Timeline dock | `package/bruceworx/mods/HistoryTimeline` → `Mod/HistoryTimeline` | on | BruceWorx → History Timeline, Preferences → BruceWorx, or close the dock |
| Hooks / part numbers | `addons/BruceWorx` → `Mod/BruceWorxHooks` | on | Preferences → BruceWorx → Hooks add-on (next start) |

First-start preference pack: when the pack has never been applied and the
switch is on, BruceWorx applies the light pack once, before the startup
workbench loads. Every key the pack writes is saved to
`<UserAppData>/BruceWorx/stock-snapshot.json` first, so an existing profile
loses nothing: unchecking the switch (or applying the "BruceWorx Off" pack)
writes those values back. It is applied at most once per profile
(`BruceWorx/FirstRunPackDone`); after you turn it off or pick another theme it
is not re-applied. The Qt style and toolbar icon size are read before
add-ons load, so those two take effect from the second start.

Build-time switches, for packagers only: `-DBUILD_BW_HISTORY_TIMELINE=OFF`,
`-DBUILD_BW_HOOKS=OFF`. New BruceWorx features follow the same pattern: on by
default, a `Gui::PrefCheckBox` on `src/Mod/BruceWorx/preferences-bruceworx.ui`
to turn them off, and an install rule so `build/<preset>/bin/FreeCAD` loads
them without an install step.

## 1. Prerequisites

### Both platforms
* git
* pixi >= 0.48 (`requires-pixi` in `pixi.toml`). CI uses v0.59.0.
  ```sh
  curl -fsSL https://pixi.sh/install.sh | bash
  ```
* About 15 GB of free disk for the environment and the build tree.

pixi installs the compilers, CMake, Ninja, ccache, Qt6, OCCT 7.8, Coin3D,
VTK, Python 3.11 and the other dependencies into `.pixi/`. You don't need
Homebrew or distro packages for the build.

### macOS arm64
* Xcode Command Line Tools: `xcode-select --install` (for the SDK and the linker).
* Use a native arm64 shell, not Rosetta. `uname -m` should print `arm64`.

### Linux x86_64
* Any recent glibc distribution. pixi supplies a CentOS-7 sysroot, clang, mold
  and the X11/Mesa libraries. To run the GUI tests headless, use the bundled
  `xvfb-run` (`pixi run xvfb-run ...`).

## 2. Get the source

```sh
git clone https://github.com/brucecodes2023/FreeCAD_BruceWorx.git
cd FreeCAD_BruceWorx
```

Submodules are initialised automatically by the `initialize` task, which every
`configure-*` task depends on.

## 3. Configure, build, run

Release build (recommended):

```sh
pixi run configure-release   # git submodule update + cmake --preset conda-<os>-release
pixi run build-release       # cmake --build build/release
pixi run freecad-release     # launches build/release/bin/FreeCAD (macOS: see note)
```

Debug build. These are also the defaults for `configure`, `build`, `test`,
`install` and `freecad`:

```sh
pixi run configure      # = configure-debug
pixi run build          # = build-debug
pixi run freecad        # = freecad-debug
```

On first run, pixi resolves the environment from `pixi.lock`, which takes a
while. After that, ccache (from the environment) speeds up rebuilds.

macOS note: depending on the CMake options, the build tree may produce a
`FreeCAD.app` bundle rather than `bin/FreeCAD`. If `freecad-release` can't
find the binary, run `pixi run install-release` and launch the installed
binary from the pixi environment, as upstream CI does.

## 4. Tests

```sh
pixi run test-release                          # ctest --test-dir build/release
pixi run build/release/bin/FreeCADCmd -t 0     # Python unit tests (CLI)
pixi run xvfb-run build/release/bin/FreeCAD -t 0   # GUI tests, Linux headless
```

The C++ GoogleTest binaries are in `build/<config>/tests/*_tests_run`.

STEP import smoke (after `pixi run install-release`):

```sh
pixi run FreeCADCmd package/bruceworx/step-import-check.py --pass data/tests/Step/as1-ac-214.stp
```

The script prints object, shape, and solid counts and exits non-zero when nothing is imported. CI uses the upstream file `data/tests/Step/as1-ac-214.stp`.

## 5. Install

```sh
pixi run install-release     # cmake --install build/release (into the pixi env prefix)
```

## 6. CI

`.github/workflows/bruceworx-ci.yml` is the BruceWorx build. The repository
variable `BW_MAC_RUNNER` stays `false`: the self-hosted Apple Silicon jobs
stay skipped. Leave that variable unset while the Mac is parked.

Jobs that run on pull requests and on pushes to `main`:

* **Linux x86_64** (GitHub-hosted `ubuntu-latest`): `pixi install` from
  `pixi.lock`, `configure-release`, `build-release` with ccache (cache key
  `bw-pixi-linux-x86_64`), the upstream C++ and Python CLI tests, the `bw.1`
  version check, a STEP import of `data/tests/Step/as1-ac-214.stp` through
  `package/bruceworx/step-import-check.py`, and
  `addons/BruceWorx/tests/run_freecad_smoke.sh` (STEP export, re-import,
  document tree, part-number rename, `hooks.py`).
* **BruceWorx hooks unit tests** (GitHub-hosted `ubuntu-latest`): `python3 -m
  unittest discover -s addons/BruceWorx/tests`. No compile. CLI usage is in
  `addons/BruceWorx/README.md`.
* **pixi lock** on `ubuntu-latest` and GitHub-hosted `macos-15` (Apple
  Silicon): `pixi lock --check` on both, and `pixi install --locked` on
  macOS so the `osx-arm64` environment from `pixi.lock` is installed without
  a full compile. `macos-15` on GitHub is arm64.

Manual job, `workflow_dispatch` only, GitHub-hosted `macos-15`. It does not
read `BW_MAC_RUNNER` and does not use the self-hosted runner:

* **macOS arm64 hosted build**: configure, build (ccache key
  `bw-pixi-macos-15-arm64`), install, and the same STEP check on the installed
  `FreeCADCmd`. [Run 38638134632](https://github.com/brucecodes2023/FreeCAD_BruceWorx/actions/runs/38638134632)
  finished this path and the Linux job together. The packaged-app STEP check
  reported 108 objects, 88 shapes, and 18 solids.
* **Unsigned .dmg** runs only when the dispatch input `upload_dmg` is checked.
  That path runs `package/bruceworx/make-dmg.sh`, repeats the STEP check
  against the packaged `FreeCADCmd`, and uploads
  `FreeCAD_BruceWorx-1.1.4-bw.1-macos-arm64-unsigned`. The image is about
  1.7 GB; leave the input off unless you need the file.

The self-hosted jobs `macos-arm64` and `macos-arm64-dmg` are still in the
workflow, behind `vars.BW_MAC_RUNNER == 'true'`, on the labels
`self-hosted, macOS, ARM64`. They upload `FreeCAD-BruceWorx-macOS-arm64-dmg`
when that variable is true. It stays false. They do not run the hooks smoke
script.

## 7. macOS arm64 .dmg (internal use only)

```sh
pixi run install-release
pixi run bash package/bruceworx/make-dmg.sh          # -> dist/FreeCAD-BruceWorx-1.1.4-bw.1-macOS-arm64.dmg
BW_ADHOC_SIGN=1 pixi run bash package/bruceworx/make-dmg.sh   # optional ad-hoc codesign
```

The script copies the pixi install prefix (`$CONDA_PREFIX`) into
`FreeCAD BruceWorx.app/Contents/Resources`, adds a launcher and `Info.plist`,
and packs it with `hdiutil`. It is **unsigned** (at most ad-hoc signed) and
**not notarized**: for internal machines only. On first launch, right-click the
app and choose Open, or run `xattr -dr com.apple.quarantine "/Applications/FreeCAD BruceWorx.app"`.

## References
* Upstream developer guide: https://freecad.github.io/DevelopersHandbook/gettingstarted/
* Upstream wiki: https://wiki.freecad.org/Compiling
