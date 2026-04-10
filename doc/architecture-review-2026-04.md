# Architecture Review — Action Items

Captured from a senior-architect review on 2026-04-10. Ordered by priority. Check off as you go.

## P0 — Do soon

- [x] **Remove password debug logging in `routes/auth.py:69-75` and `:168-174`.** ✅ 2026-04-10
  `logger.info(f"🔍 Password repr: {repr(password)}")` logs full passwords. If logs ship anywhere (file aggregator, hosting provider, error tracker), this leaks credentials.

## P1 — Security hardening

- [x] **Lock down CORS.** ✅ 2026-04-10 — Removed `CORS(app)` entirely. All browser UIs (landing page, admin pages) are same-origin with the API, so no cross-origin allowance is needed. Native iOS/Mac apps are unaffected by CORS. If a future web client on a separate origin is added, add a narrow `CORS(app, resources={r"/api/*": {"origins": [...]}})` then.
- [ ] **Add rate limiting on `/auth/*` and `/password/*`.** Flask-Limiter is already commented out in `requirements.txt` — uncomment and wire it up. Account lockout only mitigates brute-force on known accounts, not credential stuffing.
- [x] **Add a pre-commit secret scanner** (gitleaks or detect-secrets). ✅ 2026-04-10 — Added `.github/workflows/secret-scan.yml` running `gitleaks detect` on every push and PR to `main`. Full git history is scanned (`fetch-depth: 0`), so the first CI run doubles as the one-time history audit. Uses the gitleaks binary directly from GitHub releases (pinned to 8.18.4) instead of the license-restricted `gitleaks-action`. This is a server-side, non-bypassable check; a local `git commit --no-verify` can't skip it. Optional future improvement: add a local pre-commit framework hook for faster feedback before push.
- [x] **Mask DB credentials in log output.** ✅ 2026-04-10 — Added a `CredentialScrubFilter` in `config.py` that masks database passwords in DSN strings (`postgresql://user:***@host`) and `password=...` key-value forms before any log record reaches a handler. Installed on the root logger's handlers in `configure_logging()`, so it covers every logger in the process (including psycopg's own exceptions propagating up through f-string logging calls). Left `db_utils.py`'s `CONNECTION_STRING` construction alone — the filter is defense-in-depth and doesn't require changing the pool setup.

## P2 — Structural refactors (biggest quality-of-life wins)

- [ ] **Split `Shared/Support/NetworkManager.swift`** (1,906 lines) into domain services: `SongService`, `RecordingService`, `UserService`, `RepertoireService`, `ResearchService`. Also add `@MainActor` to the class — its peers have it, this one doesn't (line 110).
- [ ] **Split `Shared/Support/Models.swift`** (1,422 lines) by domain: `Models/Song.swift`, `Models/Recording.swift`, `Models/Performer.swift`, etc. This also makes the `PreviewHelpers.swift` update step in `CLAUDE.md` less error-prone.
- [ ] **Extract shared view-model logic for detail views** into `Shared/ViewModels/`. Right now iOS and Mac have parallel implementations of the same data-fetching/state logic in `SongDetailView`, `RecordingDetailView`, `LoginView`. Layouts should stay platform-specific; state and calls should be shared. Every bug fix is currently two fixes.
- [ ] **Group backend integrations into packages.** Mechanical refactor, huge discoverability win:
  ```
  integrations/spotify/    (client, matcher, matching, db, utils)
  integrations/apple_music/
  integrations/musicbrainz/
  integrations/coverart/
  core/                    (auth_utils, email_service, cache_utils, research_queue, song_research)
  ```
- [ ] **Break up god-file importers:** `spotify_matcher.py` (2019), `mb_release_importer.py` (1650), `mb_utils.py` (1465), `apple_music_matcher.py` (905). Split HTTP client / parsing / fuzzy matching / persistence into separate units.

## P3 — Developer experience

- [ ] **Adopt Alembic** (or similar) for schema migrations. `sql/jazz-db-schema.sql` + ad-hoc SQL files is becoming painful — recent VARCHAR(500) overflow and duplicate-recording bugs are the kind of thing a migration tool helps prevent.
- [ ] **Add a minimal pytest suite** (auth flow, matchers, research queue) and wire it into CI alongside `ruff`. Currently CI only runs `test_song_detail_perf.py`.
- [ ] **Add an input validation layer** at route boundaries (Pydantic or marshmallow). Kills a class of bugs and gives you OpenAPI docs for free.

