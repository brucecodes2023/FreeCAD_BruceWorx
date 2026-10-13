# Upstream sync policy (BruceWorx)

## Branches

| Branch | Meaning |
|---|---|
| `upstream-main` | A pure mirror of `FreeCAD/FreeCAD` `main`. Never commit to it. Update it only by fast-forward. |
| `main` | The BruceWorx product branch: an upstream release tag (currently **1.1.4**) plus our `[BW]` commits on top. |
| `bw/*` | Feature branches. They are merged into `main` through PRs. |

All of our commits are prefixed with `[BW]`. That's how we find our delta:

```sh
git log --oneline --grep='^\[BW\]' <upstream-tag>..main
```

## Design rule: add-ons and preferences, not core rewrites

BruceWorx changes should be shaped so that they survive rebases:

* Prefer **new workbenches/add-on modules, macros, preference packs and
  default parameter changes** over edits to upstream C++/Python core files.
* When a core change can't be avoided, keep it small and self-contained, put
  it behind a preference where possible, and consider upstreaming it.
* Don't reformat upstream code or move upstream files around.
* Docs, CI and packaging files we own (`BUILDING-BRUCEWORX.md`,
  `UPSTREAM-SYNC.md`, `NOTICE`, `.github/workflows/bruceworx-*`) are new files,
  so they never conflict.

## Cadence

1. **Now:** stay on FreeCAD **1.1.4**. Bring in upstream point releases on the
   1.1 line (1.1.x) when they are tagged.
2. **FreeCAD 26.3:** don't track 26.3 pre-releases on `main`. Within **about
   2 weeks after the final 26.3 tag**, rebase all `[BW]` commits onto that tag.
3. **After 26.3:** rebase onto **each upstream release tag** within about 2
   weeks of its release.

`upstream-main` may be used at any time to *preview* conflicts (see below),
but `main` is only ever based on a release tag.

## Procedure

```sh
git remote add upstream https://github.com/FreeCAD/FreeCAD.git   # once
git fetch upstream --tags
git push origin upstream/main:upstream-main                      # refresh mirror (fast-forward only)

OLD=1.1.4; NEW=<new tag>
git switch -c bw/rebase-$NEW main
git rebase --onto $NEW $OLD        # replays only the [BW] commits
# resolve conflicts (see below), then:
pixi run configure-release && pixi run build-release && pixi run test-release
git push -u origin bw/rebase-$NEW
gh pr create --draft --base main --title "[BW] Rebase onto FreeCAD $NEW"
```

Once CI is green and the change has been reviewed, `main` is reset to the
rebased branch (`git push --force-with-lease origin bw/rebase-$NEW:main`). Tag
the old `main` first (for example `bw-pre-$NEW`) so the previous state stays
reachable.

## Conflict handling

* **Upstream wins by default.** When a `[BW]` commit conflicts with upstream
  code, start from the upstream version and re-apply our intent on top.
  Don't keep stale upstream code.
* **Upstream already does it:** if upstream now implements what a `[BW]`
  commit did, drop our commit (`git rebase --skip`) and note this in the PR.
* **Repeated conflicts** in the same core file mean the change should be
  re-shaped into an add-on, preference or hook. Open an issue for it.
* **Dependency/toolchain changes** (`pixi.toml`, `pixi.lock`, `CMakePresets.json`):
  take upstream's version, then re-apply only our minimal tweaks. Regenerate
  `pixi.lock` with `pixi install` instead of hand-merging it.
* **CI:** upstream workflows are kept as they are. Our CI lives in
  `bruceworx-ci.yml`, so it doesn't conflict.
* Use `git rerere` (`git config rerere.enabled true`) so that resolutions are
  reused across rehearsals on `upstream-main` and the real rebase.
* Every rebase PR lists the dropped, squashed or rewritten `[BW]` commits.
