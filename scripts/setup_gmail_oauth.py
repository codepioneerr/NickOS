#!/usr/bin/env python3
"""
scripts/setup_gmail_oauth.py
One-time Gmail OAuth2 setup — supports up to 4 accounts.

Usage:
    python scripts/setup_gmail_oauth.py              # set up account 1 (default)
    python scripts/setup_gmail_oauth.py --account 2  # set up account 2
    python scripts/setup_gmail_oauth.py --account 3
    python scripts/setup_gmail_oauth.py --account 4
    python scripts/setup_gmail_oauth.py --list       # show all configured accounts

Prerequisites:
    1. Go to https://console.cloud.google.com
    2. Create/select a project → Enable Gmail API
    3. APIs & Services → Credentials → Create OAuth Client ID
       Type: Desktop App, Name: NickOS
    4. Download JSON → save as gmail/credentials.json
    5. Add account details to .env (see .env.example)
    6. Run this script per account
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT             = Path(__file__).parent.parent
CREDENTIALS_PATH = Path(os.environ.get("GMAIL_CREDENTIALS_PATH", ROOT / "gmail/credentials.json"))

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def get_account_config(account_num: int) -> dict:
    """Read one account's config from .env."""
    email = os.environ.get(f"GMAIL_ACCOUNT_{account_num}_EMAIL", "").strip()
    name  = os.environ.get(f"GMAIL_ACCOUNT_{account_num}_NAME",  f"Account {account_num}").strip()
    token = os.environ.get(
        f"GMAIL_ACCOUNT_{account_num}_TOKEN",
        str(ROOT / f"gmail/tokens/account{account_num}_token.json")
    )
    return {"num": account_num, "email": email, "name": name, "token_path": Path(token)}


def list_accounts():
    import json as _json
    tokens_dir    = ROOT / "gmail/tokens"
    registry_path = tokens_dir / "accounts_registry.json"
    registry: dict = {}
    if registry_path.exists():
        try:
            registry = _json.loads(registry_path.read_text())
        except Exception:
            pass

    token_files = sorted(
        f for f in tokens_dir.glob("*_token.json")
        if f.name != "accounts_registry.json"
    ) if tokens_dir.exists() else []

    print("\n📋 Gmail accounts (auto-detected from gmail/tokens/):\n")
    if not token_files:
        print("  No token files found in gmail/tokens/")
        print("  Run: python scripts/setup_gmail_oauth.py --account 1\n")
        return

    for i, tf in enumerate(token_files, 1):
        meta  = registry.get(tf.name, {})
        email = meta.get("email", "unknown (run --list again after first /email)")
        name  = meta.get("name",  tf.stem.replace("_token", ""))
        print(f"  {i}. {name} <{email}>")
        print(f"     Token: {tf.name}  ✅")
    print()


def authorize_account(account_num: int):
    cfg = get_account_config(account_num)

    if not cfg["email"]:
        print(f"\n❌  Account {account_num} not configured in .env")
        print(f"    Add these lines to your .env:\n")
        print(f"    GMAIL_ACCOUNT_{account_num}_NAME=MyAccount")
        print(f"    GMAIL_ACCOUNT_{account_num}_EMAIL=you@gmail.com")
        print(f"    GMAIL_ACCOUNT_{account_num}_TOKEN=./gmail/tokens/account{account_num}_token.json\n")
        sys.exit(1)

    if not CREDENTIALS_PATH.exists():
        print(f"\n❌  credentials.json not found at: {CREDENTIALS_PATH}")
        print("    Download it from Google Cloud Console (see script docstring).\n")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌  Run: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    print(f"\n🔐 Authorizing account {account_num}: {cfg['name']} <{cfg['email']}>")
    print(f"   Your browser will open for Google sign-in.")
    print(f"   Make sure to sign in as: {cfg['email']}\n")

    flow  = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    cfg["token_path"].parent.mkdir(parents=True, exist_ok=True)
    cfg["token_path"].write_text(creds.to_json())

    print(f"\n✅  Token saved: {cfg['token_path']}")

    # Verify + update accounts_registry.json
    try:
        from googleapiclient.discovery import build
        import json as _json
        service  = build("gmail", "v1", credentials=creds)
        profile  = service.users().getProfile(userId="me").execute()
        email    = profile["emailAddress"]
        local    = email.split("@")[0]
        domain   = email.split("@")[1] if "@" in email else ""
        if "fordham" in domain:
            name = f"Fordham ({local})"
        else:
            name = cfg.get("name") or local.capitalize()

        # Write to registry so fetcher picks it up immediately
        registry_path = cfg["token_path"].parent / "accounts_registry.json"
        registry: dict = {}
        if registry_path.exists():
            try:
                registry = _json.loads(registry_path.read_text())
            except Exception:
                pass
        registry[cfg["token_path"].name] = {"email": email, "name": name}
        registry_path.write_text(_json.dumps(registry, indent=2))

        print(f"   Gmail address: {email}")
        print(f"   Account name:  {name}")
        print(f"   Total messages: {profile['messagesTotal']}")
        print(f"   Registry updated: {registry_path}\n")
    except Exception as e:
        print(f"   (Could not verify: {e})\n")


def main():
    parser = argparse.ArgumentParser(description="NickOS Gmail OAuth setup")
    parser.add_argument("--account", type=int, default=1,
                        help="Account number to authorize (1–4, default: 1)")
    parser.add_argument("--list", action="store_true",
                        help="List all configured accounts and token status")
    args = parser.parse_args()

    if args.list:
        list_accounts()
        return

    if args.account < 1 or args.account > 4:
        print("❌  --account must be between 1 and 4")
        sys.exit(1)

    authorize_account(args.account)
    print("Next: run for other accounts, e.g.:")
    for i in range(1, 5):
        cfg = get_account_config(i)
        if cfg["email"] and not cfg["token_path"].exists():
            print(f"  python scripts/setup_gmail_oauth.py --account {i}")


if __name__ == "__main__":
    main()
