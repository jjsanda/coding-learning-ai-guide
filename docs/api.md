# HTTP API walkthrough

Everything the web UI does goes through this API, so anything below can be
scripted — course setup, bulk assignment creation, CI-style smoke tests
([scripts/smoke.sh](../scripts/smoke.sh) is exactly this walkthrough in bash).

- **Base path:** `/api/v1`
- **Interactive docs:** <http://localhost:8000/api/docs> (Swagger UI; raw
  OpenAPI at `/api/openapi.json`)
- **Health:** `GET /healthz` (liveness) and `GET /readyz` (readiness — checks
  the database; returns 503 when it can't)

The examples assume the Compose demo (`make demo`) with the API on
`http://localhost:8000`. The web container also proxies the API, so
`http://localhost:8080/api/v1/...` works identically. `jq` is used for
readability but isn't required.

```bash
BASE=http://localhost:8000/api/v1
```

## Authentication

Two kinds of principals, both authenticated with a bearer token in the
`Authorization` header:

| Principal | Token prefix | How you get it |
|---|---|---|
| **Instructor** | `cgi_...` | The `create-instructor` CLI command (below) |
| **Student** | `cgs_...` | Returned by `POST /auth/join` |

Tokens are random secrets shown exactly once; only their SHA-256 hashes are
stored. Send them as:

```
Authorization: Bearer cgi_...
```

Missing/invalid tokens get `401`. Resources you don't own get `404` (not
`403`) so IDs aren't confirmable by probing.

### A quick no-auth sanity check

```bash
curl -s $BASE/meta | jq
```

```json
{
  "version": "0.1.0",
  "execution_backend": "docker",
  "feedback_provider": "template"
}
```

## 1. Create an instructor (CLI)

There is no self-service signup endpoint — instructor accounts are created
administratively with the CLI, inside the running API container:

```bash
docker compose exec -T api python -m codeguide.cli create-instructor \
  --name "Ada Lovelace" --email ada@example.edu
```

```
Instructor created. The API token below is shown ONCE — store it now:

  cgi_Zn4t8sXo0hV1kq2yD7wLxNBrmPfceJgAiu96TERC3aM

Use it as:  curl -H "Authorization: Bearer <token>" ...
```

(On Kubernetes: `kubectl exec <api-pod> -- python -m codeguide.cli
create-instructor ...`. The `make demo` seed also prints a ready-made
instructor token.)

```bash
INSTRUCTOR_TOKEN=cgi_Zn4t8sXo0hV1kq2yD7wLxNBrmPfceJgAiu96TERC3aM
```

## 2. Create a course

```bash
curl -s -X POST $BASE/courses \
  -H "Authorization: Bearer $INSTRUCTOR_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title": "Intro to Programming — Fall 2026"}' | jq
```

```json
{
  "id": "4c2f0a4be2e94c9b8f6d1f2f9d3f7a10",
  "title": "Intro to Programming — Fall 2026",
  "join_code": "X7KPQ2M9",
  "created_at": "2026-07-16T09:14:02Z"
}
```

The `join_code` is what students use to enroll — it's only visible to the
course's instructor. `GET /courses` lists your courses (this is how the smoke
test discovers a join code from an instructor token).

```bash
COURSE_ID=4c2f0a4be2e94c9b8f6d1f2f9d3f7a10
```

## 3. Create an assignment

An assignment fixes the language, the entrypoint file the sandbox will run,
and the I/O test cases. Each test case feeds `stdin` to the student's program
and compares its stdout to `expected_stdout` (`match` is `"trimmed"` by
default — trailing whitespace ignored — or `"exact"`). Cases with
`"visible": false` run and count, but students see only their names.

```bash
curl -s -X POST $BASE/courses/$COURSE_ID/assignments \
  -H "Authorization: Bearer $INSTRUCTOR_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Count to N",
    "description_md": "Read an integer **N** from stdin and print the numbers 1..N, one per line.",
    "language": "python",
    "entrypoint": "main.py",
    "test_cases": [
      {"name": "counts to 3", "stdin": "3\n", "expected_stdout": "1\n2\n3\n"},
      {"name": "counts to 1", "stdin": "1\n", "expected_stdout": "1\n"},
      {"name": "hidden: large N", "stdin": "50\n",
       "expected_stdout": "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12\n13\n14\n15\n16\n17\n18\n19\n20\n21\n22\n23\n24\n25\n26\n27\n28\n29\n30\n31\n32\n33\n34\n35\n36\n37\n38\n39\n40\n41\n42\n43\n44\n45\n46\n47\n48\n49\n50\n",
       "timeout_ms": 5000, "visible": false}
    ]
  }' | jq
```

