# SPDX-License-Identifier: LGPL-2.1-or-later
# [BW] Python-only preference page. No workbench.

SET(BruceWorx_SRCS
    Init.py
    InitGui.py
    BruceWorx.py
    TestBruceWorx.py
    preferences-bruceworx.ui
    BruceWorxModelTree.qss
)

ADD_CUSTOM_TARGET(BruceWorx ALL
    SOURCES ${BruceWorx_SRCS}
)

fc_copy_sources(BruceWorx "${CMAKE_BINARY_DIR}/Mod/BruceWorx" ${BruceWorx_SRCS})

INSTALL(
    FILES ${BruceWorx_SRCS}
    DESTINATION Mod/BruceWorx
)
