# SPDX-License-Identifier: LGPL-2.1-or-later
"""App init for the History Timeline addon.

FreeCAD execs this file, so ``__file__`` is not defined here. The module
directory is already on ``sys.path``. BruceWorx installs this add-on with the
normal build (``Mod/HistoryTimeline``) and ``Mod/HistoryTimeline/Enabled``
defaults to true, so the dock shows on start. Turn it off on
Preferences → BruceWorx or with BruceWorx → History Timeline.
"""
