#!/usr/bin/env python3
"""
Grant or revoke admin access for a user.

Usage:
    python scripts/grant_admin.py <email>              # grant admin
    python scripts/grant_admin.py <email> --revoke     # revoke admin
    python scripts/grant_admin.py <email> --yes        # skip confirmation

Exits non-zero if the email is unknown or the user declines the prompt.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path so we can import db_utils (mirrors script_base.py).
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from backend/ so DATABASE_URL is available.
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from db_utils import get_db_connection  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Grant or revoke /admin access for a user.",
    )
    parser.add_argument('email', help="Email address of the user.")
    parser.add_argument(
        '--revoke',
        action='store_true',
        help="Revoke admin (set is_admin=false). Default action is grant.",
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help="Skip the interactive confirmation prompt.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    target_state = not args.revoke
    verb = "grant" if target_state else "revoke"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, display_name, is_admin, is_active "
                "FROM users WHERE email = %s",
                (args.email,),
            )
            user = cur.fetchone()

            if not user:
                print(f"No user found with email: {args.email}", file=sys.stderr)
                return 1

            print(f"User:       {user['email']}")
            print(f"  id:         {user['id']}")
            print(f"  name:       {user['display_name'] or '(unset)'}")
            print(f"  is_active:  {user['is_active']}")
            print(f"  is_admin:   {user['is_admin']} -> {target_state}")

            if user['is_admin'] == target_state:
                print(f"Nothing to do; user is already is_admin={target_state}.")
                return 0

            if not user['is_active'] and target_state:
                print(
                    "Refusing to grant admin to an inactive user.",
                    file=sys.stderr,
                )
                return 1

            if not args.yes:
                answer = input(f"Proceed to {verb} admin for {args.email}? [y/N] ")
                if answer.strip().lower() != 'y':
                    print("Cancelled.")
                    return 1

            cur.execute(
                "UPDATE users SET is_admin = %s, updated_at = NOW() "
                "WHERE id = %s RETURNING is_admin",
                (target_state, user['id']),
            )
            new_state = cur.fetchone()['is_admin']
            conn.commit()

    print(f"Done. is_admin is now {new_state} for {args.email}.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
