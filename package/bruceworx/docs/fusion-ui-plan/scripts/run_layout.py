"""Run render_layout.py inside FreeCADCmd, whose Qt finds its offscreen plugin.

    QT_QPA_PLATFORM=offscreen build/release/bin/FreeCADCmd \
        package/bruceworx/docs/fusion-ui-plan/scripts/run_layout.py
"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.argv = ["render_layout.py", ROOT]
runpy.run_path(os.path.join(HERE, "render_layout.py"), run_name="__main__")
