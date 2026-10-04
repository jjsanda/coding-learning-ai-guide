"""Demo course content: assignments plus a spread of realistic student
submissions that exercise the full analysis + feedback pipeline.

Kept in one module so ``codeguide.cli seed`` produces a dashboard with
genuine, varied data rather than hand-written numbers.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DemoSubmission:
    student: str
    files: dict[str, str]


@dataclass
class DemoAssignment:
    title: str
    language: str
    entrypoint: str
    description_md: str
    test_cases: list[dict[str, Any]]
    submissions: list[DemoSubmission] = field(default_factory=list)


@dataclass
class DemoCourse:
    title: str
    assignments: list[DemoAssignment]


# --- Python: FizzBuzz --------------------------------------------------------

_FIZZBUZZ_DESC = """\
## FizzBuzz

Read a single integer `n` from standard input and print the numbers from 1 to
`n`, one per line, with two rules:

- multiples of 3 → print `Fizz`
- multiples of 5 → print `Buzz`
- multiples of both → print `FizzBuzz`
"""

_FIZZBUZZ_TESTS = [
    {"name": "small", "stdin": "5\n", "expected_stdout": "1\n2\nFizz\n4\nBuzz", "visible": True},
    {
        "name": "through-fizzbuzz",
        "stdin": "15\n",
        "expected_stdout": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz",
        "visible": False,
    },
]

_FIZZBUZZ_CORRECT = """\
n = int(input())
for i in range(1, n + 1):
    if i % 15 == 0:
        print("FizzBuzz")
    elif i % 3 == 0:
        print("Fizz")
    elif i % 5 == 0:
        print("Buzz")
    else:
        print(i)
"""

_FIZZBUZZ_WRONG_ORDER = """\
n = int(input())
for i in range(1, n + 1):
    if i % 3 == 0:
        print("Fizz")
    elif i % 5 == 0:
        print("Buzz")
    elif i % 15 == 0:
        print("FizzBuzz")
    else:
        print(i)
"""

_FIZZBUZZ_COMPLEX = """\
def classify(i, acc=[]):
    acc.append(i)
    if i % 3 == 0:
        if i % 5 == 0:
            return "FizzBuzz"
        else:
            return "Fizz"
    else:
        if i % 5 == 0:
            return "Buzz"
        else:
            if i % 2 == 0:
                return str(i)
            else:
                return str(i)

n = int(input())
for i in range(1, n + 1):
    print(classify(i))
"""

# --- Python: user lookup (security-heavy) ------------------------------------

_LOOKUP_DESC = """\
## Look up a user

You're given a small in-memory list of users. Read a username from standard
input and print that user's role, or `unknown` if there is no such user.

This assignment is about doing the lookup **safely** — imagine the username
came from the internet.
"""

_LOOKUP_TESTS = [
    {"name": "known", "stdin": "ada\n", "expected_stdout": "admin", "visible": True},
    {"name": "unknown", "stdin": "eve\n", "expected_stdout": "unknown", "visible": True},
]

_LOOKUP_CORRECT = """\
USERS = {"ada": "admin", "grace": "user"}
name = input().strip()
print(USERS.get(name, "unknown"))
"""

_LOOKUP_VULNERABLE = """\
import sqlite3
import pickle

DB_PASSWORD = "hunter2"

def load_cache(blob):
    return pickle.loads(blob)

def lookup(name):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (name TEXT, role TEXT)")
    cur.execute("INSERT INTO users VALUES ('ada', 'admin'), ('grace', 'user')")
    cur.execute(f"SELECT role FROM users WHERE name = '{name}'")
    row = cur.fetchone()
    return row[0] if row else "unknown"

name = input().strip()
print(lookup(name))
"""

_LOOKUP_EVAL = """\
USERS = {"ada": "admin", "grace": "user"}
name = eval(input())
print(USERS.get(name, "unknown"))
"""

# --- JavaScript: sum of a list -----------------------------------------------

_SUM_DESC = """\
## Sum the numbers

