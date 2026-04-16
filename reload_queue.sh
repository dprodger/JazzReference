#!/bin/bash
# Triggers the /admin/research/queue-all-songs endpoint. Since /admin is gated,
# an ADMIN_TOKEN env var must be set to an access token issued for a user with
# is_admin=true (POST /auth/login, or generate via a local script).
set -euo pipefail

if [ -z "${ADMIN_TOKEN:-}" ]; then
    echo "ADMIN_TOKEN env var is required. Get one via POST /auth/login as an admin user." >&2
    exit 1
fi

curl -fsSL -X POST \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    https://api.approachnote.com/admin/research/queue-all-songs
