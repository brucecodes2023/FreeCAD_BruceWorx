# SPDX-License-Identifier: LGPL-2.1-or-later
"""PDM reference model: items, revisions, lifecycle, change control, BOM (BW-PDM-02).

Storage-independent. Whichever home BW-PDM-01 picks (Ops as PLM, Ops + Git
LFS, a FreeCAD vault, or an open-source PLM), it must behave exactly like this
module; the tests in ``tests/test_pdm.py`` are the contract. No FreeCAD import.

Decisions this encodes (roadmap interview, 18-19 Oct 2026):

* The part number never contains the revision. Drawings and release packages
  print ``P/N-REV`` (:func:`display_part_number`).
* Pre-release revisions are numeric, ``01, 02, ...`` (ASME Y14.35 practice).
  Every review rejection moves to the next number.
* The first approval releases letter ``A``. After that a letter changes only
  through an approved ECR -> ECO. Letters skip I, O, Q, S, X and Z, and run
  ``A .. Y, AA, AB, ...``.
* States: WIP -> In Review -> Released; an item can be retired to Obsolete.
  "Superseded" is a flag, not a state: on an older released letter, or on a
  rejected pre-release number that work has moved past.
* Released revisions are read-only.
* A drawing is its own item, linked to its part. An ECO that opens the part
  opens the drawing too, and both release together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WIP = "WIP"
IN_REVIEW = "In Review"
RELEASED = "Released"
OBSOLETE = "Obsolete"
STATES = (WIP, IN_REVIEW, RELEASED, OBSOLETE)

ITEM_TYPES = ("part", "assembly", "drawing", "cots")

# ASME Y14.35: skip letters that read like digits.
RELEASE_LETTERS = "ABCDEFGHJKLMNPRTUVWY"
PRERELEASE_WIDTH = 2


class LifecycleError(ValueError):
    """A transition the lifecycle does not allow."""


# ---------------------------------------------------------------------------
# Revision codes.


def is_prerelease(code: str) -> bool:
    return code.isdigit()


def first_prerelease() -> str:
    return "1".zfill(PRERELEASE_WIDTH)


def next_prerelease(code: str) -> str:
    if not is_prerelease(code):
        raise ValueError(f"{code!r} is not a pre-release revision")
    return str(int(code) + 1).zfill(PRERELEASE_WIDTH)


def release_index(code: str) -> int:
    """``A`` -> 1, ``Y`` -> 20, ``AA`` -> 21 (bijective base 20)."""
    if not code or any(ch not in RELEASE_LETTERS for ch in code):
        raise ValueError(f"{code!r} is not a release revision (letters {RELEASE_LETTERS})")
    value = 0
    for ch in code:
        value = value * len(RELEASE_LETTERS) + RELEASE_LETTERS.index(ch) + 1
    return value


def release_code(index: int) -> str:
    if index < 1:
        raise ValueError("release index starts at 1")
    base = len(RELEASE_LETTERS)
    letters = []
    while index:
        index, rem = divmod(index - 1, base)
        letters.append(RELEASE_LETTERS[rem])
    return "".join(reversed(letters))


def first_release() -> str:
    return RELEASE_LETTERS[0]


def next_release(code: str) -> str:
    return release_code(release_index(code) + 1)


def validate_revision(code: str) -> str:
    if is_prerelease(code):
        return code
    release_index(code)
    return code


def display_part_number(part_number: str, revision: str) -> str:
    """The form printed on drawings and in release packages."""
    return f"{part_number}-{validate_revision(revision)}"


def strip_revision(legacy: str) -> str:
    """``LE-01-01001-001-A`` -> ``LE-01-01001-001`` (migration of old labels)."""
    head, sep, tail = legacy.rpartition("-")
    if sep and tail and (tail.isalpha() or tail.isdigit()) and head.count("-") >= 3:
        return head
    return legacy


# ---------------------------------------------------------------------------
# Data model.


@dataclass
class Revision:
    code: str
    state: str = WIP
    eco: str | None = None  # ECO that opened it; None for the pre-release line
    superseded: bool = False
    history: list = field(default_factory=list)

    @property
    def editable(self) -> bool:
        return self.state == WIP


@dataclass
class Item:
    part_number: str
    item_type: str = "part"
    description: str = ""
    drawing_of: str | None = None  # for drawings: the part they document
    revisions: list = field(default_factory=list)
    obsolete: bool = False

    @property
    def latest(self) -> Revision:
        return self.revisions[-1]

    @property
    def released(self) -> Revision | None:
        for rev in reversed(self.revisions):
            if rev.state == RELEASED and not rev.superseded:
                return rev
        return None


@dataclass
class ECR:
    number: str
    problem: str
    items: list
    status: str = "Open"  # Open -> Approved | Rejected


@dataclass
class ECO:
    number: str
    ecrs: list
    items: list
    status: str = "Open"  # Open -> Released | Cancelled


class Vault:
    """In-memory reference of the lifecycle rules. A real store implements the
    same operations over its own persistence."""

    def __init__(self):
        self.items: dict[str, Item] = {}
        self.ecrs: dict[str, ECR] = {}
        self.ecos: dict[str, ECO] = {}
        self.bom: dict[str, list[tuple[str, int]]] = {}  # parent P/N -> [(child P/N, qty)]

    # ----- items ------------------------------------------------------

    def create_item(self, part_number, item_type="part", description="", drawing_of=None):
        if part_number in self.items:
            raise LifecycleError(f"{part_number} already exists")
        if item_type not in ITEM_TYPES:
            raise ValueError(f"unknown item type {item_type!r}")
        if item_type == "drawing" and drawing_of not in self.items:
            raise LifecycleError("a drawing must name the part it documents")
        item = Item(part_number, item_type, description, drawing_of)
        item.revisions.append(Revision(first_prerelease(), history=["created"]))
        self.items[part_number] = item
        return item

    def drawings_of(self, part_number):
        return [i for i in self.items.values() if i.drawing_of == part_number]

    # ----- review and release ----------------------------------------

    def submit(self, part_number):
        rev = self._latest(part_number)
        self._require(rev, WIP, "submit")
        rev.state = IN_REVIEW
        rev.history.append("submitted")
        return rev

    def reject(self, part_number, reason=""):
        item = self.items[part_number]
        rev = item.latest
        self._require(rev, IN_REVIEW, "reject")
        rev.history.append(f"rejected: {reason}" if reason else "rejected")
        if rev.eco is None:
            # Pre-release line: the rejected number stays in history; work
            # continues on the next number.
            rev.superseded = True
            nxt = Revision(next_prerelease(rev.code), history=[f"after rejection of {rev.code}"])
            item.revisions.append(nxt)
            return nxt
        rev.state = WIP  # ECO working letter is only spent on release
        return rev

    def approve(self, part_number):
        """Release a pre-release revision as ``A``. ECO revisions release
        through :meth:`release_eco`, together with the rest of the ECO."""
        item = self.items[part_number]
        rev = item.latest
        self._require(rev, IN_REVIEW, "approve")
        if rev.eco is not None:
            raise LifecycleError(f"{part_number} rev {rev.code} releases with {rev.eco}")
        if item.released is not None:
            raise LifecycleError(f"{part_number} is already released; changes need an ECO")
        rev.history.append(f"released from {rev.code}")
        rev.code = first_release()
        rev.state = RELEASED
        return rev

    def retire(self, part_number):
        item = self.items[part_number]
        if item.released is None:
            raise LifecycleError(f"{part_number} has no released revision to retire")
        users = self.where_used(part_number, released_only=True)
        if users:
            raise LifecycleError(f"{part_number} is still used by {', '.join(sorted(users))}")
        item.released.state = OBSOLETE
        item.obsolete = True

    # ----- change control ----------------------------------------------

    def raise_ecr(self, number, problem, items):
        for pn in items:
            if self.items[pn].released is None:
                raise LifecycleError(f"{pn} is not released; fix it in its pre-release line")
        ecr = ECR(number, problem, list(items))
        self.ecrs[number] = ecr
        return ecr

    def decide_ecr(self, number, approved):
        ecr = self.ecrs[number]
        if ecr.status != "Open":
            raise LifecycleError(f"{number} is already {ecr.status}")
        ecr.status = "Approved" if approved else "Rejected"
        return ecr

    def open_eco(self, number, ecr_numbers):
        ecrs = [self.ecrs[n] for n in ecr_numbers]
        for ecr in ecrs:
            if ecr.status != "Approved":
                raise LifecycleError(f"{ecr.number} is {ecr.status}, not Approved")
        affected = []
        for ecr in ecrs:
            for pn in ecr.items:
                for related in [pn] + [d.part_number for d in self.drawings_of(pn)]:
                    if related not in affected:
                        affected.append(related)
        # Check every item before changing any, so a refusal leaves no partial ECO.
        for pn in affected:
            item = self.items[pn]
            if item.latest.state in (WIP, IN_REVIEW):
                raise LifecycleError(f"{pn} already has work in progress ({item.latest.code})")
        for pn in affected:
            item = self.items[pn]
            base = item.released.code if item.released else None
            code = next_release(base) if base else first_release()
            item.revisions.append(Revision(code, eco=number, history=[f"opened by {number}"]))
        eco = ECO(number, list(ecr_numbers), affected)
        self.ecos[number] = eco
        return eco

    def release_eco(self, number):
        eco = self.ecos[number]
        if eco.status != "Open":
            raise LifecycleError(f"{number} is {eco.status}")
        pending = [pn for pn in eco.items if self.items[pn].latest.state != IN_REVIEW]
        if pending:
            raise LifecycleError(f"{number}: not in review yet: {', '.join(pending)}")
        for pn in eco.items:
            item = self.items[pn]
            old = item.released
            if old is not None:
                old.superseded = True
            rev = item.latest
            rev.state = RELEASED
            rev.history.append(f"released by {number}")
        eco.status = "Released"
        return eco

    # ----- BOM -----------------------------------------------------------

    def set_bom(self, parent, lines):
        for child, qty in lines:
            if child not in self.items:
                raise LifecycleError(f"unknown child {child}")
            if qty <= 0:
                raise ValueError("quantity must be positive")
        previous = self.bom.get(parent)
        self.bom[parent] = list(lines)
        if self._has_cycle():
            if previous is None:
                del self.bom[parent]
            else:
                self.bom[parent] = previous
            raise LifecycleError(f"BOM of {parent} would contain itself")

    def explode(self, top):
        """Total quantity of every item under ``top`` (``top`` itself excluded):
        sum over paths of the product of quantities, in topological order."""
        order = self._topological(top)
        total = {top: 1}
        for node in order:
            for child, qty in self.bom.get(node, []):
                total[child] = total.get(child, 0) + total.get(node, 0) * qty
        total.pop(top)
        return total

    def flattened(self, top):
        """Leaf items only (parts, COTS), with total quantities."""
        return {pn: q for pn, q in self.explode(top).items() if not self.bom.get(pn)}

    def where_used(self, part_number, released_only=False):
        """Every assembly that contains ``part_number`` directly or indirectly."""
        parents = {}
        for parent, lines in self.bom.items():
            for child, _qty in lines:
                parents.setdefault(child, set()).add(parent)
        found, stack = set(), [part_number]
        while stack:
            for parent in parents.get(stack.pop(), ()):
                if parent not in found:
                    found.add(parent)
                    stack.append(parent)
        if released_only:
            found = {pn for pn in found if self.items[pn].released is not None}
        return found

    # ----- helpers ---------------------------------------------------------

    def _latest(self, part_number):
        return self.items[part_number].latest

    @staticmethod
    def _require(rev, state, action):
        if rev.state != state:
            raise LifecycleError(f"cannot {action} rev {rev.code}: it is {rev.state}, not {state}")

    def _topological(self, top):
        order, seen = [], set()

        def visit(node):
            if node in seen:
                return
            seen.add(node)
            for child, _qty in self.bom.get(node, []):
                visit(child)
            order.append(node)

        visit(top)
        return list(reversed(order))

    def _has_cycle(self):
        state = {}

        def visit(node):
            if state.get(node) == 1:
                return True
            if state.get(node) == 2:
                return False
            state[node] = 1
            for child, _qty in self.bom.get(node, []):
                if visit(child):
                    return True
            state[node] = 2
            return False

        return any(visit(n) for n in list(self.bom))