```json
{
  "id": "9e1d3b6f75a24d0c8b2e4f1a6c0d9e7b",
  "course_id": "4c2f0a4be2e94c9b8f6d1f2f9d3f7a10",
  "title": "Count to N",
  "description_md": "Read an integer **N** from stdin and print the numbers 1..N, one per line.",
  "language": "python",
  "entrypoint": "main.py",
  "test_cases": [
    {"name": "counts to 3", "stdin": "3\n", "expected_stdout": "1\n2\n3\n", "visible": true},
    {"name": "counts to 1", "stdin": "1\n", "expected_stdout": "1\n", "visible": true},
    {"name": "hidden: large N", "stdin": "50\n", "expected_stdout": "1\n...\n50\n", "visible": false}
  ],
  "created_at": "2026-07-16T09:15:30Z"
}
```

Notes:

- `language` is `"python"` or `"javascript"`.
- `timeout_ms` per test case: 100–30 000, default 5000.
- The creator sees full test cases; when a *student* fetches
  `GET /assignments/{id}`, hidden cases come back as
  `{"name": "hidden: large N", "visible": false}` with no stdin/expected
  output.

```bash
ASSIGNMENT_ID=9e1d3b6f75a24d0c8b2e4f1a6c0d9e7b
```

## 4. Join as a student

Students don't register — they exchange a join code and a display name for a
student token:

```bash
curl -s -X POST $BASE/auth/join \
  -H 'Content-Type: application/json' \
  -d '{"join_code": "X7KPQ2M9", "display_name": "Sam Student"}' | jq
```

```json
{
  "student_id": "b8a1f4c2e6d94b3a9c5e7f0d2a4b6c8e",
  "student_token": "cgs_Qw3rTy5uIo7pAs9dFg1hJk2lZx4cVb6nMq8eRt0yUi5oP",
  "course": {
    "id": "4c2f0a4be2e94c9b8f6d1f2f9d3f7a10",
    "title": "Intro to Programming — Fall 2026"
  }
}
```

An unknown join code returns `404`. Store the token:

```bash
STUDENT_TOKEN=cgs_Qw3rTy5uIo7pAs9dFg1hJk2lZx4cVb6nMq8eRt0yUi5oP
```

Students list their course's assignments with
`GET /courses/{course_id}/assignments` (summaries) and fetch one with
`GET /assignments/{id}`.

## 5. Submit code

A submission is a list of files; it must include the assignment's entrypoint.
This one has a deliberate bug (counts from 0) and two teachable security
findings:

```bash
curl -s -X POST $BASE/assignments/$ASSIGNMENT_ID/submissions \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "files": [
      {
        "path": "main.py",
        "content": "import pickle\npassword = \"hunter2\"\nn = int(input())\nfor i in range(n):\n    print(i)\n"
      }
    ]
  }' | jq
```

The API validates and queues it, returning `202 Accepted` immediately:

```json
{
  "submission_id": "7f3e9a1c5b8d4e2f0a6c8b4d2e0f9a7c",
  "status": "queued"
}
```

Guardrails you may hit:

- `413` — more than 20 files, or more than 200 000 bytes total,
- `422` — unsafe/duplicate file paths, or the entrypoint file is missing,
- `429` — more than 6 submissions per minute per student.

```bash
SUBMISSION_ID=7f3e9a1c5b8d4e2f0a6c8b4d2e0f9a7c
```

## 6. Poll the submission

Processing is asynchronous: the sandbox run, analyzers and feedback generation
happen in the background. Poll until `status` is terminal:

```bash
curl -s $BASE/submissions/$SUBMISSION_ID \
  -H "Authorization: Bearer $STUDENT_TOKEN" | jq
```

