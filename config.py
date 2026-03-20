"""Configuration constants loaded from environment variables."""

import os

RPC_HOST = os.environ.get("RPC_HOST", "trackmania")
RPC_PORT = int(os.environ.get("RPC_PORT", "5000"))
RPC_USER = os.environ.get("RPC_USER", "SuperAdmin")
RPC_PASSWORD = os.environ.get("RPC_PASSWORD", "SuperAdmin")
ADMIN_LOGINS = {
    s.strip() for s in os.environ.get("ADMIN_LOGINS", "").split(",") if s.strip()
}
NICKNAMES_FILE = os.environ.get("NICKNAMES_FILE", "/data/nicknames.json")
CUSTOM_NAMES_FILE = os.environ.get("CUSTOM_NAMES_FILE", "/data/custom_names.json")
