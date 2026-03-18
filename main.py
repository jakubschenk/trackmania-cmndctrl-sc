"""Minimal guestlist controller for TrackMania dedicated server via GBX/XML-RPC."""

import asyncio
import json
import logging
import os
import struct
import xml.etree.ElementTree as ET
from xmlrpc.client import dumps, loads

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("guestlist")

RPC_HOST = os.environ.get("RPC_HOST", "trackmania")
RPC_PORT = int(os.environ.get("RPC_PORT", "5000"))
RPC_USER = os.environ.get("RPC_USER", "SuperAdmin")
RPC_PASSWORD = os.environ.get("RPC_PASSWORD", "SuperAdmin")
GUESTLIST_FILE = os.environ.get("GUESTLIST_FILE", "guestlist.txt")
ADMIN_LOGINS = {
    s.strip() for s in os.environ.get("ADMIN_LOGINS", "").split(",") if s.strip()
}
NICKNAMES_FILE = os.environ.get("NICKNAMES_FILE", "/data/nicknames.json")


def strip_tm_formatting(text: str) -> str:
    """Strip TM formatting codes ($fff, $o, $z, etc.) from a string."""
    import re
    return re.sub(r'\$([0-9a-fA-F]{3}|[lhp](\[[^\]]*\])?|.)', '', text)


class GBXClient:
    def __init__(self):
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._handler_id = 0x80000000
        self._pending: dict[int, asyncio.Future] = {}
        self.nicknames: dict[str, str] = self._load_nicknames()

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(RPC_HOST, RPC_PORT)
        header = await self.reader.readexactly(4)
        size = struct.unpack_from("<I", header)[0]
        proto = await self.reader.readexactly(size)
        if b"GBXRemote" not in proto:
            raise ConnectionError(f"Bad GBX header: {proto}")
        log.info("Connected to %s:%s (%s)", RPC_HOST, RPC_PORT, proto.decode())

    async def send(self, method: str, *args) -> object:
        payload = dumps(args, method).encode()
        handler_id = self._handler_id
        self._handler_id += 1
        header = struct.pack("<II", len(payload), handler_id)
        self.writer.write(header + payload)
        await self.writer.drain()

        fut = asyncio.get_event_loop().create_future()
        self._pending[handler_id] = fut
        return await fut

    async def _read_loop(self, callback):
        while True:
            raw_header = await self.reader.readexactly(8)
            size, handler_id = struct.unpack("<II", raw_header)
            payload = await self.reader.readexactly(size)

            if handler_id >= 0x80000000:
                fut = self._pending.pop(handler_id, None)
                if fut and not fut.done():
                    try:
                        result, _ = loads(payload)
                        fut.set_result(result[0] if len(result) == 1 else result)
                    except Exception as e:
                        fut.set_exception(e)
            else:
                try:
                    params, method = loads(payload)
                    asyncio.create_task(callback(method, params))
                except Exception:
                    log.exception("Error parsing callback")

    async def authenticate(self):
        result = await self.send("Authenticate", RPC_USER, RPC_PASSWORD)
        if not result:
            raise ConnectionError("Authentication failed")
        log.info("Authenticated as %s", RPC_USER)

        await self.send("SetApiVersion", "2013-04-16")
        await self.send("EnableCallbacks", True)
        log.info("Callbacks enabled")

    async def chat_send(self, msg: str):
        await self.send("ChatSendServerMessage", msg)

    @staticmethod
    def _load_nicknames() -> dict[str, str]:
        try:
            with open(NICKNAMES_FILE) as f:
                data = json.load(f)
                log.info("Loaded %d nicknames from cache", len(data))
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_nicknames(self):
        os.makedirs(os.path.dirname(NICKNAMES_FILE), exist_ok=True)
        with open(NICKNAMES_FILE, "w") as f:
            json.dump(self.nicknames, f)

    async def is_admin(self, login: str) -> bool:
        return login in ADMIN_LOGINS

    async def get_nickname(self, login: str) -> str:
        if login in self.nicknames:
            return self.nicknames[login]
        try:
            info = await self.send("GetDetailedPlayerInfo", login)
            nick = info.get("NickName", login) if isinstance(info, dict) else login
            self.nicknames[login] = nick
            self._save_nicknames()
            return nick
        except Exception:
            return login

    def display_name(self, login: str) -> str:
        """Return 'nickname (login)' or just login if no nickname cached."""
        nick = self.nicknames.get(login)
        if nick:
            clean = strip_tm_formatting(nick)
            if clean and clean != login:
                return f"{nick}$z$s ({login})"
        return login

    def close(self):
        if self.writer:
            self.writer.close()


