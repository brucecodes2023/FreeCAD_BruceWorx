# SPDX-License-Identifier: LGPL-2.1-or-later
"""``python -m bruceworx`` entry. FreeCADCmd should run hooks.py instead."""

import sys

from bruceworx.cli import main

if __name__ == "__main__":
    sys.exit(main())
