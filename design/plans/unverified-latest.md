# Plan: registry `latest` when the check cannot run

- **Status:** done
- **Related:** [`gitlab-package-latest.md`](../archive/gitlab-package-latest.md); `cuppa/package_managers/gitlab_latest.py`; `cuppa/package_managers/package_version_bound.py`; [`console-stop-error-reporting.md`](console-stop-error-reporting.md); [`cxx-profiles-report.md`](cxx-profiles-report.md) (end-of-build diagnostics — different pattern, see below)
- **Updated:** 2026-10-31
- **Impact:** `patch` if consume reuses a remembered pin; no flag required for the recommended option

## What happened

Online, with Boost 1.92 already extracted, and a GitLab token that has expired:

```text
cuppa --cov --test --native-output --toolchains=gcc15 --show-test-output
```

Configure dies before the build:

```text
cuppa: build_with_package: [error] [boost_package] GitLab Packages API failed for [boost] (HTTP 401): HTTP Error 401: Unauthorized
cuppa: __init__: [critical] Cuppa terminated by exception [StopError: Cannot resolve version [latest] for package [boost_package]: …]
scons: *** Cannot resolve version [latest] for package [boost_package]: … Stop.
```

The same command with `--offline` prints `Offline: using remembered registry latest [1.92] for package [boost]` and continues. The operator is online. They have the cached package. They cannot prove it is still the registry tip because the token is dead. That is a failed **check**, not a missing package.

The Boost test abort in the offline transcript (`funding_rate_table`, error 201) is the consumer test. It is not this problem.

## Why `latest` stops and a network blip does not

`list_generic_package_versions` splits failures in two:

| Failure | Exception |
|---------|-----------|
| `HTTPError` (401, 403, 404, 500, …) | `GitlabLatestError` |
| `URLError` (DNS, connection) | `GitlabLatestNetworkError` |

`resolve_latest_package_version` (the `version="latest"` path, including a missing version, which means latest) only reuses the remembered pin for `GitlabLatestNetworkError`, and only when `allow_remembered_on_network_error` is true. Consume sets that. Publish passes false (`publish_version.py`). The reuse path warns and names `--offline`.

HTTP 401 is not that class. `BuildWithPackage.default_version` logs it as an error and raises `StopError`. Construct then prints the critical "terminated by exception" line. One refusal, two severities. The critical wrapper is how every `StopError` is shown ([`console-stop-error-reporting.md`](console-stop-error-reporting.md)). Softening that wrapper would not let this build run.

## What already happened in the nearby cases

Option A below is what shipped. This table is the behaviour before that change.

| Situation | Before |
|-----------|--------|
| `latest`, `--offline`, remembered pin | Info, use the pin. No registry call |
| `latest`, `--offline`, no pin | Hard error |
| `latest`, online, DNS/connection, pin present | Warn, use the pin. Do not update the pin |
| `latest`, online, DNS/connection, no pin | Hard error |
| `latest`, online, HTTP 401/403/404, pin present | **Hard error.** The case above |
| `>=` bound, a cached version satisfies, not `--refresh-downloads` | No registry call. Return the local pick |
| `>=` bound, refresh forced, list fails (HTTP **or** network), local pick exists | **Silent** fallback to the local pick (`package_version_bound.py`) |
| Publish resolving `latest` | Never reuse a pin after a failed list |
| Exact version (`fmt/12.2.0`, `date/3.0.5` in the same log) | No list call. A later 401 while fetching the archive is a different failure: the bytes are not here |
| `cuppa` PyPI version probe | Fails open (`None`). Never stops the build |
| Source Boost scrape (`boost_latest_version`) | Different probe (upstream page, not the GitLab token). Already falls back to stored then compiled-in. Leave it alone |

Before this change an expired token was stricter than a DNS failure for `latest`, and stricter than a forced refresh of a `>=` bound, which already continued and did not even warn. DNS reuse now also requires the extract to be on disk, and a 404 on the `>=` refresh is a hard stop.

## Options

### A. Warn now, continue (what shipped)

The first draft also printed a second line after the build. The first real terse run showed that line between `[ready]` and the build, because it ran when the SConstruct returned, and it repeated the durable `[version]` row. That second line is not printed. `--terse-output` keeps `unverified · using remembered 1.92` on the version row (`unverified` is the warning background with normal foreground; `using remembered 1.92` is warning-coloured text; the mid-dot is muted). Normal output warns once at the decision.

Treat **401 and 403** as "could not verify", the same outcome as a network failure, when all of these hold:

- This is consume, not publish (`allow_remembered_on_network_error` stays false for publish).
- A remembered registry pin exists.
- The package tree for that pin is actually on disk. A conf string whose extract was wiped is not "I have it cached". No tree → keep the hard stop.
- The status is auth (401, 403), or the host was unreachable (`URLError`, and 5xx if we want the server-is-down case in the same bucket). **404 stays a hard error** even with a pin: wrong registry or wrong package name, and the pin would hide it.

At the decision, normal output warns with the dependency name, the error (`HTTP 401 - unauthorized`, or that the registry was unreachable), and the pin. Those three are the warning-coloured placeholders. Do not write a new pin; we did not learn a version. `--terse-output` does not also print that logger warning.

No new flag. `--offline` remains "do not try the network at all", which also skips location updates and other fetches. The operator in this case was online; only the token was dead. DNS-failure already continues without a flag, and this is the same kind of miss.

### B. Keep the hard stop, add a bypass only for this case

Error text says the pin and the tree exist, and names a flag such as `--allow-unverified-latest`. The flag does nothing for publish, for 404, or when there is no tree. Default stays "latest means we checked".

This is the right shape if an unverified tip must never be the default. It is a worse fit with the DNS path, which already continues with a warn and no flag. Two "could not check" failures should not have two policies. A flag also has to be discovered at the moment the token has expired.

### C. Warn and continue with no closing reminder

This is A as shipped. The terse `[version]` row is already durable, so a second line does not add a fact.

## Severity

This is a warn, not an error that becomes a critical. If we continue, there is no `StopError` and the critical line goes away on its own. Do not demote every `StopError` to a warning. No pin, no tree, 404, and publish stay hard stops, and those still print error then critical until the stop-error plan changes the wrapper.

## No second line, and not the Profiles collector

`ProfilesDiagnosticCollector` holds compiler diagnostics during a build and writes them at the end. This fact is known at configure. Say it there. Do not record it for a later print, and do not put it in the Profiles report.

The `>=` forced-refresh fallback uses the same warn. Before this change it continued and said nothing.

## Out of scope

- Refreshing or replacing the GitLab token.
- Exact-version archive download failures (no local bytes to reuse).
- Source Boost's upstream scrape.
- Letting publish proceed on an unverified latest.
