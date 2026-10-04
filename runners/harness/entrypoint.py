#!/usr/bin/env python3
"""In-sandbox harness: runs analyzers and I/O test cases over a submission.

The orchestrator injects student files and a ``plan.json`` into ``/work`` and
starts this script as the container command. The sandbox has no network; the
single channel back to the orchestrator is container stdout, where the result
JSON is printed after a sentinel line.

Analyzer steps run *before* the student's code so that nothing the code does
at runtime can alter what the analyzers see. The harness always exits 0 —
a non-zero exit means the sandbox infrastructure itself broke, never the
student's code.
"""

import ctypes
import gzip
import json
import os
import subprocess
import sys
import time

SENTINEL = "===CODEGUIDE_RESULT_v1==="
HARNESS_VERSION = 1
MAX_STREAM_BYTES = 256 * 1024
WORK_DIR = os.environ.get("CODEGUIDE_WORK_DIR", "/work")


SRC_DIR = os.environ.get("CODEGUIDE_SRC_DIR", "/work-src")

_PR_SET_DUMPABLE = 4


def harden() -> None:
    """Make this process non-dumpable before any student code runs.

    The harness is PID 1 and runs as the same unprivileged user as the
    student's code. Without this, a submission could reopen the harness's own
    stdout via ``/proc/1/fd/1`` (or read ``/proc/1/{mem,environ}``) and forge
    the result JSON. Setting PR_SET_DUMPABLE=0 makes those procfs entries
    owned by root, so a same-uid process can no longer reach them. The
    orchestrator therefore remains the sole author of what it reads back.
    """
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0)
    except Exception:  # noqa: BLE001 - best effort; the run must still proceed
        pass


def _write_into_work(rel_path: str, content: str) -> None:
    # Paths are validated upstream, but never write outside WORK_DIR anyway.
    target = os.path.realpath(os.path.join(WORK_DIR, rel_path))
    if not target.startswith(os.path.realpath(WORK_DIR) + os.sep):
        raise ValueError(f"path escapes work dir: {rel_path!r}")
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(target, "w") as fh:
        fh.write(content)


def materialize_payload() -> None:
    """Populate WORK_DIR with the submission and plan.json.

    Two delivery channels, matching the two execution backends:

    * **Docker backend** streams a gzipped JSON payload over stdin (the
      container rootfs is read-only and WORK_DIR is a tmpfs).
    * **Kubernetes backend** mounts a ConfigMap read-only at ``/work-src``;
      we copy its entries into the writable WORK_DIR.

    If neither is present the files are assumed to already be in WORK_DIR
    (the local test backend writes them there directly).
    """
    if not sys.stdin.isatty():
        raw = sys.stdin.buffer.read()
        if raw:
            doc = json.loads(gzip.decompress(raw))
            for rel_path, content in doc["files"].items():
                _write_into_work(rel_path, content)
            return

    if os.path.isdir(SRC_DIR):
        for entry in os.listdir(SRC_DIR):
            src = os.path.join(SRC_DIR, entry)
            if os.path.isfile(src):
                with open(src) as fh:
                    _write_into_work(entry, fh.read())

INTERPRETERS = {
    "python": [sys.executable],
    "javascript": ["node"],
}


def _truncate(text: str) -> str:
    encoded = text.encode(errors="replace")
    if len(encoded) <= MAX_STREAM_BYTES:
        return text
    return encoded[:MAX_STREAM_BYTES].decode(errors="replace") + "\n[output truncated]"


def run_step(step: dict) -> dict:
    """Run one analyzer command and capture its raw output for the orchestrator."""
    started = time.monotonic()
    timeout_s = step.get("timeout_s", 60)
    try:
        proc = subprocess.run(  # noqa: S603 - argv comes from the orchestrator, not the student
            step["cmd"],
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": _truncate(proc.stdout),
            "stderr": _truncate(proc.stderr),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": -1,
            "stdout": _truncate(exc.stdout or ""),
            "stderr": _truncate(exc.stderr or ""),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": True,
        }
    except FileNotFoundError as exc:
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": str(exc),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": False,
        }


def run_test_case(language: str, entrypoint: str, case: dict) -> dict:
    """Run one case and report the program's actual output.

    The harness never decides pass/fail and never sees the expected output:
    the orchestrator compares the captured ``stdout`` against the trusted,
    server-side expected value. This keeps the verdict out of the sandbox
    (untrusted) entirely, and means hidden test cases' expected outputs are
    never shipped into a place the student's program could read.
    """
    argv = INTERPRETERS[language] + [entrypoint]
    timeout_s = case.get("timeout_ms", 5000) / 1000
    started = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603
            argv,
            cwd=WORK_DIR,
            input=case.get("stdin", ""),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "name": case["name"],
            "exit_code": proc.returncode,
            "stdout": _truncate(proc.stdout),
            "stderr": _truncate(proc.stderr),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": case["name"],
            "exit_code": -1,
            "stdout": _truncate(str(exc.stdout or "")),
            "stderr": _truncate(str(exc.stderr or "")),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": True,
        }


def main() -> int:
    result = {
        "harness_version": HARNESS_VERSION,
        "steps": {},
        "tests": [],
        "error": None,
    }
    try:
        harden()
        materialize_payload()
        with open(os.path.join(WORK_DIR, "plan.json")) as fh:
            plan = json.load(fh)

        language = plan["language"]
        if language not in INTERPRETERS:
            raise ValueError(f"unsupported language: {language!r}")

        # 1. Static analysis first, on the pristine submission.
        for step in plan.get("steps", []):
            result["steps"][step["id"]] = run_step(step)

        # 2. Then the student's program against the instructor's test cases.
        for case in plan.get("test_cases", []):
            result["tests"].append(run_test_case(language, plan["entrypoint"], case))
    except Exception as exc:  # noqa: BLE001 - report, never crash the channel
        result["error"] = f"{type(exc).__name__}: {exc}"

    print(SENTINEL)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
