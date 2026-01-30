# Consistency Check Plan: Core Implementation vs Codebase

## TL;DR
- **Goal**: Verify that the current code implementation aligns with the design specifications in `docs/core-implementation.md`.
- **Deliverable**: A detailed Markdown report `docs/consistency-report.md` listing missing features, deviations, ambiguities, and classification of each gap (Critical / Minor / Ambiguous).
- **Effort**: Large (requires full repository scan & cross‑reference).

---

## Context
- **Design Document**: `docs/core-implementation.md` (covers project structure, CLI command architecture, core modules, error handling, plug‑in system, etc.).
- **Codebase**: Python package under `gm/` (`gm/cli`, `gm/core`, `gm/exceptions`, etc.).

## Work Objectives
1. **Identify all design sections** (e.g., project structure, CLI commands, DI container, plug‑in system, error handling, layout manager, symlink manager, etc.).
2. **Map each section to corresponding implementation files / classes / functions** in the repository.
3. **Detect gaps**:
   - **Missing implementations** – design element not present in code.
   - **Deviations** – behaviour or signatures differ from specification.
   - **Ambiguities** – design describes something vague; need clarification.
4. **Classify each gap** as Critical, Minor, or Ambiguous.
5. **Produce a report** (`docs/consistency-report.md`) with:
   - Table of design items ↔ implementation status.
   - Line number references where applicable.
   - Suggested actions / decisions required.
6. **Optional**: If any gaps require user decisions (e.g., design change), flag them under a "Decisions Needed" section.

## Verification Strategy
- No automated tests required for this analysis (per user request).
- Verification will be manual: the report will contain concrete file paths and line numbers so the executor can inspect.

## Execution Strategy (Parallel Waves)
| Wave | Tasks | Parallelizable |
|------|-------|----------------|
| 1 | **Collect design sections** – parse `core-implementation.md` into a structured list. | Yes (single script) |
| 2 | **Locate implementation candidates** – use `grep` / `ast_grep` to find files matching class / function names defined in design. | Yes |
| 3 | **Cross‑reference** – generate mapping of design → code, note missing items. | Yes |
| 4 | **Classify gaps** – apply criteria (Critical if core functionality missing, Minor for documentation, Ambiguous for unclear spec). | No (depends on previous wave) |
| 5 | **Draft report** – assemble Markdown file with tables and notes. | Yes |

## Recommended Agents & Skills
- **Category**: `ultrabrain` (complex analysis, cross‑referencing).
- **Load Skills**: `explore` (codebase search), `librarian` (fetch design doc if needed), `git-master` (optional for history), `oracle` (optional for strategic guidance).

## TODO List (for execution engine)
- [ ] 1️⃣ Parse `docs/core-implementation.md` into sections with headings.
- [ ] 2️⃣ For each section, define expected code artefacts (module, class, function, file).
- [ ] 3️⃣ Run `grep` / `ast_grep_search` across `gm/` to locate each artefact.
- [ ] 4️⃣ Record file path and line numbers for each found artefact.
- [ ] 5️⃣ Identify missing artefacts → mark as **Critical** if core feature, **Minor** otherwise.
- [ ] 6️⃣ Detect deviations (e.g., method signatures differ, missing docstrings) → mark accordingly.
- [ ] 7️⃣ Flag ambiguous items → require clarification.
- [ ] 8️⃣ Assemble `docs/consistency-report.md` with:
   - Table: Design Item | Expected Location | Status | Line(s) | Gap Type | Notes
- [ ] 9️⃣ Review report for completeness.
- [ ] 🔟 Delete draft file `.sisyphus/drafts/consistency-check.md`.

## Acceptance Criteria
- The generated report lists **all** design items present in the document.
- Each item includes concrete file path(s) and line numbers (or states "Not Implemented").
- All gaps are classified and justified.
- No code modifications are performed.
- The plan file is saved at `.sisyphus/plans/consistency-check.md`.

## Guardrails & Scope
- **IN**: All code under `gm/` and the design doc `docs/core-implementation.md`.
- **OUT**: External dependencies, third‑party libraries, test suite, documentation outside `docs/`.
- Do **NOT** modify any source files; only read.

## Next Steps
- After this plan is approved, run `/start-work` to execute the above TODOs.
- Optionally enable **High Accuracy Review** via Momus for rigorous gap classification.
