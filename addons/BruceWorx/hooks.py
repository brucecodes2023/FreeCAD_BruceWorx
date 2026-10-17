# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx hooks entry point.

FreeCADCmd imports a ``.py`` file as a module (``__name__`` is ``hooks``, not
``__main__``) and only falls back to running it as a script if that import
fails. Calling :func:`bruceworx.cli.main` on import is what makes

    FreeCADCmd -- addons/BruceWorx/hooks.py list-tree --input part.FCStd

actually run. Plain ``python3 hooks.py ...`` hits the ``__main__`` branch.

Do not import this module from library code or tests.
"""

from __future__ import annotations

import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bruceworx.cli import main  # noqa: E402


def _invoked_as_entry() -> bool:
    if __name__ == "__main__":
        return True
    # FreeCADCmd loadModule uses the file stem as the module name.
    return __name__ == "hooks"


if _invoked_as_entry():
    try:
        _code = main()
    except Exception:  # noqa: BLE001 — process boundary
        traceback.print_exc()
        _code = 1
    sys.exit(_code)
