"""Roadmap epics: the single source for the CSV and the LaTeX summary table.

    python3 package/bruceworx/docs/fusion-ui-plan/scripts/epics.py

Writes ../roadmap-epics.csv (for import into BruceWorx Ops) and
../chapters/gen-epics.tex. Epics only; tasks are broken down when an epic
starts. "origin" lists the Ops idea IDs (sample data) each epic absorbs.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TRACKS = {
    "FND": "Foundation & upstream",
    "MOD": "Part modeling",
    "ASM": "Assembly",
    "DRW": "Drawings (ASME)",
    "PDM": "Part & drawing management",
    "SIM": "Simulation",
    "MFG": "Manufacturing outputs",
    "ROB": "Robotics & drone kits",
    "ECD": "ECAD bridge (KiCad)",
    "AUT": "AI & automation",
    "UIX": "UI & styling",
    "KRN": "Kernel study",
}

MILESTONES = {
    "M0": "Foundation green",
    "M1": "Model it: LE-02001 modelled in FreeCAD",
    "M2": "Document & release it: LE-02001 rev A from FreeCAD",
    "M3": "Make it: print, CNC and sheet-metal outputs",
    "M4": "Validate it: simulation",
    "M5": "Advanced modeling & assembly",
    "M6": "Switch system of record (FC-T01)",
    "UI": "UI & styling pass (after M2)",
    "BG": "Background study",
}


def E(id, title, milestone, status, depends, origin, summary, accept):
    return dict(id=f"BW-{id}", track=TRACKS[id[:3]], title=title, milestone=milestone,
                status=status, depends=" ".join(f"BW-{d}" for d in depends), origin=origin,
                summary=summary, acceptance=accept)


EPICS = [
    # Foundation ----------------------------------------------------------
    E("FND-01", "Build & CI on Linux and macOS arm64", "M0", "In progress", [],
      "FCB-P0-CI-01..06, P0-01, P0-06..08, P0-10",
      "Pixi envs and lockfiles, ccache, self-hosted Mac runner, docs. Linux STEP check and hosted macOS lock are merged (#4).",
      "Fresh clone builds on both platforms using documented commands only; CI green on both."),
    E("FND-02", "Packaging, branding & releases", "M0", "In progress", ["FND-01"],
      "FCB-P0-02, P0-03, P0-09, P0-11, P0-17, P0-18",
      "Branding 1.1.4-bw.1 and the unsigned .dmg (#3) exist; release tagging with dmg + source.",
      "Tagged release installs on a clean Mac and opens a Fusion STEP file within envelope."),
    E("FND-03", "Track upstream FreeCAD main", "M0", "To do", ["FND-01"],
      "FCB-P1-16..21, P0-12 (replaced: rebase-at-26.3 policy), P2-01/02 (add-on vs fork)",
      "Continuously rebase [BW] commits onto upstream main; nightly CI merge-test; conflict budget; rewrite UPSTREAM-SYNC.md.",
      "Nightly job rebases [BW] onto main and runs tests; a conflict opens an issue within 24 h."),
    E("FND-04", "Licences & notices", "M0", "To do", [],
      "FCB-P0-13",
      "NOTICE of changes; third-party notices for bundled SheetMetal, OCP, CadQuery, build123d and any OpenSCAD binary.",
      "Every bundled component listed with its licence; source tarball attached to each release."),
    E("FND-05", "Acceptance corpus & test harness", "M0", "To do", [],
      "FCB-P1-09, P3-08",
      "LE part corpus (STEP + native), headless fixtures, screenshot script; used by every epic's acceptance.",
      "Corpus in repo or LFS; one command runs all headless acceptance checks."),
    E("FND-06", "Fixes found in review", "M0", "In progress", [],
      "(new)",
      "Spacings2 bug fixed + 3 tests; trim failure traced to int(None) (pending fix verified); tree auto-hid by default (now off).",
      "4x3 pattern gives 12 instances; only intended workbenches shown; tree visible on first run."),
    E("FND-07", "On by default, each with an off switch", "M0", "Done", [],
      "FCB-P1-01, P1-10",
      "Feature flags and preference page (#9). Rule applies to every later epic.",
      "Merged (#9)."),
    # Modeling ------------------------------------------------------------
    E("MOD-01", "Rectangular & circular patterns", "M1", "In progress", ["FND-06"],
      "(new, UI plan)",
      "Bodies/components built (link arrays, symmetric, suppress, linked/independent, dialog); features use PartDesign until the upstream rebase brings suppression.",
      "Fig. examples reproduced in GUI; undo/redo; save/reload; Assembly sees component instances."),
    E("MOD-02", "Parameters & top-down design", "M1", "To do", [],
      "(new)",
      "Change Parameters dialog over VarSet/Spreadsheet; skeleton sketches; derive geometry across files.",
      "A skeleton change propagates to three linked part files in one recompute."),
    E("MOD-03", "Configurations", "M1", "To do", ["MOD-02"],
      "(new)",
      "Table-driven variants of one part or assembly; suppression per configuration; P/N per configuration.",
      "Short/Standard/Long bracket from one file; BOM lists the right configuration P/Ns."),
    E("MOD-04", "Direct edit on imported geometry", "M1", "To do", [],
      "FCB-P2-15 (STEP import checks)",
      "Press-pull, move, delete and replace face on dumb solids; hole/fillet recognition. Builds on Part_Defeaturing.",
      "Fusion STEP of LE-01001 edited (hole moved, face offset) and still valid."),
    E("MOD-05", "Threads, holes & hardware library", "M1", "To do", [],
      "FCB-P2-09/10 (COTS), (new)",
      "Cosmetic thread object; Hole presets incl. heat-set inserts; fastener library (evaluate Fasteners add-on).",
      "M3 tapped hole and M3 heat-set hole callouts appear on the drawing from model data."),
    E("MOD-06", "Sheet metal", "M3", "To do", [],
      "(new, UI plan)",
      "Bundle the SheetMetal add-on; per-material/thickness rules and K-factor table.",
      "Bracket flat length matches the bend-allowance formula to 0.01 mm."),
    E("MOD-07", "Frames & weldments", "M3", "To do", [],
      "(new)",
      "Structural members along sketch edges, profile library (2020 extrusion, tube), end treatments, cut list.",
      "Frame example produces a cut list with lengths and mitre angles."),
    E("MOD-08", "Surfacing parity", "M5", "To do", [],
      "(new)",
      "Trim/untrim by curve, patch, extend, stitch, replace face, thicken; continuity (zebra, curvature) analysis.",
      "Surface benchmark set rebuilt to G1/G2 and thickened into a valid solid."),
    E("MOD-09", "Freeform (subdivision / T-spline-like)", "M5", "To do", ["MOD-08"],
      "(new)",
      "Form body: subdivision cage editing, conversion to B-spline B-rep.",
      "Drone canopy modelled as a cage and exported as a valid STEP solid."),
    E("MOD-10", "Mesh to solid", "M5", "To do", [],
      "(new)",
      "Mesh repair, segmentation, primitive fitting, rebuild as features; faceted fallback.",
      "Scanned bracket STL becomes a solid with planar/cylindrical faces within 0.1 mm."),
    E("MOD-11", "Inspect tools", "M1", "To do", [],
      "FCB-P2R-07 (mass), (new)",
      "Measure, mass/CG/inertia, section analysis, curvature/zebra, draft and overhang, wall thickness.",
      "Mass/CG matches a hand calculation fixture; overhang map on a printed part."),
    E("MOD-12", "Sketcher parity audit", "M1", "To do", [],
      "(new)",
      "Audit Sketcher against Fusion/SolidWorks sketch tools; fix the top gaps.",
      "Gap list approved; top five gaps closed."),
    # Assembly ------------------------------------------------------------
    E("ASM-01", "File model: one part per file", "M1", "To do", [],
      "(new)",
      "Assemblies link external part files; relative paths; 'make external' from a multi-body file.",
      "LE-02001 opens from a moved folder with no broken links."),
    E("ASM-02", "Assembly gap audit", "M1", "Done", [],
      "FCB-P2A-01/02",
      "Approved 2026-10-19 (1.1.4 + 97 upstream commits): 6 gaps close on rebase; BOM needs part properties only. GUI checks (limits while dragging, joints on pattern instances, fixed-joint placement) are in the test checklist.",
      "Gap list approved by mechanical reviewer."),
    E("ASM-03", "Joint UX & limits", "M1", "In progress", ["ASM-02"],
      "FCB-P2A-03/04",
      "Pick-two-features quick joint with type inference; limit sliders honoured while dragging. Built 2026-10-19: limits measured from datums (LimitAngleZero/LimitLengthZero), drag backstop at limits, Keep parts where they are (as-built), Python drag API, 7 tests.",
      "2-DOF arm assembled with quick joints; limits stop the drag."),
    E("ASM-04", "Exploded views & BOM", "M1", "In progress", ["ASM-01"],
      "FCB-P2A-05/06",
      "Part properties now come from a layered schema (config/part_properties.json, bruceworx/partprops.py): new properties need no code; Mass and Material are computed; the BOM keeps text such as rev 01 as typed. Still to do: exploded presets, indented and flattened BOM, CSV.",
      "LE-02001 BOM matches hand count; flattened BOM sums quantities."),
    E("ASM-05", "Sub-assemblies", "M1", "To do", ["ASM-01"],
      "FCB-P2A-07",
      "Rigid vs flexible sub-assemblies; fix-up macro.",
      "Flexible sub-assembly moves in the parent; rigid one does not."),
    E("ASM-06", "Interference & clearance", "M1", "To do", [],
      "FCB-P2A-08",
      "Pairwise clash/contact list with bbox prefilter; clearance check; highlight.",
      "Too-long bolt example reports 4.0 mm / 78.5 mm^3 clash."),
    E("ASM-07", "In-context editing", "M5", "To do", ["ASM-01", "MOD-02"],
      "(new)",
      "Edit a part inside the assembly referencing other parts; update and break/lock references.",
      "Bracket holes follow a moved motor mount across files."),
    E("ASM-08", "Large-assembly mode", "M5", "To do", ["ASM-01"],
      "(new)",
      "Lightweight/partial loading, selective open, display caches.",
      "Full robot (>500 parts) opens in under N s (target set in spike)."),
    E("ASM-09", "Smart fastener mating", "M5", "To do", ["MOD-05", "ASM-03"],
      "FCB-P2R-04 (mounting LCS)",
      "Recognise holes, insert matching fastener of correct length, auto-joint.",
      "Bolting a motor mount places and joints all screws in one command."),
    E("ASM-10", "Dynamic motion study", "M5", "To do", ["ASM-03"],
      "FCB-P2A-10",
      "Gravity, forces, motor torque and contact over time; plots and video.",
      "Arm under gravity matches analytic pendulum period within 2 %."),
    # Drawings ------------------------------------------------------------
    E("DRW-01", "ASME templates & title block", "M2", "To do", [],
      "FCB-P2-06/07/08",
      "ANSI A-D sheets, third-angle symbol, tolerance block; fields filled from PDM metadata.",
      "LE-01001 sample drawing fills every field automatically."),
    E("DRW-02", "Associative BOM table & balloons", "M2", "To do", ["ASM-04"],
      "FCB-P2A-06",
      "Native parts list (ASME Y14.34) driven by the assembly BOM; balloons linked to item numbers.",
      "Adding a part updates the table and keeps balloon numbers."),
    E("DRW-03", "GD&T & datums (ASME Y14.5)", "M2", "To do", [],
      "(new)",
      "Semantic feature control frames, datum symbols, basic dimensions; validation.",
      "FCF referencing a missing datum is flagged; frames survive model edits."),
    E("DRW-04", "Hole & thread callouts from the model", "M2", "To do", ["MOD-05"],
      "(new)",
      "Callout text generated from Hole/thread data (counterbore, depth, thread class).",
      "Callouts update when the hole changes."),
    E("DRW-05", "Revision table & release stamp", "M2", "To do", ["PDM-02"],
      "(new)",
      "Revision block from change history; PRELIMINARY stamp for numeric revs; P/N-REV printed.",
      "Releasing rev A clears the stamp and adds the revision row."),
    E("DRW-06", "Auto-generate drawing", "M2", "To do", ["DRW-01", "DRW-04"],
      "(new)",
      "One click: view selection, hole callouts and key dimensions, then manual edit.",
      "Corpus parts get a usable first-pass drawing; reviewer rates >= 70 % of dims kept."),
    E("DRW-07", "Sheet-metal flat & cut-list drawings", "M3", "To do", ["MOD-06", "MOD-07"],
      "(new)",
      "Flat-pattern view with bend table; weldment cut-list table.",
      "Bracket drawing shows flat with bend lines and table."),
    E("DRW-08", "Publish PDF/DXF", "M2", "To do", ["DRW-01"],
      "(new)",
      "Vector PDF and DXF export, batch publish for a BOM.",
      "One command publishes every drawing of LE-02001."),
    # PDM -----------------------------------------------------------------
    E("PDM-01", "PDM evaluation & decision", "M2", "Done", [],
      "(new)",
      "Decided 2026-10-19: folder-backed vault in any folder (iCloud Drive first), opened through a .bwvault ref file; one writer at a time. Prototype bruceworx/pdm_folder.py passes the PDM-02 contract plus folder and sync-duplicate tests.",
      "Decision memo approved at a gate."),
    E("PDM-02", "Data model & lifecycle spec", "M2", "In progress", [],
      "(new)",
      "Reference model bruceworx/pdm.py + 18 contract tests + docs/pdm-openapi.yaml (17 endpoints) drafted 2026-10-19; awaiting approval.",
      "Spec approved; state machine covers every transition in the doc."),
    E("PDM-03", "Numbering service", "M2", "In progress", ["PDM-02"],
      "FCB-P2-03/04/05",
      "P/N without revision; Ops API reader; migrate numbering.py ({REV} moves to metadata). Local JSON source merged (#5).",
      "P/N allocated from Ops; existing LE numbers migrate unchanged except REV."),
    E("PDM-04", "FreeCAD vault client", "M2", "To do", ["PDM-01", "PDM-02"],
      "(new)",
      "FreeCAD panel over the folder vault: open a .bwvault, check out to a working folder, check in, get latest, status overlay in the tree. Multi-user locking is a later step.",
      "Check-out/check-in round trip of LE-02001 from an iCloud Drive vault inside FreeCAD; status icons correct."),
    E("PDM-05", "Lifecycle & change control", "M2", "To do", ["PDM-04"],
      "(new)",
      "WIP/In Review/Released/Obsolete; ECR -> ECO; approvals in Ops; released files read-only.",
      "Rev A -> ECR -> ECO -> rev B round trip on LE-01001."),
    E("PDM-06", "BOM sync & where-used", "M2", "To do", ["ASM-04", "PDM-04"],
      "(new)",
      "Push indented BOM per revision to Ops; where-used queries.",
      "Where-used of a bolt lists every assembly revision that uses it."),
    E("PDM-07", "Pilot: LE-02001 & CAD register", "M2", "To do", ["PDM-05", "DRW-05"],
      "FCB-P2-15/16/17/18, P2-21",
      "Pedestal assembly tree, CAD register links, design-freeze checklist; real release.",
      "LE-02001 rev A released from FreeCAD with drawings and package."),
    E("PDM-08", "Migration from Fusion", "M6", "To do", ["PDM-07"],
      "FC-T01, FCB-P2-22",
      "Bulk import Fusion exports with P/N and revision mapping; switch criteria checklist.",
      "All LE parts imported, numbered and released; FC-T01 criteria met."),
    # Simulation ----------------------------------------------------------
    E("SIM-01", "Study setup (Fusion-style)", "M4", "To do", [],
      "(new)",
      "Simulation workspace: static, modal, buckling, thermal, thermal-stress studies on CalculiX/Elmer.",
      "Each study type runs from the wizard on a corpus part."),
    E("SIM-02", "Contacts, bolts & preload", "M4", "To do", ["SIM-01"],
      "(new)",
      "Bonded/separation contacts, bolt connectors with preload.",
      "Bolted bracket benchmark within 5 % of reference."),
    E("SIM-03", "Materials incl. FDM", "M4", "To do", ["SIM-01"],
      "(new)",
      "Isotropic + knockdown by default; orthotropic by print orientation; PETG/ABS/PLA/PA-CF library.",
      "Same part, two orientations: Z-weak case shows lower safety factor."),
    E("SIM-04", "Results & reports", "M4", "To do", ["SIM-01"],
      "(new)",
      "Safety factor, mode shapes, probes, mesh convergence, PDF report.",
      "Report regenerates from the study; convergence plot included."),
    E("SIM-05", "Verification benchmarks", "M4", "To do", ["SIM-01"],
      "(new)",
      "Cantilever, plate with hole, Euler column, beam modes vs closed form.",
      "All benchmarks within stated tolerance in CI."),
    E("SIM-06", "CFD / airflow (later)", "M5", "To do", ["SIM-01"],
      "(new)",
      "Prop wash and enclosure cooling via CfdOF/OpenFOAM.",
      "Deferred; scope set when started."),
    # Manufacturing -------------------------------------------------------
    E("MFG-01", "3D-print prep", "M3", "To do", ["MOD-11"],
      "(new)",
      "Print orientation property, overhang map, 3MF export, slicer handoff, insert hole presets.",
      "Part opens in the slicer with orientation preserved."),
    E("MFG-02", "CNC CAM", "M3", "To do", [],
      "(new)",
      "CAM setups and templates, tool library, post-processor for the shop's machine.",
      "Corpus part posts G-code that simulates clean."),
    E("MFG-03", "Sheet-metal flat DXF", "M3", "To do", ["MOD-06"],
      "(new)",
      "Flat DXF with cut and bend layers, bend notes, K-factor per material.",
      "Laser shop accepts DXF unchanged."),
    E("MFG-04", "Release package", "M2", "To do", ["PDM-05", "DRW-08"],
      "(new)",
      "On release: STEP AP242, PDF, DXF/3MF, checksums; attached to the revision.",
      "Package rebuilds byte-identically from the released files."),
    # Robotics & drones ---------------------------------------------------
    E("ROB-01", "COTS library & insert", "M1", "To do", ["MOD-05"],
      "FCB-P2-09/10, P2R-01..04",
      "Per-part metadata (mass, CG, mount pattern), motors/servos/ESCs/props/bearings, insert with mounting LCS.",
      "NEMA17 and 2207 motor inserted and jointed by mounting LCS."),
    E("ROB-02", "Frame & arm templates", "M3", "To do", ["MOD-03"],
      "FCB-P2R-05/06",
      "Parametric quad X-frame and servo arm as configurations.",
      "Template regenerates for three wheelbases."),
    E("ROB-03", "Mass, CG & inertia report", "M1", "To do", ["MOD-11", "ROB-01"],
      "FCB-P2R-07",
      "Per-part mass (density or COTS override), total, CG, inertia; CSV and 3D marker.",
      "X-frame example: 388.1 g, CG (2.45, 0, -2.73) mm."),
    E("ROB-04", "Drone balance & thrust-to-weight", "M3", "To do", ["ROB-03"],
      "FCB-P2R-08",
      "CG vs motor centroid, thrust-to-weight from COTS data.",
      "Check flags an offset battery."),
    E("ROB-05", "Kinematic chains & joint drive", "M5", "To do", ["ASM-03"],
      "FCB-P2A-09/10",
      "Link chain from revolute joints, joint table, FK readout, servo sweeps, video.",
      "2-DOF arm FK matches hand calculation."),
    # ECAD ----------------------------------------------------------------
    E("ECD-01", "ECAD intake & adopt-vs-build", "M1", "To do", [],
      "FCB-P2E-01..04",
      "Requirements intake; StepUp evaluation (AGPL); decision memo.",
      "Decision recorded."),
    E("ECD-02", "Board STEP into assembly", "M3", "To do", ["ECD-01"],
      "FCB-P2E-05",
      "kicad-cli STEP export, inserted with LCS at board origin.",
      "Board lands at the right origin."),
    E("ECD-03", "Board outline round-trip", "M3", "To do", ["ECD-01"],
      "FCB-P2E-06, P2E-09",
      "Edge.Cuts to Sketcher and back.",
      "Outline delta < 0.01 mm."),
    E("ECD-04", "Placement sync & enclosure fit", "M3", "To do", ["ECD-02", "ASM-06"],
      "FCB-P2E-07/08",
      "Connector/hole positions both ways; board vs housing interference.",
      "Fit check flags a moved connector."),
    # Automation ----------------------------------------------------------
    E("AUT-01", "Headless hooks & CLI", "M0", "Done", [],
      "FCB-P2-11..14",
      "Export STEP, tree JSON, rename/numbering via FreeCADCmd (#5).",
      "Merged (#5)."),
    E("AUT-02", "bruceworx.api", "M1", "To do", ["AUT-01"],
      "FCB-P2AI-03",
      "Python API over the hooks: create/edit part, parameters, tree, export.",
      "API covered by headless tests."),
    E("AUT-03", "MCP server", "M1", "To do", ["AUT-02"],
      "FCB-P2AI-01/02, 04..08",
      "Base selection, BruceWorx tools, headless mode, security (localhost, token, audit), docs, CI.",
      "Agent creates, queries and exports a part headless in CI."),
    E("AUT-04", "Assistant panel", "M5", "To do", ["AUT-03"],
      "FCB-P2AI-09..15",
      "Dock chat with tool-call preview, apply/undo per action.",
      "Try-out on real CAD work signed off."),
    E("AUT-05", "Command line", "M5", "To do", [],
      "(new, UI plan)",
      "AutoCAD-style aliases, inline Python, CadQuery/build123d (pinned), OpenSCAD; CodeFeature with trust prompt.",
      "CPATTERN @Bolt Q 8 reproduces the component pattern; build123d box lands in the timeline."),
    # UI ------------------------------------------------------------------
    E("UIX-01", "Theme, pref pack & viewport styling", "UI", "Done", [],
      "FCB-P1-01..05, P1V-01..07, P1V-10..18",
      "Preference pack, QSS, viewport colours, ground grid (#8); follow-ups: AA check, Victor try-out.",
      "Merged (#8); try-out pending."),
    E("UIX-02", "macOS title bar", "UI", "Done", [],
      "FCB-P1F-01..05, P1F-26",
      "Unified title bar and native buttons (#6).",
      "Merged (#6)."),
    E("UIX-03", "Browser (overlay model tree)", "UI", "In progress", [],
      "FCB-P1F-06..14, P1F-27",
      "Overlay tree via prefs/QSS merged (#6); free-floating panel needs OverlayManager patch.",
      "Tree floats top-left at any inset; off switch restores docks."),
    E("UIX-04", "History timeline", "UI", "In progress", [],
      "FCB-P1F-15..25, P1F-28",
      "Spike and mock merged (#7); full timeline with marker drag, edit, suppress, reorder.",
      "Timeline drives Tip and edits on LE parts."),
    E("UIX-05", "Workspaces & tabs (Fusion naming)", "UI", "To do", [],
      "(new, UI plan)",
      "Design/Simulation/Manufacture/Drawing; Solid/Surface/Mesh/Sheet Metal/Utilities; contextual Sketch.",
      "No workbench switch when changing Design tabs; off switch restores tab bar."),
    E("UIX-06", "Toolbar & panels", "UI", "To do", ["UIX-05"],
      "(new, UI plan)",
      "Captioned groups, floating command dialog, document tabs on top, one-row timeline.",
      "Matches the redesigned mock at two resolutions."),
    E("UIX-07", "Task panel polish", "UI", "To do", [],
      "FCB-P1-06/07/08",
      "Sketcher, PartDesign and TechDraw dialogs.",
      "Before/after gallery approved."),
    E("UIX-08", "Matcap shading", "UI", "To do", [],
      "FCB-P1V-08/09/13/14/15",
      "Matcap draw style behind a preference.",
      "Pref off renders stock; light/dark screenshots."),
    E("UIX-09", "Fresh UI design & re-render figures", "UI", "In progress", ["UIX-05"],
      "(new)",
      "New visual design for the whole app; regenerate all roadmap figures.",
      "Design approved; figures regenerated."),
    # Kernel --------------------------------------------------------------
    E("KRN-01", "OCCT coupling survey", "BG", "To do", [],
      "FCB-P3-01..06",
      "Count OCCT use per module, TNP/element-map dependencies, Python exposure; option A note.",
      "Coupling report published."),
    E("KRN-02", "STEP exchange harness", "BG", "To do", ["FND-05"],
      "FCB-P3-07..11",
      "Separate harness repo, LE corpus, round-trip metrics, CI.",
      "Harness runs on Linux CI."),
    E("KRN-03", "Kernel decision", "BG", "To do", ["KRN-01", "KRN-02"],
      "FCB-P3-12/13/14",
      "A/B/C memo with effort estimates; gate.",
      "Direction picked."),
]


def tex_escape(s):
    return (s.replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%")
            .replace("_", r"\_").replace("#", r"\#").replace("$", r"\$").replace("~", r"\textasciitilde{}")
            .replace("^", r"\textasciicircum{}").replace("<", r"\textless{}").replace(">", r"\textgreater{}"))


def main():
    ids = {e["id"] for e in EPICS}
    for e in EPICS:
        for d in e["depends"].split():
            assert d in ids, f"{e['id']} depends on unknown {d}"
    csv_path = os.path.join(ROOT, "roadmap-epics.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "track", "title", "milestone", "milestone_name", "status", "depends_on",
                    "origin_ideas", "summary", "acceptance"])
        for e in EPICS:
            w.writerow([e["id"], e["track"], e["title"], e["milestone"], MILESTONES[e["milestone"]],
                        e["status"], e["depends"], e["origin"], e["summary"], e["acceptance"]])
    rows = []
    track = None
    for e in EPICS:
        if e["track"] != track:
            track = e["track"]
            rows.append(r"\midrule\multicolumn{5}{@{}l}{\textbf{" + tex_escape(track) + r"}}\\")
        status = {"Done": r"\stDone", "In progress": r"\stProg", "To do": r"\stTodo"}[e["status"]]
        rows.append(" & ".join([r"\code{" + e["id"][3:] + "}", tex_escape(e["title"]), e["milestone"],
                                r"\scriptsize " + tex_escape(e["depends"].replace("BW-", "")) if e["depends"] else "---",
                                status]) + r"\\")
    tex_path = os.path.join(ROOT, "chapters", "gen-epics.tex")
    os.makedirs(os.path.dirname(tex_path), exist_ok=True)
    with open(tex_path, "w") as fh:
        fh.write("% Generated by scripts/epics.py; do not edit.\n")
        fh.write(r"\begin{longtable}{@{}p{1.4cm}p{5.8cm}p{0.9cm}p{4.3cm}p{1.95cm}@{}}" + "\n")
        fh.write(r"\toprule ID & Epic & Mile. & Depends on & Status\\ \midrule\endhead" + "\n")
        fh.write(r"\bottomrule\endfoot" + "\n")
        fh.write("\n".join(rows) + "\n")
        fh.write(r"\end{longtable}" + "\n")
    # Swimlane: tracks x milestones, each cell lists its epics coloured by status.
    order = ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "UI", "BG"]
    colour = {"Done": "bwgreen", "In progress": "bworange", "To do": "bwdark"}
    lane = [r"% Generated by scripts/epics.py; do not edit.",
            r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{2.35cm}*{9}{>{\centering\arraybackslash}p{1.12cm}}@{}}",
            r"\toprule",
            " & ".join([r"\textbf{Track}"] + [r"\textbf{" + m + "}" for m in order]) + r"\\",
            r"\midrule"]
    for key, name in TRACKS.items():
        cells = []
        for m in order:
            ids = [e for e in EPICS if e["id"][3:6] == key and e["milestone"] == m]
            cells.append(" ".join(r"\textcolor{" + colour[e["status"]] + "}{" + e["id"][7:] + "}"
                                          for e in ids))
        lane.append(r"\scriptsize " + tex_escape(name) + " & "
                    + " & ".join(r"\scriptsize " + c if c else "" for c in cells)
                    + r"\\[2pt]")
    lane += [r"\bottomrule", r"\end{tabular}"]
    with open(os.path.join(ROOT, "chapters", "gen-swimlanes.tex"), "w") as fh:
        fh.write("\n".join(lane) + "\n")
    counts = {}
    for e in EPICS:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print(f"{len(EPICS)} epics -> {csv_path}, {tex_path}; {counts}")


if __name__ == "__main__":
    main()
