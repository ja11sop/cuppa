# Note: terse ledger for `--refresh-downloads`

- **Status:** done
- **Related:** [`package-download-freshness.md`](package-download-freshness.md); [`archive/package-download-refresh.md`](../archive/package-download-refresh.md); [`archive/terse-dependency-locations.md`](../archive/terse-dependency-locations.md); [`archive/transfer-and-archive-progress.md`](../archive/transfer-and-archive-progress.md)
- **Updated:** 2026-11-11
- **Impact:** `patch` — ships with 1.14.0 — [#397](https://github.com/ja11sop/cuppa/pull/397)

Done on master via [#397](https://github.com/ja11sop/cuppa/pull/397). Archive when 1.14.0 ships.

Soak on **project B** (consume-only tip) with `--terse-output` (± `-Q`) and
`--refresh-downloads` for a large GitLab package dep.

## What happened

With plain `--terse-output -Q`, live collect/extract already uses the heartbeat row, then durable `→ [collect]` / `→ [extract]`. That is fine — no new `[collecting]` / `[extracting]` durable lines.

Without `-Q` (or with `--verbosity=…` punching INFO through), resolve chatter still includes:

```text
cuppa: gitlab_latest: [info] Stored gitlab_package_latest_… = [1.92] in [.cuppaconfig]
cuppa: gitlab: [info] --refresh-downloads: cleared 3 path(s) for package […]; re-fetching
cuppa: gitlab: [info] Downloading package archive […]…
```

Those duplicate the ledger (`[version]`, heartbeat + `[collect]` / `[extract]`).

## Settled

1. **Demote under `--terse-output`** (including `-Q`) to debug:
   - `Stored … in [.cuppaconfig]` (`remember_registry_latest`)
   - `Downloading package archive […]…` (`download_first_available_package`)
2. **Durable resolve child for force refresh** (like `[update]`, including under `-Q`):

   ```text
               → [location] <google_cloud_cpp> = google-cloud-cpp/3.9.0 · package
   |--•------|   → Downloading google-cloud-cpp_….tar.gz   29% […]  … ETA …
               → [refresh]  <google_cloud_cpp> · 3.9.0 · cache re-fetched
               → [registry] …
               → [collect]  …
               → [extract]  …
   ```

   The refresh **action** is clear + re-download. Live work is the existing
   download heartbeat. Durable `[refresh] · cache re-fetched` is written **only
   after that download completes** — not when clear starts, not after extract.
   Then `[collect]` / `[extract]` follow as today.
   `-n` / `--no-exec` → `would re-fetch` at decision time (no work runs).
   Under terse, the INFO “cleared …; re-fetching” is debug (start chatter only).
3. **`--refresh-downloads` stays force** — always drop + fetch when selected; no HEAD short-circuit. Automatic freshness remains the HEAD path without the flag.

## Not this slice

- Reworking live ProgressReporter into `[collecting]` / `[extracting]` durable lines
- Changing freshness HEAD behaviour
