# Design ideas scratchpad

- **Status:** living
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); [`design/README.md`](../README.md) (graduate notes into `plans/` then ROADMAP)
- **Updated:** 2026-09-06

Scratchpad for suggestions that may become new plans or updates to existing ones.
The goal is to turn these notes into actionable, well-understood plan elements.

When a note graduates, create or update a document under `design/plans/`, add or adjust the
matching [`ROADMAP.md`](../../ROADMAP.md) row, then **remove** the note from this file.
Priority is decided at that graduation step — not here.

Do not put private project names here; use anonymised labels and
`INTERNAL_PROJECTS.local.md` for the map.

### Graduated (removed from this file)

- Dependent GitLab packages → [`plans/gitlab-package-transitive.md`](../plans/gitlab-package-transitive.md)
- Boost `latest` persistence → [`archive/boost-latest-persistence.md`](../archive/boost-latest-persistence.md)
- `--list-toolchains` → [`archive/list-toolchains.md`](../archive/list-toolchains.md)
- Native coloured toolchain output → [`plans/native-toolchain-output.md`](../plans/native-toolchain-output.md)
- Terse / minimal progress output → [`plans/terse-build-output.md`](../plans/terse-build-output.md)
- Configure-time log hygiene (toolchain spam, variant log fix) → [`plans/build-log-hygiene.md`](../plans/build-log-hygiene.md)
- `cuppa --info` (version without build) → [`plans/cuppa-info.md`](../plans/cuppa-info.md)
- C++ Profiles violation report → [`plans/cxx-profiles-report.md`](../plans/cxx-profiles-report.md)
- Split methods into own pages → [`plans/methods-pages-split.md`](../plans/methods-pages-split.md)
- Better Antora UI bundle → [`plans/antora-ui-bundle.md`](../plans/antora-ui-bundle.md)
- Shiki syntax highlighting → [`plans/shiki-syntax-highlighting.md`](../plans/shiki-syntax-highlighting.md)
- Boost name clashes / BuildWith type resolve → [`archive/dependency-resolve.md`](../archive/dependency-resolve.md) (Quince #250; boost-updates cross-link)

## Output processing (follow-on)

### stderr vs stdout

Today logging and build output largely share stdout. A clearer split may be: logging → stderr,
primary tool output → stdout, with a normal interactive run still showing both. Validate current
behaviour before changing anything. Tracked on ROADMAP as `console-stream-split` when validated.

## New plan(s): Toolchains

### Coverage for MSVC / `cl` (deferred)

Assess what is involved and write a plan. Should integrate with the existing GCC/Clang coverage
reporting path. Deferred while Boost latest persistence and `--list-toolchains` are in flight.

## New plan(s): Dependencies

### GitHub packages (registry consume / publish, like GitLab)

Explore a first-class **GitHub Packages** dependency kind parallel to today’s GitLab package
path (`package_dependency` / `GitlabPackagePublisher`, storage type `gitlab`, list/remove
buckets, optional `cuppa-dependency.json` transitive edges).

**Already reserved / noted (not a plan yet):**

- Token selector `[gh]` is reserved for a future GitHub package kind — see
  [`removal-options.md`](../plans/removal-options.md) §4.15 alias map (`gh` next to `gl`) and
  “Out of scope for §4.15: … implementing a GitHub package kind”; consumer docs echo
  ``[gh] is reserved`` on the removing page.
- No ROADMAP row and no `design/plans/*` document yet. Do **not** treat GitHub *release*
  archive downloads (existing location / HTTP source-archive grouping) as this feature.

**When graduating to a plan, settle at least:**

- GitHub Packages API vs GitLab Generic Packages: auth (`GITHUB_TOKEN` / fine-grained),
  org/user registry URLs, version listing, OS/toolchain stem identity reuse
- Publish surface (GitHub twin of `GitlabPackagePublisher`) and consume
  (`github_package` / `[gh]` storage type)
- Whether transitive `cuppa-dependency.json` (and `--list-dependencies` `requires`) should
  share one manifest format across registries or stay GitLab-first
- Develop / offline / wipe / list parity with GitLab; docs under Dependencies (consume) vs
  Packages (publish)

Trigger: after the GitLab transitive + list work has soaked; write
`design/plans/github-packages.md` (name TBD) and a ROADMAP row before implementation.

### Built-in dependencies in their own repositories

Shipping every built-in inside Cuppa does not scale and is a weak blueprint for third-party
dependencies. Move them out, for example:

- boost → `cuppa-dep-boost`
- quince → `cuppa-dep-quince`
- Qt4 → `cuppa-dep-qt4`
- Qt5 → `cuppa-dep-qt5`

Capture trade-offs: a meta “all cuppa deps” repo vs documenting discrete packages users
`pip install` selectively. A central catch-all repo is probably unhelpful except as an index.

### Qt6 dependency

Add Qt6 alongside Qt4/Qt5. It need not be implemented as a SCons Tool (though copying the Qt5
tool may be expedient); a native Cuppa dependency is fine. Prefer the own-repo layout from the
related plan once that exists.

## New or updated plan(s): Documentation

### Shell / console listing colours (Cursor-like)

Prefer reading shell samples the way Cursor colours them in the editor — especially in **light**
mode: command / executable tokens orange (or amber), flags blue, variables / expansions
purple–magenta, strings and paths clearly distinct from bare text. Today Antora `[source,shell]`
/ `bash` / `console` blocks use the default UI highlighter (or plain), so CLI teaching samples are
harder to scan than coloured report trees (`cuppa-output`).

Relate to [`shiki-syntax-highlighting.md`](../plans/shiki-syntax-highlighting.md) (build-time Shiki
for `bash`/`shell`/`console`, theme mapped to cup-of-tea palettes — not stock nord/github-light).
Also touch [`antora-ui-bundle.md`](../plans/antora-ui-bundle.md) if token colours live in
supplemental CSS. Mermaid theme tweaks do **not** highlight AsciiDoc source listings; only a
highlighter (Shiki or highlight.js grammar + CSS) or hand-authored spans would. Do not confuse
with semantic report HTML (`++++` samples) — those stay on the colourised-samples path.

Graduate to a short plan or a Shiki plan subsection when that work is next; until then keep this
as the reminder of the desired light-mode token map.

### Structure pages folder under docs to match nav structure

For example, copy how integration pages are under the "integration" folder. We should do the same
for dependencies and other multi-page sections to make it easier to navigate the folder as a human
to find documentation that needs to be edited. ROADMAP: `doc-folder-layout`; aligns with
[`methods-pages-split.md`](../plans/methods-pages-split.md).

### Better Mermaid styling

Adopt a custom Mermaid theme that fits the docs. Candidate: Material theme from
https://github.com/gotoailab/modern_mermaid (live example:
https://modern-mermaid.live/?theme=material). ROADMAP: `doc-mermaid-theme`.

### Broader diagram support

Mermaid avoids Kroki network fetches at site build time. A local Kroki (or similar) service via
Docker Compose could unlock PlantUML, Graphviz, and other diagrams when needed. Capture options
and operational cost in a plan. See https://docs.kroki.io/kroki/setup/use-docker-or-podman/ and
https://kroki.io/examples.html.

## New plan(s): Ease of use and interoperability

### Canonical bootstrap scripts

A Linux entry script (`bootstrap.sh`, `cuppa_bootstrap.sh`, `develop.sh`, or similar) that
creates/updates a Python virtualenv, installs Cuppa, then runs a small orientation command
(`--list-toolchains`, or a new `--intro` / `--welcome`).

Illustrative sketch (names and UX unsettled):

```bash
#!/bin/bash
GREEN_FG=`tput setaf 2`
BLUE_FG=`tput setaf 4`
RED_FG=`tput setaf 1`
RESET=`tput sgr0`

sys_py_version=`python -c 'import sys; version=sys.version_info[:3]; print("{0}.{1}".format(*version))'`

existing_venv=false

if [ -f venv/bin/activate ]; then
    echo "There is an existing virtualenv. Checking version..."
    echo "system python version is ${BLUE_FG}$sys_py_version${RESET}"
    source venv/bin/activate
    venv_py_version=`python -c 'import sys; version=sys.version_info[:3]; print("{0}.{1}".format(*version))'`
    echo "${BLUE_FG}venv${RESET} python version is ${BLUE_FG}$venv_py_version${RESET}"
    if [ "$venv_py_version" != "$sys_py_version" ]; then
        echo "Your ${BLUE_FG}venv${RESET} python version is out of date; replacing the virtualenv..."
        deactivate
        echo "Removing out-of-date virtualenv..."
        rm -rf venv
        echo "Creating new virtualenv..."
        echo "python -m virtualenv venv"
        python -m virtualenv venv
        echo "${GREEN_FG}New virtualenv is ready${RESET}"
    else
        echo "${GREEN_FG}Virtualenv is up-to-date${RESET}"
        existing_venv=true
    fi
else
    echo "No virtualenv exists. Creating one..."
    python -m virtualenv venv
fi
echo "Activating ${BLUE_FG}$sys_py_version${RESET} python ${BLUE_FG}venv${RESET} ..."
source venv/bin/activate
echo "Environment activated"

if [ "$existing_venv" = false ] ; then
    echo "Installing cuppa..."
    echo ""
    echo "pip install cuppa"
    echo ""
else
    echo "Reinstalling packages to ensure they are up-to-date..."
    echo ""
    echo "pip install cuppa"
    echo ""
fi

errors_found=false

if pip install cuppa ; then
    echo ""
    echo "${GREEN_FG}Cuppa was installed.${RESET}"
    echo ""
else
    errors_found=true
    echo ""
    echo "${RED_FG}Cuppa could not be installed.${RESET}"
    echo ""
fi

if [ "$errors_found" = false ] ; then
    echo "${GREEN_FG}Cuppa is ready for use!${RESET}"
    cuppa --welcome
else
    echo "${RED_FG}Environment could not be set up for use!${RESET}"
fi
```

Example invocation:

```shell
source cuppa_bootstrap.sh
```
