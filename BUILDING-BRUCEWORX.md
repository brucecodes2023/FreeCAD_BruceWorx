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

## 5. Install

```sh
pixi run install-release     # cmake --install build/release (into the pixi env prefix)
```

## 6. CI

`.github/workflows/bruceworx-ci.yml` runs these steps:

* **Linux x86_64** (GitHub-hosted `ubuntu-latest`): configure-release,
  build-release with a ccache cache, then the upstream C++ and Python test
  actions.
* **macOS arm64** (self-hosted runner labelled `self-hosted, macOS, ARM64`):
  the same steps. This job runs only when the repository variable
  `BW_MAC_RUNNER` is set to `true`, and is skipped otherwise.

## References
* Upstream developer guide: https://freecad.github.io/DevelopersHandbook/gettingstarted/
* Upstream wiki: https://wiki.freecad.org/Compiling
