<!-- ADMIN-EDITABLE — SYSTEM-WIDE PROJECT-PLAN GUIDE (.local. override).
     This machine-local copy is used as the default PROJECT_PLAN_GUIDE.md when
     scaffolding new project plans on this machine. Edit freely to change the
     system-wide project-plan rules; it is never overwritten by package updates
     or by the AIOS sync. Delete it to fall back to the package's shipped default.
     A single project/folder can override this further with its own
     PROJECT_PLAN_GUIDE.local.md referenced from that folder's agents.md. -->

# Project Plan Guide (this folder)

> **This file makes the folder self-managing.** It is a copy dropped in when the first project plan
> was scaffolded. Everything needed to create, run, and close project plans in THIS folder is here —
> you do not need to consult any external kit or repository again. If you're an agent picking up work
> in this project, this file plus `index.md` are your source of truth for how plans are run.

A **project plan** is a doc-truth roadmap for a multi-session body of work. Each project is a set of
six files sharing a zero-padded serial (`001_`, `002_`, …) and a topic slug, registered in
`index.md`.

| Role | File | Purpose |
|---|---|---|
| Detail | `NNN_detail-slug.md` | Plan of record: headline, summary, dependencies, traced file map, verbatim brief, your synthesis, the sectioned plan. |
| Status | `NNN_status-slug.md` | Live per-item status + append-only serialized `NOTE NNN-K` decisions. |
| Status archive | `NNN_status_archive-slug.md` | Completed/verified blocks retired out of the live status doc. |
| Orientation | `NNN_current_orientation-slug.md` | Cold-start doc — read instead of a handoff. |
| Action log | `NNN_action_log-slug.md` | Append-only one-line-per-action timeline (no frontmatter). |
| Bugs & debt | `NNN_bugs_and_technical_debt-slug.md` | Running list; cleared or deferred-with-reason before close. |

---

## Creating a new project

1. **Serial** — next unused `NNN` from the `# Projects` list in `index.md`.
2. **Slug** — lowercase, underscore-joined topic (e.g. `auth_token_rotation`). Stable for life.
3. **Create the six files** by copying an existing project's set (or the originals) and substituting
   `NNN`/`SLUG` throughout. Fill: detail (headline → summary → dependencies → relevant files → verbatim
   brief → your understanding → sectioned plan); status (one item per plan section); the others start
   near-empty per their headers.
4. **Register** in `index.md`, linking all six files.
5. **First postcard** in the action log: `project scaffold created (six files + index); planning-only`.
6. **Seed decisions** — record kickoff decisions/open questions as `NOTE NNN-1`, `NOTE NNN-2` in status.

Paste the user's brief **verbatim** into the detail doc. Trace the code before writing your
understanding and the relevant-files map — name real symbols; mark guesses (UNVERIFIED).

---

## Standing upkeep rules (do these without being asked)

1. **Status stays live.** Update each item's `**Status:**` as work lands. Legend:
   `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `DONE` (landed, build-clean) · `VERIFIED` (confirmed in
   the running system). Only `VERIFIED` work is archivable. Keep `DONE` vs `VERIFIED` honest — don't
   claim verified what you haven't run or the user hasn't confirmed.
2. **Record every decision** as a serialized, append-only `## NOTE NNN-K` (newest at bottom; never
   rewrite — supersede). Grep-able: `grep "NOTE NNN-"`.
   ```
   ## NOTE NNN-K | YYYY-MM-DD | <short title>
   - Status: OPEN | RESOLVED | SUPERSEDED-BY-NOTE-NNN-J
   - Sections: <e.g. 1.1, 4.3>
   - Context: <the forces>
   - Decision/Update: <what changed>
   ```
3. **Archive verified work.** Move a `VERIFIED` Section block verbatim into the status archive under a
   dated `## Archived YYYY-MM-DD — <Section>` heading; leave a one-line stub in the live status doc.
4. **Log every meaningful action** as one postcard appended to the action log:
   ```bash
   echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),<postcard>" >> "NNN_action_log-SLUG.md"
   ```
5. **Keep the orientation current** — a couple of plain lines when the shape or next step changes.
6. **Track bugs/debt as they surface** — stable `BUG-NNN-K` / `DEBT-NNN-K` ids; nothing disappears
   silently.

---

## Closing a project (clean rest state)

Closing is deliberate. Run these gates; do not skip them.

**Gates (all pass, or waive in writing):**
- **G1 — every plan item terminal:** `VERIFIED`, `DONE` (with outstanding verification named &
  accepted), or `DROPPED` (with reason + `NOTE`). No item closes `NOT STARTED`/`IN PROGRESS`/`BLOCKED`
  without a `NOTE` saying why and where the work goes.
- **G2 — every bug/debt item cleared:** `FIXED` (commit referenced) or `DEFERRED` (rationale +
  destination). Nothing silent.
- **G3 — decisions settled:** every `NOTE` `RESOLVED`/`SUPERSEDED`/`OPEN (carried to <dest>)`.
- **G4 — dependencies honored:** downstream projects that needed this one actually got the state they
  depend on (or are notified).

**Steps:**
1. Archive remaining live status under `## Archived YYYY-MM-DD — Project close`.
2. Write a final `## NOTE NNN-K | YYYY-MM-DD | Project close` — outcome (shipped vs planned),
   dropped/deferred items + destinations, final branch/tag/commit, successors.
3. Orientation top → closed banner: `STATUS: CLOSED YYYY-MM-DD — <outcome>. See closeout NOTE NNN-K.`
4. Frontmatter `status: closed` across the set.
5. `index.md` project line → `— CLOSED YYYY-MM-DD (<outcome>)`. Keep all links.
6. Final action-log postcard: `PROJECT CLOSED — <outcome>; N verified, M deferred (see NOTE NNN-K)`.
7. Scaffold any successor project now and set its `## Dependencies` upstream pointer back to this one.

**Reopening:** frontmatter `status: draft`; add `## NOTE NNN-K | … | Reopened` (why); restore affected
items from archive to live; update the orientation banner; log `PROJECT REOPENED`. Never delete the
closeout note.

**Closed is not deleted, not perfect, not silent.** Closed projects are permanent record; they stay in
the folder and index. A project may close with named/accounted-for deferred debt. Stopping without
running this checklist is *abandonment*, not closing — prefer a real close.

---

## Overriding these rules for this folder (`.local.`)

This guide is the base rulebook. To change or extend the rules **for this folder only**, create a
`PROJECT_PLAN_GUIDE.local.md` beside this file with just your overrides, and reference it from this
folder's `agents.md` (e.g. `@PROJECT_PLAN_GUIDE.local.md`) so agents load it on top of this base. Keep
`.local.` files git-ignored. Do not edit this base to make folder-specific tweaks — put them in the
`.local.` override so the base stays portable.

## Conventions

- **Serialization is grep-able.** `NOTE NNN-K`, `BUG-NNN-K`, `DEBT-NNN-K` — one `grep` reconstructs a
  thread.
- **Never rewrite history.** Status is updated in place; notes/logs/archive are append-only; supersede
  rather than edit.
- **Optional host integrations stay optional.** If this repo keeps decision records (ADRs), objectives,
  handoffs, or a branch-status doc, cross-reference them from the relevant docs. If it doesn't, the
  plan is fully self-contained — `NOTE` entries are the decision record.
