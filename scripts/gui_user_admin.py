from __future__ import annotations
import json
import os
import secrets
import sys
from pathlib import Path

from argon2 import PasswordHasher
import pyotp

CFG_DIR = Path.home() / ".config" / "algonovax"
USERS = CFG_DIR / "users.json"
CFG_DIR.mkdir(parents=True, exist_ok=True)

ph = PasswordHasher()

def load() -> dict:
    """
    Load the user database from the configured USERS JSON file.
    
    If the USERS file exists, parse and return its JSON content as a dict. If the file is missing, return a default dictionary with an empty "users" mapping.
    """
    if USERS.exists():
        return json.loads(USERS.read_text(encoding="utf-8"))
    return {"users": {}}

def save(db: dict) -> None:
    """
    Write the given user database dictionary to the module's USERS file as pretty-printed JSON and restrict the file permissions to owner read/write (0o600).
    
    Parameters:
        db (dict): JSON-serializable dictionary representing the user database to persist.
    """
    USERS.write_text(json.dumps(db, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(USERS, 0o600)

def add_user(username: str, password: str, role: str, totp: bool) -> None:
    """
    Create a new user record in the persistent JSON user database.
    
    Parameters:
    	username (str): Username for the new account.
    	password (str): Plain-text password to be hashed and stored.
    	role (str): Role assigned to the user.
    	totp (bool): If True, generate and store a TOTP secret and print the provisioning URI and secret.
    
    Raises:
    	SystemExit: If a user with the given username already exists.
    """
    db = load()
    if username in db["users"]:
        raise SystemExit(f"user exists: {username}")
    rec = {
        "role": role,
        "pass_hash": ph.hash(password),
        "totp_secret": pyotp.random_base32() if totp else "",
    }
    db["users"][username] = rec
    save(db)
    if totp:
        uri = pyotp.totp.TOTP(rec["totp_secret"]).provisioning_uri(name=username, issuer_name="AlgoNovaX")
        print("TOTP_URI:", uri)
        print("TOTP_SECRET:", rec["totp_secret"])

def set_pw(username: str, password: str) -> None:
    """
    Update the stored password for an existing user by hashing the provided password and persisting the database.
    
    Parameters:
    	username (str): Username whose password will be replaced.
    	password (str): Plaintext password to be hashed and stored.
    
    Raises:
    	SystemExit: If the specified username does not exist in the user database.
    """
    db = load()
    if username not in db["users"]:
        raise SystemExit(f"no such user: {username}")
    db["users"][username]["pass_hash"] = ph.hash(password)
    save(db)

def main() -> int:
    """
    CLI entry point for managing the local user database.
    
    Supports commands:
    - add <user> <pass> <role:admin|operator|viewer> [--totp]: create a new user (optionally enable TOTP).
    - passwd <user> <pass>: update an existing user's password.
    Prints "OK" on successful operations and prints usage when no command is provided.
    
    Returns:
        exit_code (int): 0 on success, 2 when usage information is shown.
    
    Raises:
        SystemExit: when a command is missing required arguments or an unknown command is provided.
    """
    if len(sys.argv) < 2:
        print("Usage:")
        print("  add <user> <pass> <role:admin|operator|viewer> [--totp]")
        print("  passwd <user> <pass>")
        return 2
    cmd = sys.argv[1]
    if cmd == "add":
        if len(sys.argv) < 5:
            raise SystemExit("add requires: user pass role")
        user, pw, role = sys.argv[2], sys.argv[3], sys.argv[4]
        totp = "--totp" in sys.argv[5:]
        add_user(user, pw, role, totp)
        print("OK")
        return 0
    if cmd == "passwd":
        if len(sys.argv) < 4:
            raise SystemExit("passwd requires: user pass")
        set_pw(sys.argv[2], sys.argv[3])
        print("OK")
        return 0
    raise SystemExit(f"unknown cmd: {cmd}")

if __name__ == "__main__":
    raise SystemExit(main())