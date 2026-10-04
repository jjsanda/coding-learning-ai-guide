#!/usr/bin/env bash
# End-to-end smoke test: join a course, submit code, poll until the sandbox
# run completes, and assert that feedback comes back. Exercises the whole
# pipeline through the public HTTP API.
#
# Usage: scripts/smoke.sh [BASE_URL] [JOIN_CODE]
#   BASE_URL defaults to http://localhost:8080 (the web proxy).
#   JOIN_CODE defaults to the first course's code, discovered via the API
#   when an instructor token is available in $CODEGUIDE_INSTRUCTOR_TOKEN.
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
JOIN_CODE="${2:-${CODEGUIDE_JOIN_CODE:-}}"

fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }
json() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

echo "→ checking API metadata"
curl -fsS "$BASE_URL/api/v1/meta" | json "['version']" >/dev/null || fail "meta endpoint unreachable"

if [ -z "$JOIN_CODE" ]; then
  [ -n "${CODEGUIDE_INSTRUCTOR_TOKEN:-}" ] || fail "provide a JOIN_CODE argument or CODEGUIDE_INSTRUCTOR_TOKEN"
  JOIN_CODE=$(curl -fsS "$BASE_URL/api/v1/courses" \
    -H "Authorization: Bearer $CODEGUIDE_INSTRUCTOR_TOKEN" | json "[0]['join_code']")
fi
echo "→ joining course $JOIN_CODE"

STUDENT=$(curl -fsS -X POST "$BASE_URL/api/v1/auth/join" \
  -H 'Content-Type: application/json' \
  -d "{\"join_code\":\"$JOIN_CODE\",\"display_name\":\"Smoke Test\"}")
TOKEN=$(echo "$STUDENT" | json "['student_token']")
COURSE_ID=$(echo "$STUDENT" | json "['course']['id']")

ASSIGNMENT_ID=$(curl -fsS "$BASE_URL/api/v1/courses/$COURSE_ID/assignments" \
  -H "Authorization: Bearer $TOKEN" | json "[0]['id']")
echo "→ submitting to assignment $ASSIGNMENT_ID"

read -r -d '' PAYLOAD <<'JSON' || true
{"files":[{"path":"main.py","content":"import pickle\npassword = \"hunter2\"\nn = int(input())\ncur = None\nfor i in range(1, n + 1):\n    print(i)\n"}]}
JSON

SUBMISSION_ID=$(curl -fsS -X POST "$BASE_URL/api/v1/assignments/$ASSIGNMENT_ID/submissions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "$PAYLOAD" | json "['submission_id']")

echo "→ polling submission $SUBMISSION_ID"
STATUS=""
for _ in $(seq 1 60); do
  STATUS=$(curl -fsS "$BASE_URL/api/v1/submissions/$SUBMISSION_ID" \
    -H "Authorization: Bearer $TOKEN" | json "['status']")
  case "$STATUS" in
    completed) break ;;
    failed) fail "submission failed" ;;
  esac
  sleep 2
done
[ "$STATUS" = "completed" ] || fail "submission did not complete (status: $STATUS)"

FEEDBACK=$(curl -fsS "$BASE_URL/api/v1/submissions/$SUBMISSION_ID/feedback" \
  -H "Authorization: Bearer $TOKEN")
ITEMS=$(echo "$FEEDBACK" | json "['items'].__len__()")
[ "$ITEMS" -gt 0 ] || fail "feedback had no items"

echo "SMOKE PASS: submission completed with $ITEMS feedback item(s)"
