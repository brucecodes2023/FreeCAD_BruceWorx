# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx defaults: everything ships on, each with an off switch.

This module owns the "preference pack on by default" rule.

``BaseApp/Preferences/BruceWorx/PreferencePack`` (bool, default true) is the
switch shown on the BruceWorx preference page.

* First start with the switch on and the pack not applied: the BruceWorx
  (light) pack is applied once, through the same snapshot path the pack's
  ``pre.FCMacro`` uses (``bruceworx_pack.enable``). Every key the pack
  writes is saved to ``<UserAppData>/BruceWorx/stock-snapshot.json`` first,
  so nothing is lost. ``FirstRunPackDone`` records that this happened, so a
  user who later picks another theme is not overridden on the next start.
* Unchecking the switch restores that snapshot (same as the "BruceWorx Off"
  pack). Checking it again re-applies the light pack.
* Choosing a pack in Preferences → General → Theme keeps working. The
  BruceWorx packs flip the switch to match (``bruceworx_pack.freecad_pre`` /
  ``freecad_off``).

The functions take a ``store`` (``bruceworx_pack.MemoryStore`` in tests,
``bruceworx_pack.FreeCADStore`` in FreeCAD) so they run without a GUI.
"""

from __future__ import annotations

import bruceworx_pack

GROUP = bruceworx_pack.APPLIED_GROUP  # BaseApp/Preferences/BruceWorx
SWITCH = "PreferencePack"
FIRST_RUN_DONE = "FirstRunPackDone"


def switch_on(store) -> bool:
    return bool(store.get(GROUP, SWITCH, "bool", True))


def pack_applied(store) -> bool:
    return bool(store.get(GROUP, bruceworx_pack.APPLIED_NAME, "bool", False))


def apply_first_run(store, snapshot_path: str) -> str:
    """Apply the pack once on first start. Returns what happened.

    ``"applied"``   the pack was applied now;
    ``"already"``   it was already applied (by hand or an earlier start);
    ``"done"``      a previous start already handled first run;
    ``"off"``       the switch is off.
    """
    if not switch_on(store):
        return "off"
    if pack_applied(store):
        store.set(GROUP, FIRST_RUN_DONE, "bool", True)
        return "already"
    if store.get(GROUP, FIRST_RUN_DONE, "bool", False):
        return "done"
    bruceworx_pack.enable(store, snapshot_path, "light")
    store.set(GROUP, FIRST_RUN_DONE, "bool", True)
    return "applied"


def on_switch_changed(store, snapshot_path: str, value: bool) -> str:
    """React to the preference-page switch. Idempotent."""
    store.set(GROUP, FIRST_RUN_DONE, "bool", True)
    if value:
        if pack_applied(store):
            return "noop"
        bruceworx_pack.enable(store, snapshot_path, "light")
        return "applied"
    if not pack_applied(store):
        return "noop"
    return bruceworx_pack.disable(store, snapshot_path)


# --- FreeCAD glue -------------------------------------------------------------

_live = {"last": None, "observer": None, "group": None, "busy": False}


def _store():
    return bruceworx_pack.FreeCADStore()


def _log(message: str) -> None:
    try:
        import FreeCAD

        FreeCAD.Console.PrintLog(message + "\n")
    except Exception:
        pass


def _warn(message: str) -> None:
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(message + "\n")
    except Exception:
        print(message)


def _activate_ground_grid(applied: bool) -> None:
    try:
        import ground_grid

        if applied:
            ground_grid.activate()
        else:
            ground_grid.deactivate()
    except Exception as exc:
        _warn(f"BruceWorx ground grid: {exc}")


class _SwitchObserver:
    def onChange(self, _group, name):
        if name != SWITCH or _live["busy"]:
            return
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, _flush)
        except Exception:
            _flush()


def _flush():
    store = _store()
    value = switch_on(store)
    if value == _live["last"]:
        return
    _live["last"] = value
    _live["busy"] = True
    try:
        result = on_switch_changed(store, bruceworx_pack.default_snapshot_path(), value)
    except Exception as exc:
        _warn(f"BruceWorx preference pack switch failed: {exc}")
        return
    finally:
        _live["busy"] = False
    _log(f"BruceWorx preference pack switch: {result}")
    if result != "noop":
        _activate_ground_grid(value)


def startup() -> str:
    """Called from InitGui before the startup workbench is activated."""
    store = _store()
    try:
        result = apply_first_run(store, bruceworx_pack.default_snapshot_path())
    except Exception as exc:
        _warn(f"BruceWorx first-run preference pack failed: {exc}")
        result = "error"
    if result == "applied":
        try:
            import FreeCAD

            FreeCAD.Console.PrintMessage(
                "BruceWorx: applied the BruceWorx preference pack (first start). "
                "Your previous values are saved; uncheck Preferences → BruceWorx → "
                "Preference pack to restore them.\n"
            )
        except Exception:
            pass
    _live["last"] = switch_on(store)
    if _live["observer"] is None:
        try:
            import FreeCAD

            observer = _SwitchObserver()
            # Keep the group handle: the Python wrapper detaches its
            # observers when it is garbage collected.
            group = FreeCAD.ParamGet("User parameter:" + GROUP)
            group.Attach(observer)
            _live["observer"] = observer
            _live["group"] = group
        except Exception as exc:
            _warn(f"BruceWorx preference pack switch not attached: {exc}")
    return result


def sync_switch(value: bool) -> None:
    """Keep the switch in step when a pack is applied from the Theme combo."""
    try:
        store = _store()
        if switch_on(store) != bool(value):
            _live["last"] = bool(value)
            _live["busy"] = True
            try:
                store.set(GROUP, SWITCH, "bool", bool(value))
                store.set(GROUP, FIRST_RUN_DONE, "bool", True)
            finally:
                _live["busy"] = False
    except Exception as exc:
        _warn(f"BruceWorx preference pack switch: {exc}")
