---
description: Audit the current phase against its plan doc — DoD status, gaps, and binding-rule violations
---

You are auditing Patchwork Assurance against its own plan. Be honest and specific; this is a real
status check, not reassurance.

1. **Identify the active phase.** Read `docs/ROADMAP.md` §6 (the phase spine) and the matching
   `docs/roadmap/phase-N-*.md`. If a `phase-N-*-IMPLEMENTATION.md` exists, read it too. Infer the
   current phase from what exists in the repo.

2. **Check the Definition of Done.** Go through the active phase's DoD checklist item by item. For each,
   inspect the actual code/files and report: met / partial / not started — with the file or evidence.
   Do not take the plan's word for it; verify against the tree.

3. **Check the binding rules / invariants** (`CLAUDE.md` "Architecture invariants" and `.claude/rules/`):
   - `core/` imports inward only (never imports `api/` or `ui/`).
   - No hardcoded statutes; corpus-as-folder honored.
   - Stateless: no auth, no DB, no saved history.
   - The not-legal-advice chrome is present on every surface.
   - No Phase 6+ feature built before v1 (Phases 0–5) is deployed and works end to end.
   Flag any violation as a real bug.

4. **Report**: a short table of DoD status, a list of concrete gaps to close the phase, and any
   invariant violations. End with the single most useful next action. Do not commit or push anything.
