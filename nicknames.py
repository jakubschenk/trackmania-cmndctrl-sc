"""Nickname cache backed by a JSON file."""

import json
import logging
import os

from formatting import strip_tm_formatting

log = logging.getLogger("cmnd/ctrl")


def _load_json(path: str) -> dict[str, str]:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_json(path: str, data: dict):
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


class NicknameCache:
    def __init__(self, file_path: str, custom_file: str):
        self.file_path = file_path
        self.custom_file = custom_file
        self._cache: dict[str, str] = _load_json(file_path)
        if self._cache:
            log.info("Loaded %d nicknames from cache", len(self._cache))
        self._custom: dict[str, str] = _load_json(custom_file)
        if self._custom:
            log.info("Loaded %d custom names", len(self._custom))

    def save(self):
        _save_json(self.file_path, self._cache)

    def get(self, login: str) -> str | None:
        return self._cache.get(login)

    def set(self, login: str, nick: str):
        self._cache[login] = nick

    def setdefault(self, login: str, nick: str):
        self._cache.setdefault(login, nick)

    def pop(self, login: str, default=None):
        return self._cache.pop(login, default)

    # Custom names

    def get_custom(self, login: str) -> str | None:
        return self._custom.get(login)

    def set_custom(self, login: str, name: str):
        self._custom[login] = name

    def remove_custom(self, login: str):
        self._custom.pop(login, None)

    def save_custom(self):
        _save_json(self.custom_file, self._custom)

    def custom_items(self):
        return self._custom.items()

    def display_name(self, login: str) -> str:
        """Return 'nickname (login)' or just login if no nickname cached."""
        custom = self._custom.get(login)
        if custom:
            return f"{custom}$z$s ({login})"
        nick = self._cache.get(login)
        if nick:
            clean = strip_tm_formatting(nick)
            if clean and clean != login:
                return f"{nick}$z$s ({login})"
        return login

    async def get_or_fetch(self, login: str, client) -> str:
        """Get nickname from cache, or fetch from server via GBX."""
        cached = self._cache.get(login)
        if cached is not None:
            return cached
        try:
            info = await client.send("GetDetailedPlayerInfo", login)
            nick = info.get("NickName", login) if isinstance(info, dict) else login
            self._cache[login] = nick
            self.save()
            return nick
        except Exception:
            return login

    def __len__(self):
        return len(self._cache)

    def __contains__(self, login):
        return login in self._cache