## P4 — Cleanups (quick wins)

- [ ] **Delete `apps/New Group/`** — empty Xcode-default directory.
- [ ] **Consolidate `SharedDataManagers.swift`.** Two copies exist: `apps/SharedDataManagers.swift` and `apps/Mac/Managers/SharedDataManagers.swift`. The root file's own comment says "THIS FILE GOES IN THE MAC APP TARGET ONLY" — so move to `Mac/` and delete the root copy.
- [ ] **Clarify the three `Managers/` directories.** `Shared/Managers/`, `iOS/Managers/`, and `Mac/Managers/` all exist side-by-side, and from the names it's not obvious why. The legitimate reason is that `iOS/Managers/` and `Mac/Managers/` hold share-extension IPC wrappers (platform-specific by nature) while `Shared/Managers/` holds the real cross-platform managers. Either rename the platform-specific ones (e.g., `iOS/ShareExtensionBridge/`, `Mac/ShareExtensionBridge/`) or add a short README in each directory explaining its scope. Prevents future drift and makes it clear where new managers should land.
- [ ] **Replace `print()` with `os.Logger`** in Swift code (~109 in `NetworkManager.swift` alone). Use `.private` for anything PII-adjacent.
- [ ] **Replace force-unwrapped URLs in `AuthenticationManager.swift`** (lines 104, 160, 216, 288, 330, 355, 497, 630) with a single `URL.api(path:)` helper.
- [ ] **Schema cleanup:** redundant UNIQUE constraints on `recording_releases` (the `(recording_id, release_id, disc_number, track_number)` and `(recording_id, release_id)` constraints overlap). Document the dual-MB-ID design on `songs` (`musicbrainz_id` + `second_mb_id`).
- [ ] **Flesh out `README.md`.** Currently one sentence. Your `CLAUDE.md` is better onboarding than your README.

---

## Things that are already good (don't touch)

For reference — these came up during the review but are fine as-is:

- Auth primitives: bcrypt (work factor 12), JWT access/refresh split, account lockout, email-enumeration-safe password reset.
- All SQL is parameterized; no injection risk found.
- `db_utils.py` pooling, health checks, keepalive thread.
- `KeychainHelper.swift` — correct use of `kSecAttrAccessibleWhenUnlocked` and `SecItem*` APIs.
- `AuthenticationManager` token-refresh serialization (prevents concurrent-refresh races).
- `Shared/Managers/FavoritesManager` and `RepertoireManager` are consistently patterned (`@MainActor class ... : ObservableObject` with `@Published` state) — good consistency that the rest of the Swift managers should follow.
- Explicit `MainActor.run { ... }` wrappers on network-completion callbacks show main-thread boundaries are understood, even though `NetworkManager` itself isn't `@MainActor`-annotated.
- Route blueprint layout — thin routes, logic delegated out.
- Database schema — 3NF, 48 FKs with deliberate cascades, 106 indexes, good use of enum types.
- `scripts/script_base.py` shared infrastructure.
- Git hygiene (file-level): `.env`, `cache/`, and the `.p8` Apple key are all properly gitignored and not in history (verified).

> **Correction (2026-04-10):** The initial review claimed git hygiene was "clean" based on verifying those three paths. That was technically accurate but misleadingly incomplete — it did not check for hardcoded secrets inline in source files. When the gitleaks CI workflow was added (see P1), its first run caught 10 historical commits between 2025-10-04 and 2025-11-19 containing the production Supabase database password as a hardcoded fallback default (`os.environ.get('DB_PASSWORD', '<literal>')`) across seven files. The credential was rotated via the Supabase dashboard on 2026-04-10, the remaining at-HEAD occurrences in `diagnose_connections.py` and `venv_setup_instructions.md` were scrubbed in the same session, and the dead-credential fingerprint was added to `.gitleaks.toml` so future scans pass. Lesson: manual review is not a substitute for automated scanning, and the scanner paid for itself on its first run.
