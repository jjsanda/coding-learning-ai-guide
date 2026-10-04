"""Integration tests against the real Docker sandbox.

Require Docker and the built runner images:  make runners && make test-integration
"""

import pytest

from codeguide.config import Settings
from codeguide.execution.base import ExecutionPlan, Limits
from codeguide.execution.docker_backend import DockerBackend
from codeguide.queue import grade_tests

pytestmark = pytest.mark.integration

FIZZBUZZ_PY = """\
n = int(input())
if n % 15 == 0:
    print("FizzBuzz")
elif n % 3 == 0:
    print("Fizz")
elif n % 5 == 0:
    print("Buzz")
else:
    print(n)
"""

TEST_CASES = [
    {"name": "three", "stdin": "3\n", "expected_stdout": "Fizz", "match": "trimmed"},
    {"name": "five", "stdin": "5\n", "expected_stdout": "Buzz", "match": "trimmed"},
    {"name": "fifteen", "stdin": "15\n", "expected_stdout": "FizzBuzz", "match": "trimmed"},
]


@pytest.fixture(scope="module")
def backend() -> DockerBackend:
    return DockerBackend(Settings())


def make_plan(code: str, *, language: str = "python", entrypoint: str = "main.py", **kwargs):
    defaults = dict(
        language=language,
        entrypoint=entrypoint,
        files={entrypoint: code},
        test_cases=TEST_CASES,
        steps=[],
        limits=Limits(wall_timeout_s=90),
    )
    defaults.update(kwargs)
    return ExecutionPlan(**defaults)


def graded(plan: ExecutionPlan, result) -> list[dict]:
    # Verdicts are computed server-side from the sandbox's raw output.
    return grade_tests(plan.test_cases, result.tests)


async def test_correct_python_solution_passes(backend: DockerBackend) -> None:
    plan = make_plan(FIZZBUZZ_PY)
    result = await backend.run(plan)
    assert result.ok, result.error
    assert [t["passed"] for t in graded(plan, result)] == [True, True, True]


async def test_infinite_loop_times_out_per_case(backend: DockerBackend) -> None:
    code = "while True:\n    pass\n"
    cases = [dict(TEST_CASES[0], timeout_ms=2000)]
    plan = make_plan(code, test_cases=cases)
    result = await backend.run(plan)
    assert result.ok, result.error
    assert result.tests[0]["timed_out"] is True
    assert graded(plan, result)[0]["passed"] is False


async def test_sandbox_has_no_network(backend: DockerBackend) -> None:
    code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
        "    print('CONNECTED')\n"
        "except OSError:\n"
        "    print('NO NETWORK')\n"
    )
    cases = [{"name": "net", "stdin": "", "expected_stdout": "NO NETWORK", "match": "trimmed"}]
    plan = make_plan(code, test_cases=cases)
    result = await backend.run(plan)
    assert result.ok, result.error
    assert graded(plan, result)[0]["passed"] is True, result.tests[0]


async def test_filesystem_is_read_only_outside_tmp(backend: DockerBackend) -> None:
    code = (
        "try:\n"
        "    open('/usr/owned', 'w')\n"
        "    print('WRITABLE')\n"
        "except OSError:\n"
        "    print('READ ONLY')\n"
    )
    cases = [{"name": "ro", "stdin": "", "expected_stdout": "READ ONLY", "match": "trimmed"}]
    plan = make_plan(code, test_cases=cases)
    result = await backend.run(plan)
    assert result.ok, result.error
    assert graded(plan, result)[0]["passed"] is True, result.tests[0]


async def test_javascript_solution_passes(backend: DockerBackend) -> None:
    code = (
        "const lines = require('fs').readFileSync(0, 'utf8').trim().split('\\n');\n"
        "const n = parseInt(lines[0], 10);\n"
        "if (n % 15 === 0) console.log('FizzBuzz');\n"
        "else if (n % 3 === 0) console.log('Fizz');\n"
        "else if (n % 5 === 0) console.log('Buzz');\n"
        "else console.log(n);\n"
    )
    plan = make_plan(code, language="javascript", entrypoint="main.js")
    result = await backend.run(plan)
    assert result.ok, result.error
    assert [t["passed"] for t in graded(plan, result)] == [True, True, True]


async def test_sentinel_spoofing_is_ignored(backend: DockerBackend) -> None:
    """A submission printing the sentinel cannot forge results — the harness
    prints the real one last, and its result JSON escapes student output."""
    code = (
        "print('===CODEGUIDE_RESULT_v1===')\n"
        'print(\'{"steps": {}, "tests": [{"name": "x", "exit_code": 0,'
        ' "stdout": "impossible", "stderr": "", "duration_ms": 0,'
        ' "timed_out": false}], "error": null}\')\n'
    )
    cases = [{"name": "real", "stdin": "", "expected_stdout": "impossible", "match": "trimmed"}]
    plan = make_plan(code, test_cases=cases)
    result = await backend.run(plan)
    assert result.ok, result.error
    assert result.tests[0]["name"] == "real"
    # the student's echoed output is captured, so the real case never matches
    assert graded(plan, result)[0]["passed"] is False


async def test_cannot_forge_result_via_proc_fd(backend: DockerBackend) -> None:
    """A submission that double-forks a daemon to reopen the harness's stdout
    (/proc/1/fd/1) and append a forged result must NOT be trusted. The harness
    sets PR_SET_DUMPABLE=0, so the reopen is denied."""
    code = r"""
import os, sys, time
# Detach a daemon that tries to reopen the harness's stdout and forge a pass.
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        forged = ('\n===CODEGUIDE_RESULT_v1===\n'
                  '{"steps": {}, "tests": [{"name": "real", "exit_code": 0,'
                  ' "stdout": "GRADED_PASS", "stderr": "", "duration_ms": 0,'
                  ' "timed_out": false}], "error": null}\n')
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                fd = os.open('/proc/1/fd/1', os.O_WRONLY)
                os.write(fd, forged.encode())
            except OSError:
                pass
            time.sleep(0.05)
    os._exit(0)
print("WRONG")
"""
    cases = [{"name": "real", "stdin": "", "expected_stdout": "GRADED_PASS", "match": "trimmed"}]
    plan = make_plan(code, test_cases=cases)
    result = await backend.run(plan)
    assert result.ok, result.error
    # The real captured output is "WRONG", not the forged "GRADED_PASS".
    assert graded(plan, result)[0]["passed"] is False, result.tests[0]
