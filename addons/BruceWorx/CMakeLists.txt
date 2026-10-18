# SPDX-License-Identifier: LGPL-2.1-or-later
# [BW] BruceWorx hooks add-on (Python only), installed with the normal build
# as Mod/BruceWorxHooks: copied into <build>/Mod/BruceWorxHooks (what
# build/<preset>/bin/FreeCAD loads) and installed to Mod/BruceWorxHooks.
#
# The folder name differs from src/Mod/BruceWorx on purpose: FreeCAD keys
# modules by lower-cased folder name, so a second "BruceWorx" would replace
# the preference module.
#
# package.xml is not installed: with a package.xml that lists no workbench,
# FreeCAD skips Init.py / InitGui.py. hooks.py goes to cli/ so the add-on's
# top folder (on sys.path) has no module named "hooks".
#
# Build switch: -DBUILD_BW_HOOKS=OFF. Runtime switch: Preferences -> BruceWorx.

SET(BruceWorxHooks_SRCS
    Init.py
    InitGui.py
    LICENSE
    README.md
    bruceworx/__init__.py
    bruceworx/__main__.py
    bruceworx/cli.py
    bruceworx/config_path.py
    bruceworx/freecad_io.py
    bruceworx/gui.py
    bruceworx/macro.py
    bruceworx/numbering.py
    bruceworx/sources.py
    bruceworx/step_export.py
    bruceworx/tree.py
    config/document_types.json
    config/numbering.example.json
    macros/PartNumber.FCMacro
)

ADD_CUSTOM_TARGET(BW_BruceWorxHooks ALL
    SOURCES ${BruceWorxHooks_SRCS} hooks.py
)

set(BW_HOOKS_BUILD_DIR "${CMAKE_BINARY_DIR}/Mod/BruceWorxHooks")
fc_copy_sources(BW_BruceWorxHooks "${BW_HOOKS_BUILD_DIR}" ${BruceWorxHooks_SRCS})

# hooks.py -> cli/hooks.py
add_custom_command(
    OUTPUT "${BW_HOOKS_BUILD_DIR}/cli/hooks.py"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${BW_HOOKS_BUILD_DIR}/cli"
    COMMAND "${CMAKE_COMMAND}" -E copy "${CMAKE_CURRENT_SOURCE_DIR}/hooks.py" "${BW_HOOKS_BUILD_DIR}/cli/hooks.py"
    MAIN_DEPENDENCY "${CMAKE_CURRENT_SOURCE_DIR}/hooks.py"
    COMMENT "Copying hooks.py to ${BW_HOOKS_BUILD_DIR}/cli/hooks.py"
)
add_custom_target(BW_BruceWorxHooks_cli ALL DEPENDS "${BW_HOOKS_BUILD_DIR}/cli/hooks.py")

INSTALL(FILES Init.py InitGui.py LICENSE README.md DESTINATION Mod/BruceWorxHooks)
INSTALL(
    FILES
        bruceworx/__init__.py
        bruceworx/__main__.py
        bruceworx/cli.py
        bruceworx/config_path.py
        bruceworx/freecad_io.py
        bruceworx/gui.py
        bruceworx/macro.py
        bruceworx/numbering.py
        bruceworx/sources.py
        bruceworx/step_export.py
        bruceworx/tree.py
    DESTINATION Mod/BruceWorxHooks/bruceworx
)
INSTALL(
    FILES config/document_types.json config/numbering.example.json
    DESTINATION Mod/BruceWorxHooks/config
)
INSTALL(FILES macros/PartNumber.FCMacro DESTINATION Mod/BruceWorxHooks/macros)
INSTALL(FILES hooks.py DESTINATION Mod/BruceWorxHooks/cli)
