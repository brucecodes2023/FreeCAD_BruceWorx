# SPDX-License-Identifier: LGPL-2.1-or-later

SET(BruceWorx_SRCS
    InitGui.py
    bruceworx_pack.py
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
