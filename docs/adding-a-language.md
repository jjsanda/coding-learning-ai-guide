# Adding a language

Languages are plugins. Python and JavaScript each consist of the same five
pieces, and adding a third language means adding the same five pieces again:

1. a **runner image** with the language runtime and its analyzers,
2. **`Analyzer` classes** — one per tool — that emit a sandbox command and
   parse its output into `NormalizedFinding`s,
3. a **registry entry** mapping the language name to its analyzers,
4. **misconception mappings** so findings feed the instructor dashboard,
5. small **wiring**: the runner-image setting, the harness interpreter, and
   the API's language enum.

This guide walks through all five using **Go** as a worked example, modeled
directly on the existing
[`python_tools.py`](../backend/src/codeguide/analyzers/python_tools.py) and
[`javascript_tools.py`](../backend/src/codeguide/analyzers/javascript_tools.py).
The Go code below is illustrative — it follows the real patterns but hasn't
shipped in the repo — so treat it as a template, not a copy-paste guarantee.

## The contract in one screen

From [`analyzers/base.py`](../backend/src/codeguide/analyzers/base.py): an
analyzer contributes one command that runs **inside the sandbox** and a parser
that runs **orchestrator-side** on trusted infrastructure.

```python
@dataclass(frozen=True)
class NormalizedFinding:
    analyzer: str        # tool name, e.g. "gosec"
    rule_id: str         # stable rule id, e.g. "G401" — keys the misconception map
    severity: Severity   # info | warning | error | critical
    category: Category   # style | complexity | security | bug_risk | correctness
    file: str            # path relative to the submission root, e.g. "main.go"
    line_start: int
    line_end: int
    message: str

class Analyzer(Protocol):
    name: str
    languages: frozenset[str]

    def sandbox_step(self) -> Step: ...              # the command to run in the sandbox
    def parse(self, out: StepOutput) -> list[NormalizedFinding]: ...
```

Two helpers do the boring parts: `normalize_path()` strips `/work/` and `./`
prefixes from tool-reported paths, and `load_json_output()` parses a step's
stdout as JSON while tolerating broken/timed-out tools (a misbehaving analyzer
must degrade to zero findings, never fail the submission).

Design rules worth keeping:

- **Analyzers only ever see the pristine submission.** The harness runs all
  analyzer steps *before* the student's program executes.
- **Parsers run on trusted infrastructure** but consume output produced inside
  the sandbox — be defensive: check types, use `.get()` with defaults, return
  `[]` on anything unexpected (every existing parser does).
- **Rule IDs are the API to the taxonomy.** Keep them stable; the
  misconception map and dashboard aggregate by them.

## Step 1 — the runner image

Create `runners/go/Dockerfile`. Two things every runner must have: the
**Python harness** (the in-sandbox entrypoint is Python, so non-Python images
install a minimal `python3`, exactly like the Node runner does) and **pinned
analyzer versions** so findings are reproducible.

```dockerfile
# Sandbox runner for Go submissions.
# Runs with: no network, all capabilities dropped, read-only rootfs,
# non-root user. Analyzer versions are pinned so findings are reproducible.
FROM golang:1.24-bookworm

# The harness is Python; install a minimal Python alongside Go.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

# Pinned analyzers, on PATH for the harness.
RUN go install github.com/securego/gosec/v2/cmd/gosec@v2.22.0 \
    && go install github.com/fzipp/gocyclo/cmd/gocyclo@v0.6.0 \
    && mv /root/go/bin/* /usr/local/bin/

COPY harness/entrypoint.py /opt/runner/entrypoint.py
# COPY rules/semgrep/go /opt/rules/go     # if you add semgrep rules (step 5)

RUN mkdir -p /work && chown 65534:65534 /work

USER 65534:65534
WORKDIR /work

# The rootfs is read-only at runtime; every cache must live on the /tmp tmpfs.
# GOCACHE matters: `go run`/`go vet` refuse to work without a writable cache.
ENV HOME=/tmp \
    TMPDIR=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    GOCACHE=/tmp/gocache \
    GOFLAGS=-mod=mod

ENTRYPOINT ["python3", "/opt/runner/entrypoint.py"]
```

Add it to the `runners` target in the [Makefile](../Makefile):

```make
runners: ## Build the sandbox runner images
	docker build -t coding-learning-ai-guide-runner-python:latest -f runners/python/Dockerfile runners
	docker build -t coding-learning-ai-guide-runner-node:latest -f runners/node/Dockerfile runners
	docker build -t coding-learning-ai-guide-runner-go:latest -f runners/go/Dockerfile runners
```

(Note the build context is `runners/`, so the Dockerfile can `COPY
harness/entrypoint.py`.)

## Step 2 — the Analyzer classes

