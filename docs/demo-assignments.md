# Demo courses and assignments

`make demo` (or `codeguide seed` directly) seeds two demo courses and then
pushes every sample submission through the **real pipeline**: each one runs in
the actual sandbox, is scanned by the actual analyzers, and gets actual
feedback. Nothing on the resulting dashboard is a hand-written number — the
misconception counts, pass rates and findings you see are what the system
genuinely produced. The content lives in
`backend/src/codeguide/demo_content.py`.

The sample submissions are deliberately varied: some are correct, and the
flawed ones each carry a specific, teachable mistake chosen to light up a
different part of the misconception taxonomy.

## Course 1: Introduction to Programming (Python)

### FizzBuzz

Print 1..n, replacing multiples of 3/5/15 with Fizz/Buzz/FizzBuzz. Teaches
branching, ordering of conditions, and reading a loop.

| Submission | What it demonstrates |
|---|---|
| Correct (2 students) | A clean pass — the analyzers find nothing to flag. |
| Wrong branch order (2 students) | The `% 15` check comes *after* `% 3`, so it is unreachable and 15 prints `Fizz`. It passes the visible test (n=5 has no multiple of 15) but fails the hidden `through-fizzbuzz` test — a nice illustration of why hidden tests exist. Surfaces a **correctness** finding (`test-failure`). |
| Over-complicated (1 student) | A deeply nested `classify()` with duplicated branches and a mutable default argument (`acc=[]`). Surfaces **excessive-complexity** and **mutable-default-argument**. |

### Safe user lookup

Look up a username's role from a small user store — where the username should
be imagined as hostile internet input. Teaches treating input as data.

| Submission | What it demonstrates |
|---|---|
| Correct (2 students) | A plain dictionary lookup — safe by construction. |
| Vulnerable (2 students) | The classic trio: an f-string SQL query (**sql-injection**, Bandit B608), `DB_PASSWORD = "hunter2"` in source (**hardcoded-secret**, B105), and a `pickle.loads` helper (**unsafe-deserialization**, B301). It passes both tests — correctness is not safety. |
| `eval(input())` (1 student) | Executes the user's input as Python. Surfaces **eval-injection** (B307). |

## Course 2: Web Programming Basics (JavaScript)

### Sum the numbers

Read space-separated integers from stdin and print their sum. Teaches parsing
input and JavaScript's comparison pitfalls.

| Submission | What it demonstrates |
|---|---|
| Correct (1 student) | `split` / `map(Number)` / `reduce`. |
| Loose equality (2 students) | Uses `!=` in the loop guard. Surfaces **loose-equality** (`eqeqeq`). |
| `eval` per token (1 student) | Sums the numbers by `eval`-ing each token. Surfaces **eval-injection** (`no-eval`). |

### Build a greeting

Print `Hello, <name>!` — and think about whether the code would be safe on a
web page. Teaches where user text ends up.

| Submission | What it demonstrates |
|---|---|
| Correct (1 student) | A template literal to stdout. |
| Secret + innerHTML (2 students) | A hardcoded `sk-live-…` API key (**hardcoded-secret**) and user text concatenated into `innerHTML` (**xss**). It passes the test — again, correct output with unsafe habits. |

## Why seed it this way

Because the seeder exercises the production code path, the demo doubles as an
end-to-end smoke test: if the sandbox, an analyzer, the taxonomy mapping or
the feedback layer breaks, `make demo` shows it immediately. It also means the
instructor dashboard tells a coherent story out of the box — for example,
**sql-injection** shows up across multiple students on "Safe user lookup",
which is exactly the class-wide pattern the dashboard is built to reveal.