`status` walks `queued → running → analyzing → feedback → completed` (or
`failed`, with `error` set — infrastructure failure, never "the student's code
was wrong"). When completed:

```json
{
  "id": "7f3e9a1c5b8d4e2f0a6c8b4d2e0f9a7c",
  "assignment_id": "9e1d3b6f75a24d0c8b2e4f1a6c0d9e7b",
  "student_id": "b8a1f4c2e6d94b3a9c5e7f0d2a4b6c8e",
  "status": "completed",
  "error": null,
  "created_at": "2026-07-16T09:21:44Z",
  "started_at": "2026-07-16T09:21:45Z",
  "completed_at": "2026-07-16T09:21:53Z",
  "test_results": [
    {"name": "counts to 3", "passed": false, "expected": "1\n2\n3\n",
     "actual": "0\n1\n2\n", "duration_ms": 41, "timed_out": false},
    {"name": "counts to 1", "passed": false, "expected": "1\n",
     "actual": "0\n", "duration_ms": 38, "timed_out": false},
    {"name": "hidden: large N", "passed": false, "expected": "1\n...\n50\n",
     "actual": "0\n...\n49\n", "duration_ms": 45, "timed_out": false}
  ],
  "findings": [
    {
      "id": 301,
      "analyzer": "ruff",
      "rule_id": "F401",
      "severity": "info",
      "category": "style",
      "file": "main.py",
      "line_start": 1,
      "line_end": 1,
      "message": "`pickle` imported but unused",
      "snippet": "import pickle",
      "misconception_tag": null
    },
    {
      "id": 302,
      "analyzer": "bandit",
      "rule_id": "B105",
      "severity": "warning",
      "category": "security",
      "file": "main.py",
      "line_start": 2,
      "line_end": 2,
      "message": "Possible hardcoded password: 'hunter2'",
      "snippet": "password = \"hunter2\"",
      "misconception_tag": "hardcoded-secret"
    }
  ]
}
```

Every finding is deterministic analyzer output: the exact tool, rule ID, file
and lines. `misconception_tag` is the deterministic rule-to-concept mapping
that the instructor dashboard aggregates.

## 7. Fetch the feedback

```bash
curl -s $BASE/submissions/$SUBMISSION_ID/feedback \
  -H "Authorization: Bearer $STUDENT_TOKEN" | jq
```

Returns `404` until feedback has been generated (i.e. while the submission is
still in flight). Then:

```json
{
  "submission_id": "7f3e9a1c5b8d4e2f0a6c8b4d2e0f9a7c",
  "provider": "template",
  "model": null,
  "summary_md": "Your program runs, but all 3 tests failed and the analyzers flagged 2 issues worth a look. Start with the failing tests — the pattern in what's printed is a big hint.",
  "items": [
    {
      "finding_ref": 302,
      "explanation_md": "The password on line 2 is written directly into the source code. Anyone who can read the code — including version control history — can read the secret.",
      "hint_md": "Where could a program get a secret from at runtime instead of having it typed into the file?",
      "misconception_tag": "hardcoded-secret"
    }
  ],
  "next_steps": [
    "Compare the expected and actual output of 'counts to 3' line by line.",
    "Check what range(n) actually produces for its first and last value."
  ],
  "cached": true,
  "created_at": "2026-07-16T09:21:53Z"
}
```

`provider` and `model` tell you who wrote the prose: `template` (built-in,
no API key), or `anthropic` / `openai` / `ollama` with the model name. Each
item's `finding_ref` points back at a finding ID from step 6 — explanations
are only ever attached to real findings.

## 8. Instructor insights

Class-wide aggregation over deterministic findings and test results
(instructor-only, own courses only):

```bash
curl -s $BASE/courses/$COURSE_ID/insights \
  -H "Authorization: Bearer $INSTRUCTOR_TOKEN" | jq
```

```json
{
  "course_id": "4c2f0a4be2e94c9b8f6d1f2f9d3f7a10",
  "total_submissions": 42,
  "total_students": 17,
  "misconceptions": [
    {"misconception_tag": "hardcoded-secret", "count": 11, "affected_students": 8},
    {"misconception_tag": "sql-injection", "count": 6, "affected_students": 5},
    {"misconception_tag": "excessive-complexity", "count": 4, "affected_students": 3}
  ],
  "pass_rates": [
    {"assignment_id": "9e1d3b6f75a24d0c8b2e4f1a6c0d9e7b", "title": "Count to N",
     "submissions": 42, "pass_rate": 0.62}
  ],
  "findings_by_category": [
    {"category": "style", "count": 58},
    {"category": "security", "count": 21},
    {"category": "complexity", "count": 9},
    {"category": "bug_risk", "count": 7}
  ],
  "submissions_per_day": [
    {"day": "2026-07-15", "count": 18},
    {"day": "2026-07-16", "count": 24}
  ]
}
```

`affected_students` counts distinct students, so one student's repeated
mistake doesn't look like a class-wide trend. Instructors can also page
through raw submissions with
`GET /courses/{course_id}/submissions?assignment_id=...&limit=100&offset=0`,
and fetch any of their courses' submissions/feedback by ID using the same
endpoints as students.

## Endpoint summary

| Method & path | Who | Purpose |
|---|---|---|
| `GET /meta` | anyone | Version, execution backend, active feedback provider |
| `POST /auth/join` | anyone with a join code | Enroll; returns a student token |
| `POST /courses` | instructor | Create a course |
| `GET /courses` | instructor | List own courses (includes join codes) |
| `GET /courses/{id}` | instructor | One course |
| `POST /courses/{id}/assignments` | instructor | Create an assignment with test cases |
| `GET /courses/{id}/assignments` | student or instructor | List assignments |
| `GET /assignments/{id}` | student or instructor | Assignment detail (students: hidden cases redacted) |
| `POST /assignments/{id}/submissions` | student | Submit files; returns `202` + submission ID |
| `GET /submissions/{id}` | owner student or course instructor | Status, test results, findings |
| `GET /submissions/{id}/feedback` | owner student or course instructor | Generated feedback (`404` until ready) |
| `GET /courses/{id}/submissions` | instructor | Page through a course's submissions |
| `GET /courses/{id}/insights` | instructor | Class-wide aggregates |

Full request/response schemas: <http://localhost:8000/api/docs>.
