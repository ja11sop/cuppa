# Plan: registry `latest` when the check cannot run

- **Status:** proposal
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

## What already happens in the nearby cases

| Situation | Today |
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

So an expired token is stricter than a DNS failure for `latest`, and stricter than a forced refresh of a `>=` bound, which already continues and does not even warn.

## Options

### A. Warn now, continue, remind at the end (recommended for consume)

Treat **401 and 403** as "could not verify", the same outcome as a network failure, when all of these hold:

- This is consume, not publish (`allow_remembered_on_network_error` stays false for publish).
- A remembered registry pin exists.
- The package tree for that pin is actually on disk. A conf string whose extract was wiped is not "I have it cached". No tree → keep the hard stop.
- The status is auth (401, 403), or the host was unreachable (`URLError`, and 5xx if we want the server-is-down case in the same bucket). **404 stays a hard error** even with a pin: wrong registry or wrong package name, and the pin would hide it.

At the decision, warn with the package name, the HTTP status, and the pin being used. Do not write a new pin; we did not learn a version.

After the build finishes (success or a later build failure), print one reminder: you asked for latest, the registry was not verified, this build used the remembered version, so it might not be the registry tip. The configure warn is the decision. The closing line is so a long `--cov --test` does not leave that fact only in the scrollback above the build.

No new flag. `--offline` remains "do not try the network at all", which also skips location updates and other fetches. The operator in this case was online; only the token was dead. DNS-failure already continues without a flag, and this is the same kind of miss.

### B. Keep the hard stop, add a bypass only for this case

Error text says the pin and the tree exist, and names a flag such as `--allow-unverified-latest`. The flag does nothing for publish, for 404, or when there is no tree. Default stays "latest means we checked".

This is the right shape if an unverified tip must never be the default. It is a worse fit with the DNS path, which already continues with a warn and no flag. Two "could not check" failures should not have two policies. A flag also has to be discovered at the moment the token has expired.

### C. Warn and continue with no closing reminder

Same as A at configure, nothing at the end. Enough for a short command. Not enough for the coverage run that prompted this: the warn is above a long transcript. Prefer A.

## Severity

This is a warn, not an error that becomes a critical. If we continue, there is no `StopError` and the critical line goes away on its own. Do not demote every `StopError` to a warning. No pin, no tree, 404, and publish stay hard stops, and those still print error then critical until the stop-error plan changes the wrapper.

## End reminder is not the Profiles collector

`ProfilesDiagnosticCollector` holds compiler diagnostics during a build and writes them at the end, because the lines arrive while compiling and the session index is the report. That is "collect during, show at the end".

Here the fact is known at configure. Warn at the decision, then say it again when the build that used the pin has finished. Do not put package warnings into the Profiles report, and do not build a general deferred-diagnostic store for one closing line. A short list recorded at resolve time and printed from the construct exit path is enough.

The `>=` forced-refresh fallback should use that same warn and the same reminder. Today it continues and says nothing, so a refresh that could not verify is quieter than `latest`.

## Out of scope

- Refreshing or replacing the GitLab token.
- Exact-version archive download failures (no local bytes to reuse).
- Source Boost's upstream scrape.
- Letting publish proceed on an unverified latest.
