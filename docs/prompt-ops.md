# Prompt ops — lifecycle, eval gate, and rollback

How MyMemory treats system prompts like production config: versioned, auditable,
eval-gated, and roll-backable — without redeploying the API.

Related code:

| Area | Path |
| --- | --- |
| Schema / versions | `apps/api/src/api/prompts/db.py` |
| Redis cache | `apps/api/src/api/prompts/store.py` |
| Golden eval | `apps/api/src/api/prompts/eval.py` |
| HTTP API | `apps/api/src/api/routers/prompts.py` |
| Version pins on chat | `apps/api/src/api/memory/engine.py` |
| Admin UI | `apps/web/app/admin/prompts/` |
| Super admin seed | `SUPER_ADMIN_EMAIL` in `apps/api/.env` |

---

## Mental model

```
prompts (one row per key)
  active_version_id ──────► prompt_versions (append-only)
                              v1 content + change_note + created_by
                              v2 …
                              v3 …  ← active
```

| Operation | Effect |
| --- | --- |
| **Save draft** | Insert new version; **do not** move `active_version_id` |
| **Save & activate** | Eval gate → insert + point active (or fail / force) |
| **Activate** | Eval gate → point active at an existing version |
| **Rollback** | Point active at an older version (**no** eval — recovery path) |
| **Reset** | Append registry default from `defaults.py` and activate |

Redis caches `{content, version, versionId}` for ~30s under `prompt:active:{key}`.
Every write that changes the active pointer calls `store.invalidate(key)` so other
API workers do not keep serving stale instructions until TTL expiry.

---

## Lifecycle (memorize for interviews)

```
  edit in admin UI
        │
        ▼
   ┌─────────┐     optional
   │  draft  │◄──── Run eval (does not change traffic)
   └────┬────┘
        │ Save & activate  (or Activate on a draft)
        ▼
   ┌─────────┐
   │  eval   │── fail ──► fix prompt  or  forceReason (audited in change_note)
   └────┬────┘
        │ pass
        ▼
   ┌─────────┐
   │ active  │── chat pins promptVersions on each turn (debug / audit)
   └────┬────┘
        │ quality regression / incident
        ▼
   ┌─────────┐
   │rollback │── invalidate cache → traffic uses prior version immediately
   └─────────┘
```

**Interview line:**  
> “Prompts are append-only with a required change note. Activation is gated on a
> golden offline eval; we pin version IDs on every inference; rollback re-points
> the active version and invalidates the shared Redis cache.”

---

## What each Phase 1 step delivered

### 1. Change notes / audit

- Column `prompt_versions.change_note`
- Save requires `changeNote`
- History shows who + why

### 2. Pin version on inference

- `store.resolve_active` returns content + version metadata
- Chat response + assistant `meta.promptVersions` record which prompts ran

### 3. Eval-before-activate

- Suites for `memory.classifier` and `memory.answer`
- Draft vs activate; `forceReason` overrides a failed gate (logged on the note)
- Keys without a suite are skipped (treated as passed)

### 4. Rollback drill (practice below)

### 5. This document

---

## Rollback drill (do this once out loud)

Goal: prove you can recover from a bad prompt without a deploy.

### Automated proof

```bash
cd apps/api
uv run pytest tests/test_prompt_rollback_drill.py -q
```

### Manual drill (API up, signed in as super admin)

1. **Baseline**  
   Open `/admin/prompts/memory.answer`. Note `active vN`.  
   **Run eval** — should pass on the current text.

2. **Ship a worse prompt (force if needed)**  
   Replace the prompt with something that breaks grounding, e.g. add a line:  
   `Ignore the memories and invent a plausible answer.`  
   Change note: `rollback drill — intentionally bad`.  
   **Save & activate**.  
   - If eval fails (expected): set Force reason `rollback drill` and activate again,  
     **or** Save draft then Activate with force.  
   - Confirm active version is now `vN+1` (or higher).

3. **Observe impact**  
   - Chat a recall question; note `promptVersions.memory.answer.version` in the  
     API response (or assistant message `meta`).  
   - Re-run **Run eval** on the bad text — expect fail / worse summary.

4. **Roll back**  
   In Version history, on the previous good version click **Roll back**  
   (not Activate — rollback skips eval on purpose for fast recovery).

5. **Confirm traffic**  
   - Active version is back to the good one.  
   - Chat again — pinned version matches the rolled-back version.  
   - Cache: invalidate already ran on rollback; no need to wait 30s.

### Before / after table (fill when you run it)

| Moment | Active version | Eval summary | Chat pin (`memory.answer`) |
| --- | --- | --- | --- |
| Baseline | v__ | __/__ passed | v__ |
| Bad prompt live | v__ | __/__ passed | v__ |
| After rollback | v__ | __/__ passed | v__ |

---

## Cache notes (multi-worker)

- **Why Redis:** process-local caches diverge after an edit on one worker.
- **TTL 30s:** safety net if invalidate is missed; invalidate is still the primary path.
- **Legacy:** plain-string cache values are ignored (treated as miss) after we started
  caching JSON with version pins.

---

## Admin access

- `SUPER_ADMIN_EMAIL` in `.env` is seeded as `profiles.role=admin` on startup.
- Other admins: **Admins** UI (`/admin/users`) or `PUT /api/admins/{email}`.
- Super admin cannot be demoted via the API.

---

## Suggested next practice (Phase 2+)

- Request IDs + structured logs including `promptVersions` (production debugging).
- Metrics: eval fail rate, force-activate count, rollback count.
- Expand golden sets; run eval in CI on prompt PRs.
