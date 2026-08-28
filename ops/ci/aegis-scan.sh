#!/usr/bin/env sh
#
# Launch an Aegis scan from any CI system and fail the build on blocking
# findings.
#
# The GitHub App handles GitHub natively (check runs, PR comments, the
# new-findings-only gate). This script is for everywhere else — GitLab CI,
# Jenkins, Buildkite, CircleCI, a cron box — and needs only an API token and
# curl.
#
# Usage:
#   AEGIS_TOKEN=aeg_...  AEGIS_TARGET_ID=<uuid>  ./aegis-scan.sh
#
# Environment:
#   AEGIS_TOKEN      required. An API token from Team -> API tokens.
#   AEGIS_TARGET_ID  required. The target to scan (copy it from its URL).
#   AEGIS_API        optional. Defaults to https://api.aegis.security/api/v1
#   AEGIS_ORG        optional. Slug or id, when the token should act in a
#                    different organization than its own.
#   AEGIS_MODE       optional. quick (default) | standard | deep
#   AEGIS_FAIL_ON    optional. Comma-separated severities that fail the build.
#                    Defaults to critical,high. Set to "" to never fail.
#   AEGIS_TIMEOUT    optional. Seconds to wait for the scan. Default 3600.
#   AEGIS_POLL       optional. Seconds between status checks. Default 20.
#
# Exit codes:
#   0  scan completed and nothing blocking was found
#   1  blocking findings
#   2  the scan failed, was canceled, or timed out
#   3  bad configuration or an API error
#
# POSIX sh on purpose: it runs in a busybox CI image without bash installed.

set -eu

API="${AEGIS_API:-https://api.aegis.security/api/v1}"
MODE="${AEGIS_MODE:-quick}"
FAIL_ON="${AEGIS_FAIL_ON-critical,high}"
TIMEOUT="${AEGIS_TIMEOUT:-3600}"
POLL="${AEGIS_POLL:-20}"

die() { echo "aegis: $1" >&2; exit "${2:-3}"; }

[ -n "${AEGIS_TOKEN:-}" ] || die "AEGIS_TOKEN is not set"
[ -n "${AEGIS_TARGET_ID:-}" ] || die "AEGIS_TARGET_ID is not set"
command -v curl >/dev/null 2>&1 || die "curl is required"

# The org header is only sent when asked for; without it the token acts in
# the organization it was issued to, which is what nearly everyone wants.
if [ -n "${AEGIS_ORG:-}" ]; then
  ORG_HEADER="X-Aegis-Org: ${AEGIS_ORG}"
else
  ORG_HEADER="X-Aegis-Ignore: 1"
fi

api() {
  # api <method> <path> [body]
  _method="$1"; _path="$2"; _body="${3:-}"
  if [ -n "$_body" ]; then
    curl -sS -X "$_method" "${API}${_path}" \
      -H "Authorization: Bearer ${AEGIS_TOKEN}" \
      -H "${ORG_HEADER}" \
      -H "Content-Type: application/json" \
      -d "$_body"
  else
    curl -sS -X "$_method" "${API}${_path}" \
      -H "Authorization: Bearer ${AEGIS_TOKEN}" \
      -H "${ORG_HEADER}"
  fi
}

# Minimal JSON field reader. Enough for the flat scalars this script reads,
# and it avoids making jq a hard dependency of every CI image.
json_field() {
  # json_field <json> <key>
  printf '%s' "$1" | tr ',' '\n' | sed -n \
    "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^\",}]*\)\"\{0,1\}.*/\1/p" | head -n 1
}

echo "aegis: launching a ${MODE} scan of ${AEGIS_TARGET_ID}"
CREATE=$(api POST /scans "{\"target_id\":\"${AEGIS_TARGET_ID}\",\"scan_mode\":\"${MODE}\"}") \
  || die "could not reach ${API}"

SCAN_ID=$(json_field "$CREATE" id)
[ -n "$SCAN_ID" ] || die "could not start the scan: ${CREATE}"
echo "aegis: scan ${SCAN_ID} queued"

WAITED=0
STATUS="pending"
while [ "$WAITED" -lt "$TIMEOUT" ]; do
  sleep "$POLL"
  WAITED=$((WAITED + POLL))
  SCAN=$(api GET "/scans/${SCAN_ID}") || continue
  STATUS=$(json_field "$SCAN" status)
  case "$STATUS" in
    completed) break ;;
    failed|canceled)
      echo "aegis: scan ${STATUS}: $(json_field "$SCAN" error_message)" >&2
      exit 2
      ;;
    *) echo "aegis: ${STATUS}… (${WAITED}s)" ;;
  esac
done

[ "$STATUS" = "completed" ] || die "timed out after ${TIMEOUT}s waiting for the scan" 2

REPORT=$(api GET "/scans/${SCAN_ID}/report") || die "could not fetch the report"
echo "aegis: report ready at ${API%/api/v1}/scans/${SCAN_ID}"

# Count blocking findings from the report's severity histogram. `counts_by_
# severity` excludes anything a human has already triaged away, so a finding
# accepted as a known risk does not fail the build a second time.
BLOCKING=0
if [ -n "$FAIL_ON" ]; then
  for sev in $(printf '%s' "$FAIL_ON" | tr ',' ' '); do
    n=$(printf '%s' "$REPORT" | tr ',' '\n' | sed -n \
      "s/.*\"${sev}\"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p" | head -n 1)
    [ -n "$n" ] || n=0
    [ "$n" -gt 0 ] && echo "aegis: ${n} ${sev} finding(s)"
    BLOCKING=$((BLOCKING + n))
  done
fi

if [ "$BLOCKING" -gt 0 ]; then
  echo "aegis: ${BLOCKING} blocking finding(s) — failing the build" >&2
  exit 1
fi

echo "aegis: no blocking findings"
exit 0