async def handle_callback(client: GBXClient, method: str, params):
    if method == "ManiaPlanet.PlayerConnect":
        # params: [Login, IsSpectator]
        login = params[0]
        try:
            info = await client.send("GetDetailedPlayerInfo", login)
            nick = info.get("NickName", login) if isinstance(info, dict) else login
            client.nicknames[login] = nick
            client._save_nicknames()
            # Path is like "World|Europe|Netherlands|North Holland"
            path = info.get("Path", "") if isinstance(info, dict) else ""
            parts = path.split("|")
            country = parts[2] if len(parts) >= 3 else parts[-1] if parts else "Unknown"
        except Exception:
            nick = login
            country = "Unknown"
        await client.chat_send(f"$z$s$ff0Player $z$s$fff{nick} $z$s$ff0has joined from $z$s$fff{country}$z$s$ff0.")
        log.info("Player connected: %s (%s) from %s", login, strip_tm_formatting(nick), country)
        return

    if method == "ManiaPlanet.PlayerDisconnect":
        # params: [Login, DisconnectionReason]
        login = params[0]
        name = client.display_name(login)
        await client.chat_send(f"$z$s$ff0<< {name} $z$s$ff0left the server")
        client.nicknames.pop(login, None)
        return

    if method != "ManiaPlanet.PlayerChat":
        return

    # params: [PlayerUid, Login, Text, IsRegisteredCmd]
    player_uid, login, text, *_ = params
    # Ignore server messages (uid 0)
    if player_uid == 0:
        return

    text = text.strip()
    if not text.startswith("//"):
        return

    parts = text.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    COMMANDS = ("//addguest", "//removeguest", "//guestlist", "//admins", "//addguestuser")
    if cmd not in COMMANDS:
        return

    if not await client.is_admin(login):
        await client.chat_send(f"$z$s$f00Access denied: {login} is not an admin.")
        return

    if cmd == "//addguest":
        if not arg:
            await client.chat_send("$z$s$f00Usage: //addguest <login>")
            return
        try:
            await client.send("AddGuest", arg)
            await client.send("SaveGuestList", GUESTLIST_FILE)
            await client.chat_send(f"$z$s$ff0Guest added: {client.display_name(arg)}")
            log.info("Guest added: %s (by %s)", arg, login)
        except Exception as e:
            await client.chat_send(f"$z$s$f00Error adding guest: {e}")

    elif cmd == "//removeguest":
        if not arg:
            await client.chat_send("$z$s$f00Usage: //removeguest <login>")
            return
        try:
            await client.send("RemoveGuest", arg)
            await client.send("SaveGuestList", GUESTLIST_FILE)
            await client.chat_send(f"$z$s$ff0Guest removed: {client.display_name(arg)}")
            log.info("Guest removed: %s (by %s)", arg, login)
        except Exception as e:
            await client.chat_send(f"$z$s$f00Error removing guest: {e}")

    elif cmd == "//guestlist":
        try:
            guests = await client.send("GetGuestList", -1, 0)
            if not guests:
                await client.chat_send("$z$s$ff0Guestlist is empty.")
            else:
                names = [client.display_name(g["Login"]) for g in guests]
                await client.chat_send(f"$z$s$ff0Guests ({len(names)}): {'$z$s$ff0,'.join(names)}")
        except Exception as e:
            await client.chat_send(f"$z$s$f00Error listing guests: {e}")

    elif cmd == "//admins":
        names = [client.display_name(l) for l in sorted(ADMIN_LOGINS)]
        await client.chat_send(f"$z$s$ff0Admins ({len(names)}): {'$z$s$ff0,'.join(names)}")

    elif cmd == "//addguestuser":
        if not arg:
            await client.chat_send("$z$s$f00Usage: //addguestuser <username>")
            return
        try:
            players = await client.send("GetPlayerList", -1, 0)
            search = arg.lower()
            matches = []
            for p in players:
                nick = p.get("NickName", "")
                clean = strip_tm_formatting(nick).lower()
                if clean == search:
                    matches = [p]
                    break
                if search in clean:
                    matches.append(p)
            if not matches:
                await client.chat_send(f"$z$s$f00No online player matching '{arg}'")
            elif len(matches) > 1:
                names = [strip_tm_formatting(p.get("NickName", p["Login"])) for p in matches]
                await client.chat_send(f"$z$s$f00Multiple matches: {', '.join(names)}")
            else:
                target = matches[0]["Login"]
                await client.send("AddGuest", target)
                await client.send("SaveGuestList", GUESTLIST_FILE)
                client.nicknames.setdefault(target, matches[0].get("NickName", target))
                await client.chat_send(f"$z$s$ff0Guest added: {client.display_name(target)}")
                log.info("Guest added: %s (by %s, via username '%s')", target, login, arg)
        except Exception as e:
            await client.chat_send(f"$z$s$f00Error: {e}")


