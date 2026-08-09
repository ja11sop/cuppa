# Design ideas scratchpad

- **Status:** living
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); [`design/README.md`](../README.md) (graduate notes into `plans/` then ROADMAP)
- **Updated:** 2026-08-09

Scratchpad for suggestions that may become new plans or updates to existing ones.
The goal is to turn these notes into actionable, well-understood plan elements.

When a note graduates, create or update a document under `design/plans/`, add or adjust the
matching [`ROADMAP.md`](../../ROADMAP.md) row, then **remove** the note from this file.
Priority is decided at that graduation step — not here.

Do not put private project names here; use anonymised labels and
`INTERNAL_PROJECTS.local.md` for the map.

## Update: plans/boost-updates.md

### Latest boost version

If we do not already have a `--boost-latest-version` config setting we should add one. When Cuppa
checks the Boost website for the latest version it should write that value into `.cuppaconfig`
*if* it differs from the default version in the Boost dependency. That setting might eventually
replace the hard-coded default entirely.

Typical CI shape that motivates this:

1. Online, parallel: clone or download dependencies and build quickly (including Boost), for
   example:

```shell
cuppa --dbg --rel --cov --parallel
```

2. Offline, serial tests (everything already downloaded):

```shell
cuppa --dbg --rel --cov --test --offline
```

If Cuppa’s declared “latest” Boost is older than the version fetched online in step 1 (common
around a Boost release), step 2 offline will honour the older declared version, find that older
archive under `--downloads-root`, and build/use it instead of the newer tree from step 1.

A persisted `--boost-latest-version` (or equivalent) would make step 2 reuse the version
discovered online in step 1.

### Boost name clashes and built-in dependencies (possibly a separate plan)

Built-in dependencies such as `boost` are registered automatically. Consumers then opt in with
`env.BuildWith()` or `default_dependencies`.

A name taken by a built-in cannot be reused for another dependency. Consumer projects often
register a GitLab Boost package under a different name (for example `boost_package`) to avoid
clashing with the built-in `boost`.

Type selectors may help: `[archive]boost`, `[gitlab]boost`, `[conan]boost`.

Open questions:

- Should type selectors be required always, or only when a name is ambiguous?
- Should selection distinguish more than “available” vs “default”, for example:
  - known / accessible
  - imported / made available to this project
  - used by default

Today every built-in is automatically available (by design, for convenience). The longer-term
direction is to move built-ins into their own repositories so `pip install` auto-registration
acts as the “import” step. That is environment-scoped, not `sconstruct`-scoped.

A backwards-compatible approach might keep today’s auto-register behaviour unless an
`sconstruct` opts into an explicit list (`cuppa.import_dependencies([...])` /
`cuppa.use_dependencies([...])`, perhaps with `cuppa.explicit_dependencies()` so nothing is
available until imported). Naming (`env.UseDependency`, `env.Import`, …) is unsettled; “import”
may be too general.

This may need a broader dependency-selection plan; it surfaces here because of Boost.

## New plan(s): Output processing

### Supporting native coloured toolchain output

Early Cuppa colourised toolchain output itself because compilers did not. Cuppa still parses
build output for diagnostics and normalises formatting across toolchains.

Modern toolchains ship their own coloured, formatted diagnostics. A flag such as
`--native-output` (alongside existing `--raw-output` and related options) would allow preferring
that native presentation.

### Minimal / terse output with coloured progress

`--minimal-output` still shows toolchain command lines; otherwise it focuses on errors and
warnings.

A closer analogue to familiar CMake-style progress — perhaps `--terse-output` or
`--simple-output` — would print a short coloured status line per action (success emphasised)
and keep command lines for failures/warnings only. The goal is less console noise for readers
who only care about the invocation when something goes wrong — not a CMake clone.

### stderr vs stdout

Today logging and build output largely share stdout. A clearer split may be: logging → stderr,
primary tool output → stdout, with a normal interactive run still showing both. Validate current
behaviour before changing anything.

## New plan(s): Toolchains

### Coverage for MSVC / `cl`

Assess what is involved and write a plan. Should integrate with the existing GCC/Clang coverage
reporting path.

### Add `--list-toolchains`

List both automatically discovered toolchains and manually registered ones (wording TBD:
“automatically discovered” vs “automatically registered”, and the matching manual term), similar
in spirit to `--list-dependencies`. Only manually registered toolchains would be wipeable.

Also show the full path to the driver (`clang++`, `g++`, …) so callers that need the binary
directly know where it is.

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

### Split methods into their own pages

Build methods are core `sconscript` vocabulary; each Cuppa method deserves its own page and
examples. Also cover a small set of canonical SCons methods (for example `env.Install()`) that
are commonly used with Cuppa progress helpers, so the methods section is comprehensive enough
for most projects — possibly grouped for navigation.

Why not only link to SCons docs?

1. SCons documentation is hard to navigate, version-fragmented, and often too simplistic for
   real projects.
2. Readers should learn Cuppa without depending on off-site docs that may be stale or misleading
   in a Cuppa context.

Phased approach:

- Phase 1: one page per Cuppa method
- Phase 2: key SCons methods, then subgrouping

### Better Antora UI bundle

Default Antora styling is adequate; something closer to the Boost Antora UI bundle or MkDocs
would read better. Boost bundle (reference only — not drop-in):

https://github.com/boostorg/website-v2-docs/releases/download/ui-develop/ui-bundle.zip

It breaks some structural elements as-is; extracting primary styling into a custom bundle may
still be viable.

### Better Mermaid styling

Adopt a custom Mermaid theme that fits the docs. Candidate: Material theme from
https://github.com/gotoailab/modern_mermaid (live example:
https://modern-mermaid.live/?theme=material).

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
