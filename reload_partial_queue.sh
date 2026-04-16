#!/bin/bash
# Triggers /admin/research/queue-all-songs for a single repertoire. Since
# /admin is gated, an ADMIN_TOKEN env var must be set to an access token for
# a user with is_admin=true.
set -euo pipefail

if [ -z "${ADMIN_TOKEN:-}" ]; then
    echo "ADMIN_TOKEN env var is required. Get one via POST /auth/login as an admin user." >&2
    exit 1
fi

curl -fsSL -X POST \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    "https://api.approachnote.com/admin/research/queue-all-songs?repertoire_id=9a117193-6a57-41b2-ad81-614c9bc2cd0b"
