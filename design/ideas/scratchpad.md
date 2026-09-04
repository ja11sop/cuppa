# Design ideas scratchpad

- **Status:** living
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); [`design/README.md`](../README.md) (graduate notes into `plans/` then ROADMAP)
- **Updated:** 2026-09-04

Scratchpad for suggestions that may become new plans or updates to existing ones.
The goal is to turn these notes into actionable, well-understood plan elements.

When a note graduates, create or update a document under `design/plans/`, add or adjust the
matching [`ROADMAP.md`](../../ROADMAP.md) row, then **remove** the note from this file.
Priority is decided at that graduation step — not here.

Do not put private project names here; use anonymised labels and
`INTERNAL_PROJECTS.local.md` for the map.

### Graduated (removed from this file)

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
- Boost name clashes / BuildWith type resolve → [`plans/dependency-resolve.md`](../plans/dependency-resolve.md) (Quince #250; boost-updates cross-link)

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