Create `backend/src/codeguide/analyzers/go_tools.py`. Two full examples: a
JSON-emitting security tool (gosec, closely mirroring `BanditAnalyzer`) and a
plain-text complexity tool (gocyclo, playing radon's role — showing that
parsers aren't limited to JSON).

```python
"""Go analyzers: gosec (security), gocyclo (complexity)."""

import typing

from codeguide.analyzers.base import NormalizedFinding, load_json_output, normalize_path
from codeguide.execution.base import Step, StepOutput
from codeguide.models import Category, Severity


class GosecAnalyzer:
    name = "gosec"
    languages = frozenset({"go"})

    _SEVERITY: typing.ClassVar[dict[str, Severity]] = {
        "LOW": Severity.WARNING,
        "MEDIUM": Severity.ERROR,
        "HIGH": Severity.CRITICAL,
    }

    def sandbox_step(self) -> Step:
        return Step(
            id=self.name,
            cmd=["gosec", "-fmt=json", "-quiet", "./..."],
            timeout_s=60,
        )

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        doc = load_json_output(self.name, out)
        if not isinstance(doc, dict):
            return []
        findings = []
        for item in doc.get("Issues", []):
            line = str(item.get("line", "0")).split("-")  # gosec: "12" or "12-14"
            findings.append(
                NormalizedFinding(
                    analyzer=self.name,
                    rule_id=item.get("rule_id", "gosec"),
                    severity=self._SEVERITY.get(item.get("severity", "LOW"), Severity.WARNING),
                    category=Category.SECURITY,
                    file=normalize_path(item.get("file", "")),
                    line_start=int(line[0] or 0),
                    line_end=int(line[-1] or 0),
                    message=item.get("details", ""),
                )
            )
        return findings


class GocycloAnalyzer:
    name = "gocyclo"
    languages = frozenset({"go"})

    _THRESHOLD = 10  # complexity at/above this becomes a finding

    def sandbox_step(self) -> Step:
        # Output: one "<complexity> <package> <func> <file>:<line>:<col>" per line.
        return Step(
            id=self.name,
            cmd=["gocyclo", "-over", str(self._THRESHOLD - 1), "."],
            timeout_s=60,
        )

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        if out.timed_out:
            return []
        findings = []
        for row in out.stdout.splitlines():
            parts = row.split()
            if len(parts) != 4 or not parts[0].isdigit():
                continue
            complexity, _pkg, func, location = parts
            file, _, rest = location.partition(":")
            line = int(rest.split(":")[0] or 0)
            findings.append(
                NormalizedFinding(
                    analyzer=self.name,
                    rule_id="gocyclo-over",
                    severity=Severity.ERROR if int(complexity) >= 15 else Severity.WARNING,
                    category=Category.COMPLEXITY,
                    file=normalize_path(file),
                    line_start=line,
                    line_end=line,
                    message=(
                        f"'{func}' has cyclomatic complexity {complexity}. "
                        "Deeply branching code is hard to test and to reason about — "
                        "consider splitting it into smaller functions."
                    ),
                )
            )
        return findings
```

A `GoVetAnalyzer` for bug-risk findings follows the same shape; one quirk to
know before writing it: `go vet -json` prints its JSON to **stderr** (grouped
by package), so its `parse()` reads `out.stderr` instead of going through
`load_json_output`.

### Category and severity mapping

Pick categories by what the *student* should learn, not by which tool fired —
the four buckets the UI and dashboard use are `security`, `complexity`,
`bug_risk` and `style` (test failures produce `correctness` findings
separately). Look at how the existing analyzers decide:

- Ruff maps `C9*` codes to complexity, `F8*`/`B*` to bug risk, everything else
  to style, and escalates severity for codes that mean "this will crash".
- ESLint keys off rule names — a `security/` prefix or `no-eval` is security,
  `complexity`/`max-depth` are complexity, `no-undef` etc. are bug risk.

## Step 3 — register the language

In [`analyzers/registry.py`](../backend/src/codeguide/analyzers/registry.py):

```python
from codeguide.analyzers.go_tools import GocycloAnalyzer, GosecAnalyzer

_REGISTRY: dict[str, list[Analyzer]] = {
    "python": [...],
    "javascript": [...],
    "go": [
        GosecAnalyzer(),
        GocycloAnalyzer(),
        SemgrepAnalyzer("go", "/opt/rules/go"),   # if you did step 5
    ],
}
```

`build_plan()` in [`execution/plan.py`](../backend/src/codeguide/execution/plan.py)
picks these up automatically — every registered analyzer's `sandbox_step()`
goes into the plan for submissions in that language.

Also widen the API's language enum in
[`schemas.py`](../backend/src/codeguide/schemas.py), or assignment creation
will reject the new language with a validation error:

```python
Language = Literal["python", "javascript", "go"]
```

## Step 4 — misconception mappings

Findings only reach the instructor dashboard's class-wide aggregation if their
`rule_id` maps to a misconception tag in
[`taxonomy/misconceptions.yaml`](../backend/src/codeguide/taxonomy/misconceptions.yaml).
Unmapped findings still show to the student — they just don't aggregate.

Attach the new tool's rule IDs to *existing* tags where the underlying concept
is the same, and add new tags only for genuinely new concepts:

```yaml
  - tag: hardcoded-secret
    title: Secrets written into source code
    summary: >-
      Passwords and API keys in source end up in version control and every
      copy of the code. Secrets belong in the environment or a vault.
    rules:
      - B105                    # bandit
      - py-hardcoded-password
      - js-hardcoded-secret
      - G101                    # gosec: hardcoded credentials
      - G798                    # gosec: hardcoded credentials (newer id)

  - tag: weak-randomness
    rules:
      # ...existing rules...
      - G404                    # gosec: use of math/rand for security purposes

  - tag: unhandled-error
    title: Ignoring returned errors
    summary: >-
      Go reports failures through return values. Discarding an error means the
      program continues as if the operation succeeded — often far past the
      point where the real problem happened.
    rules:
      - G104                    # gosec: errors unhandled
```

The mapping is deterministic by design — the dashboard never aggregates
LLM-generated tags (see
[`analyzers/misconceptions.py`](../backend/src/codeguide/analyzers/misconceptions.py)).

## Step 5 — semgrep rules (optional)

For teachable patterns the off-the-shelf tools don't cover, add a curated
offline ruleset at `runners/rules/semgrep/go/security.yaml`, mirroring the
[Python one](../runners/rules/semgrep/python/security.yaml). Rules are
vendored into the image (the sandbox has no network, so nothing can be pulled
from the Semgrep registry at scan time):

```yaml
rules:
  - id: go-sqli-sprintf
    languages: [go]
    severity: ERROR
    message: >-
      SQL query built with fmt.Sprintf. Anything the user typed becomes part
      of the SQL command itself (SQL injection). Pass values as query
      parameters instead.
    metadata:
      category: security
      cwe: "CWE-89"
    patterns:
      - pattern-either:
          - pattern: $DB.Query(fmt.Sprintf("...", ...), ...)
          - pattern: $DB.Exec(fmt.Sprintf("...", ...), ...)
```

Then `COPY rules/semgrep/go /opt/rules/go` in the Dockerfile, install semgrep
in the image (see the Node runner for the pattern), instantiate
`SemgrepAnalyzer("go", "/opt/rules/go")` in the registry, and map each rule
`id` in the taxonomy.

## Step 6 — wiring: runner image, harness interpreter

**Runner image setting** — add a field in
[`config.py`](../backend/src/codeguide/config.py) (environment variable:
`CODEGUIDE_RUNNER_IMAGE_GO`):

```python
runner_image_go: str = "coding-learning-ai-guide-runner-go:latest"
```

and extend the map in
[`execution/plan.py`](../backend/src/codeguide/execution/plan.py):

```python
def runner_image(language: str, settings: Settings) -> str:
    return {
        "python": settings.runner_image_python,
        "javascript": settings.runner_image_node,
        "go": settings.runner_image_go,
    }[language]
```

**Harness interpreter** — the in-sandbox harness
([`runners/harness/entrypoint.py`](../runners/harness/entrypoint.py)) runs the
student's entrypoint against each test case via its `INTERPRETERS` map:

```python
INTERPRETERS = {
    "python": [sys.executable],
    "javascript": ["node"],
    "go": ["go", "run"],
}
```

`go run main.go` compiles and runs a single file in one step, which fits the
harness's interpreter-style invocation — this is why the Dockerfile sets
`GOCACHE=/tmp/gocache` (the only writable place). Expect the first test case
of each run to pay the compile cost; keep per-case `timeout_ms` generous.

**Helm** — for Kubernetes deployments, add a `runners.go` value in
[`values.yaml`](../deploy/helm/coding-learning-ai-guide/values.yaml) and a
`CODEGUIDE_RUNNER_IMAGE_GO` env entry in
[`templates/api.yaml`](../deploy/helm/coding-learning-ai-guide/templates/api.yaml),
following the python/node lines exactly.

## Step 7 — prove it works

- **Parser unit tests**: feed captured tool output (including garbage and
  empty output) into `parse()` — see the existing analyzer tests in
  `backend/tests/` for the pattern. `make test`.
- **Integration**: `make runners && make test-integration` runs real sandbox
  containers.
- **End to end**: `make demo`, create a Go assignment via the API (language
  `"go"`, entrypoint `main.go`, a couple of stdin/stdout test cases — see
  [docs/api.md](api.md)), submit something deliberately bad, and check that
  findings, misconception tags and feedback all come back.