Read a single line of space-separated integers from standard input and print
their sum.
"""

_SUM_TESTS = [
    {"name": "basic", "stdin": "1 2 3 4\n", "expected_stdout": "10", "visible": True},
    {"name": "single", "stdin": "42\n", "expected_stdout": "42", "visible": True},
]

_SUM_CORRECT = """\
const line = require('fs').readFileSync(0, 'utf8').trim();
const total = line.split(/\\s+/).map(Number).reduce((a, b) => a + b, 0);
console.log(total);
"""

_SUM_LOOSE_EQ = """\
const line = require('fs').readFileSync(0, 'utf8').trim();
const parts = line.split(' ');
var total = 0;
for (var i = 0; i < parts.length; i++) {
  if (parts[i] != '') {
    total += parseInt(parts[i]);
  }
}
console.log(total);
"""

_SUM_EVAL = """\
const line = require('fs').readFileSync(0, 'utf8').trim();
const nums = line.split(' ');
let total = 0;
for (const n of nums) {
  total += eval(n);
}
console.log(total);
"""

# --- JavaScript: greeting builder (XSS-ish / secret) -------------------------

_GREET_DESC = """\
## Build a greeting

Read a name from standard input and print `Hello, <name>!`.

Think about where the name ends up and whether any of this code would be safe
if it ran on a web page.
"""

_GREET_TESTS = [
    {"name": "basic", "stdin": "Ada\n", "expected_stdout": "Hello, Ada!", "visible": True},
]

_GREET_CORRECT = """\
const name = require('fs').readFileSync(0, 'utf8').trim();
console.log(`Hello, ${name}!`);
"""

_GREET_SECRET = """\
const apiKey = "sk-live-3f9a2b7c1d8e4f6a";
const name = require('fs').readFileSync(0, 'utf8').trim();
const el = { innerHTML: '' };
el.innerHTML = "Hello, " + name + "!";
console.log(`Hello, ${name}!`);
"""


def demo_courses() -> list[DemoCourse]:
    intro = DemoCourse(
        title="Introduction to Programming",
        assignments=[
            DemoAssignment(
                title="FizzBuzz",
                language="python",
                entrypoint="main.py",
                description_md=_FIZZBUZZ_DESC,
                test_cases=_FIZZBUZZ_TESTS,
                submissions=[
                    DemoSubmission("Ada Lovelace", {"main.py": _FIZZBUZZ_CORRECT}),
                    DemoSubmission("Grace Hopper", {"main.py": _FIZZBUZZ_CORRECT}),
                    DemoSubmission("Alan Turing", {"main.py": _FIZZBUZZ_WRONG_ORDER}),
                    DemoSubmission("Katherine Johnson", {"main.py": _FIZZBUZZ_WRONG_ORDER}),
                    DemoSubmission("Edsger Dijkstra", {"main.py": _FIZZBUZZ_COMPLEX}),
                ],
            ),
            DemoAssignment(
                title="Safe user lookup",
                language="python",
                entrypoint="main.py",
                description_md=_LOOKUP_DESC,
                test_cases=_LOOKUP_TESTS,
                submissions=[
                    DemoSubmission("Ada Lovelace", {"main.py": _LOOKUP_CORRECT}),
                    DemoSubmission("Alan Turing", {"main.py": _LOOKUP_VULNERABLE}),
                    DemoSubmission("Katherine Johnson", {"main.py": _LOOKUP_VULNERABLE}),
                    DemoSubmission("Grace Hopper", {"main.py": _LOOKUP_EVAL}),
                    DemoSubmission("Edsger Dijkstra", {"main.py": _LOOKUP_CORRECT}),
                ],
            ),
        ],
    )

    web = DemoCourse(
        title="Web Programming Basics",
        assignments=[
            DemoAssignment(
                title="Sum the numbers",
                language="javascript",
                entrypoint="main.js",
                description_md=_SUM_DESC,
                test_cases=_SUM_TESTS,
                submissions=[
                    DemoSubmission("Radia Perlman", {"main.js": _SUM_CORRECT}),
                    DemoSubmission("Barbara Liskov", {"main.js": _SUM_LOOSE_EQ}),
                    DemoSubmission("Margaret Hamilton", {"main.js": _SUM_LOOSE_EQ}),
                    DemoSubmission("Guido van Rossum", {"main.js": _SUM_EVAL}),
                ],
            ),
            DemoAssignment(
                title="Build a greeting",
                language="javascript",
                entrypoint="main.js",
                description_md=_GREET_DESC,
                test_cases=_GREET_TESTS,
                submissions=[
                    DemoSubmission("Radia Perlman", {"main.js": _GREET_CORRECT}),
                    DemoSubmission("Barbara Liskov", {"main.js": _GREET_SECRET}),
                    DemoSubmission("Margaret Hamilton", {"main.js": _GREET_SECRET}),
                ],
            ),
        ],
    )

    return [intro, web]