async def run():
    client = GBXClient()
    try:
        await client.connect()

        # Start read loop first so responses to send() are processed
        read_task = asyncio.create_task(
            client._read_loop(lambda method, params: handle_callback(client, method, params))
        )

        await client.authenticate()

        await client.chat_send("$z$s$ff0Controller connected.")

        # Disable callvotes
        try:
            await client.send("SetCallVoteTimeOut", 0)
            log.info("Callvotes disabled")
        except Exception as e:
            log.warning("Failed to disable callvotes: %s", e)

        # Hide UI modules: records widget and join/leave notifications
        try:
            await client.send(
                "TriggerModeScriptEventArray",
                "Common.UIModules.SetProperties",
                ['{"uimodules":['
                 '{"id":"Race_Record","visible":false,"visible_update":true},'
                 '{"id":"Race_PlayersPresentation","visible":false,"visible_update":true}'
                 ']}'],
            )
            log.info("UI modules hidden")
        except Exception as e:
            log.warning("Failed to hide UI modules: %s", e)

        # Pre-populate nickname cache from current player list
        try:
            players = await client.send("GetPlayerList", -1, 0)
            for p in players:
                login = p.get("Login", "")
                nick = p.get("NickName", "")
                if login and nick:
                    client.nicknames[login] = nick
            client._save_nicknames()
            log.info("Cached %d player nicknames", len(client.nicknames))
        except Exception as e:
            log.warning("Failed to fetch player list: %s", e)

        # Ensure all admins are on the guestlist
        for login in ADMIN_LOGINS:
            try:
                await client.send("AddGuest", login)
                log.info("Ensured admin %s is on guestlist", login)
            except Exception as e:
                log.warning("AddGuest %s: %s", login, e)
        if ADMIN_LOGINS:
            try:
                await client.send("SaveGuestList", GUESTLIST_FILE)
                log.info("Guestlist saved")
            except Exception:
                log.exception("Failed to save guestlist")

        # Block until connection drops
        await read_task
    finally:
        client.close()


async def main():
    while True:
        try:
            await run()
        except (ConnectionError, asyncio.IncompleteReadError, OSError) as e:
            log.warning("Connection lost: %s — retrying in 5s", e)
        except Exception:
            log.exception("Unexpected error — retrying in 5s")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
