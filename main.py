"""cmnd/ctrl v0.1 — guestlist & chat controller for TrackMania dedicated server."""

import asyncio
import logging

import guestlist
from config import ADMIN_LOGINS, NICKNAMES_FILE, CUSTOM_NAMES_FILE
from gbx_client import GBXClient
from nicknames import NicknameCache
from commands import handle_callback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cmnd/ctrl")


async def run():
    client = GBXClient()
    nicknames = NicknameCache(NICKNAMES_FILE, CUSTOM_NAMES_FILE)
    try:
        await client.connect()

        # Start read loop first so responses to send() are processed
        read_task = asyncio.create_task(
            client._read_loop(
                lambda method, params: handle_callback(client, nicknames, method, params)
            )
        )

        await client.authenticate()

        await client.chat_send("$z$s$999cmnd$fff/$d0fctrl $999v0.1 $fff| $d0finitialized successfully")

        # Enable manual chat routing so we can intercept protected commands
        try:
            await client.send("ChatEnableManualRouting", True, False)
            log.info("Manual chat routing enabled")
        except Exception as e:
            log.warning("Failed to enable manual chat routing: %s", e)

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
                    nicknames.set(login, nick)
            nicknames.save()
            log.info("Cached %d player nicknames", len(nicknames))
        except Exception as e:
            log.warning("Failed to fetch player list: %s", e)

        # Load guestlist from local file and sync to server via RPC
        logins = guestlist.load("/data/guestlist.txt") | ADMIN_LOGINS
        for login in logins:
            try:
                await client.send("AddGuest", login)
            except Exception as e:
                log.warning("AddGuest %s: %s", login, e)
        guestlist.save("/data/guestlist.txt", logins)
        log.info("Synced %d guests to server", len(logins))

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
