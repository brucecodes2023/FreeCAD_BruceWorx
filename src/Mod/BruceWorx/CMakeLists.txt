# SPDX-License-Identifier: LGPL-2.1-or-later
# [BW] Python-only: preference page, overlay model tree, preference-pack
# helper (applied on first start), shared BruceWorx menu and ground grid.
# No workbench, no C++.

SET(BruceWorx_SRCS
    Init.py
    InitGui.py
    BruceWorx.py
    TestBruceWorx.py
    preferences-bruceworx.ui
    BruceWorxModelTree.qss
    bruceworx_pack.py
    bruceworx_defaults.py
    bruceworx_menu.py
    ground_grid.py
)

ADD_CUSTOM_TARGET(BruceWorx ALL
    SOURCES ${BruceWorx_SRCS}
)

fc_copy_sources(BruceWorx "${CMAKE_BINARY_DIR}/Mod/BruceWorx" ${BruceWorx_SRCS})

INSTALL(
    FILES ${BruceWorx_SRCS}
    DESTINATION Mod/BruceWorx
)
