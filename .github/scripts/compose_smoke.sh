#!/usr/bin/env bash
# Smoke test for the whole stack (story 3b.4): does it start, and is it wired up?
#
# Checks the wiring, not the logic (that's what the unit tests do): all services
# healthy, the pages and APIs answer on their host ports, and the generator can
# reach the inbox by its service name and deliver with the shared token.
# No Claude call is made (CI has no API key), so this costs nothing.
#
# Needs: the stack running (`docker compose up -d --wait`) with INGEST_TOKEN in
# the repo-root .env (CI writes a throwaway one). Run from the repo root:
#   bash .github/scripts/compose_smoke.sh
set -euo pipefail

step() { printf '\n== %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

step "All three services are running and healthy"
for service in backend frontend generator; do
  id="$(docker compose ps -q "$service")"
  [ -n "$id" ] || fail "service '$service' is not running"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$id")"
  echo "$service: $health"
  case "$service:$health" in
    frontend:*) ;;  # nginx has no healthcheck; it starts after a healthy backend
    *:healthy) ;;
    *) fail "$service is $health" ;;
  esac
done

step "Inbox page (:8080) and API through nginx"
curl -fsS -o /dev/null http://localhost:8080/ && echo "inbox page: 200"
curl -fsS http://localhost:8080/api/health && echo

step "Generator page (:8081) and its API"
curl -fsS http://localhost:8081/ | grep -q '<title>Email Generator</title>' \
  || fail "generator page not served at /"
echo "generator page: 200, title Email Generator"
curl -fsS http://localhost:8081/api/health && echo

# The next two steps run inside the generator container and use ITS settings
# (INBOX_URL, INGEST_TOKEN), so they prove compose configured it correctly.
step "The generator reaches the inbox at its INBOX_URL (service name, Docker DNS)"
docker compose exec -T generator python -c "
import os, urllib.request
url = os.environ['INBOX_URL']
print(url, '->', urllib.request.urlopen(url + '/api/health', timeout=5).read().decode())"

step "Delivery with the generator's own token: 201; with a wrong token: 401"
# A real (fictional) email; it lands in the inbox as unclassified.
docker compose exec -T generator python -c "
import json, os, urllib.error, urllib.request
from datetime import UTC, datetime, timedelta

email = {
    'sender_name': 'Smoke Test',
    'sender_email': 'smoke.test@example.com',
    'subject': 'Compose smoke test delivery',
    'body': 'Delivered by the compose smoke test (story 3b.4).',
    'received_at': (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
}

def deliver(token):
    request = urllib.request.Request(
        os.environ['INBOX_URL'] + '/api/emails/ingest',
        data=json.dumps({'emails': [email]}).encode(),
        headers={'Content-Type': 'application/json', 'X-Ingest-Token': token},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None

status, body = deliver('wrong-token')
print('wrong token ->', status)
assert status == 401, status

token = os.environ.get('INGEST_TOKEN', '')
assert token.strip(), 'INGEST_TOKEN is not set in the generator container'
status, body = deliver(token)
print('right token ->', status, body)
assert status == 201 and body['created'] == 1, (status, body)
"

step "The generator runs as non-root"
uid="$(docker compose exec -T generator id -u)"
echo "generator UID: $uid"
[ "$uid" != "0" ] || fail "generator runs as root"

printf '\nSmoke test passed.\n'
