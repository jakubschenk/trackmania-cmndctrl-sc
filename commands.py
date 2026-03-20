"""Chat command and callback handlers."""

import json
import logging

import guestlist
from config import ADMIN_LOGINS
from formatting import strip_shadow, strip_tm_formatting

_GUESTLIST_PATH = "/data/guestlist.txt"

log = logging.getLogger("cmnd/ctrl")

# ---------------------------------------------------------------------------
# Command registry & Better Chat state
# ---------------------------------------------------------------------------

_registry: dict[str, dict] = {}
_better_chat_logins: set[str] = set()


def command(name: str, *, protected: bool = False):
    """Register a chat command handler."""
    def decorator(func):
        _registry[name] = {"handler": func, "protected": protected}
        return func
    return decorator


# ---------------------------------------------------------------------------
# Unprotected commands  (single /, anyone can use)
# ---------------------------------------------------------------------------

@command("/admins")
async def cmd_admins(client, nicknames, login, arg, reply):
    names = [nicknames.get_custom(a) or nicknames.get(a) or a for a in sorted(ADMIN_LOGINS)]
    await reply(
        f"$z$s$d0f» $999Admins $d0f({len(names)})$999: $fff{'$999, $fff'.join(names)}"
    )


@command("//guestlist", protected=True)
async def cmd_guestlist(client, nicknames, login, arg, reply):
    try:
        guests = await client.send("GetGuestList", -1, 0)
        if not guests:
            await reply("$z$s$d0f» $999Guestlist is empty.")
        else:
            names = [nicknames.display_name(g["Login"]) for g in guests]
            header = f"$z$s$d0f» $999Guests $d0f({len(names)})"
            sep = "$999, $fff"
            # Split into chunks that fit TM's chat limit
            chunk = []
            length = len(header) + 6  # ": $fff"
            for name in names:
                added = len(sep) + len(name) if chunk else len(name)
                if length + added > 500 and chunk:
                    await reply(f"{header}$999: $fff{sep.join(chunk)}")
                    header = "$z$s$d0f»"
                    chunk = [name]
                    length = len(header) + 6 + len(name)
                else:
                    chunk.append(name)
                    length += added
            if chunk:
                await reply(f"{header}$999: $fff{sep.join(chunk)}")
    except Exception as e:
        await reply(f"$z$s$f00Error listing guests: {e}")


@command("/chatformat")
async def cmd_chatformat(client, nicknames, login, arg, reply):
    if arg == "json":
        _better_chat_logins.add(login)
    elif arg == "text":
        _better_chat_logins.discard(login)
    else:
        await client.chat_send_to(
            "$z$s$f00Invalid chat format. Available formats: $999json, text", login
        )


@command("/setname")
async def cmd_setname(client, nicknames, login, arg, reply):
    # NOTE: Custom names appear in chat and join/leave messages only.
    # The native scoreboard always shows the Nadeo account nickname;
    # overriding it would require a full ManiaLink overlay.
    if not arg:
        await client.chat_send_to(
            "$z$s$f00Usage: $999/setname <name with $color codes>", login
        )
        return
    nicknames.set_custom(login, arg)
    nicknames.save_custom()
    await client.chat_send_to(f"$z$s$d0f» $999Name set to: $fff{arg}", login)
    log.info("Custom name set: %s -> %s", login, strip_tm_formatting(arg))


@command("/resetname")
async def cmd_resetname(client, nicknames, login, arg, reply):
    nicknames.remove_custom(login)
    nicknames.save_custom()
    await client.chat_send_to("$z$s$d0f» $999Name reset to default.", login)
    log.info("Custom name removed: %s", login)


# ---------------------------------------------------------------------------
# Protected commands  (double //, admin only)
# ---------------------------------------------------------------------------

_SAY_ML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<manialink version="3" id="CmndCtrl_Say">'
    '<frame pos="0 15">'
    '<quad pos="0 0" z-index="0" size="160 14" halign="center" valign="center"'
    ' bgcolor="000" opacity="0.7"/>'
    '<label pos="0 0" z-index="1" size="155 12" text="{text}"'
    ' textsize="7" halign="center" valign="center"/>'
    '</frame>'
    '</manialink>'
)


@command("//say", protected=True)
async def cmd_say(client, nicknames, login, arg, reply):
    if not arg:
        await reply("$z$s$f00Usage: $999//say <message>")
        return
    safe = (arg.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;").replace('"', "&quot;"))
    xml = _SAY_ML.format(text=safe)
    await client.send("SendDisplayManialinkPage", xml, 6000, False)
    log.info("Say: %s (by %s)", strip_tm_formatting(arg), login)


@command("//addguest", protected=True)
async def cmd_addguest(client, nicknames, login, arg, reply):
    if not arg:
        await reply("$z$s$f00Usage: $999//addguest <login>")
        return
    try:
        await client.send("AddGuest", arg)
        logins = guestlist.load(_GUESTLIST_PATH)
        logins.add(arg)
        guestlist.save(_GUESTLIST_PATH, logins)
        await reply(f"$z$s$d0f» $999Guest added: $fff{nicknames.display_name(arg)}")
        log.info("Guest added: %s (by %s)", arg, login)
    except Exception as e:
        await reply(f"$z$s$f00Error adding guest: {e}")


@command("//removeguest", protected=True)
async def cmd_removeguest(client, nicknames, login, arg, reply):
    if not arg:
        await reply("$z$s$f00Usage: $999//removeguest <login>")
        return
    try:
        await client.send("RemoveGuest", arg)
        logins = guestlist.load(_GUESTLIST_PATH)
        logins.discard(arg)
        guestlist.save(_GUESTLIST_PATH, logins)
        await reply(f"$z$s$d0f» $999Guest removed: $fff{nicknames.display_name(arg)}")
        log.info("Guest removed: %s (by %s)", arg, login)
    except Exception as e:
        await reply(f"$z$s$f00Error removing guest: {e}")


@command("//addguestuser", protected=True)
async def cmd_addguestuser(client, nicknames, login, arg, reply):
    if not arg:
        await reply("$z$s$f00Usage: $999//addguestuser <username>")
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
            await reply(f"$z$s$f00No online player matching '$fff{arg}$f00'")
        elif len(matches) > 1:
            names = [
                strip_tm_formatting(p.get("NickName", p["Login"])) for p in matches
            ]
            await reply(f"$z$s$f00Multiple matches: $fff{', '.join(names)}")
        else:
            target = matches[0]["Login"]
            await client.send("AddGuest", target)
            logins = guestlist.load(_GUESTLIST_PATH)
            logins.add(target)
            guestlist.save(_GUESTLIST_PATH, logins)
            nicknames.setdefault(target, matches[0].get("NickName", target))
            await reply(
                f"$z$s$d0f» $999Guest added: $fff{nicknames.display_name(target)}"
            )
            log.info(
                "Guest added: %s (by %s, via username '%s')", target, login, arg
            )
    except Exception as e:
        await reply(f"$z$s$f00Error: {e}")


# ---------------------------------------------------------------------------
# Callback dispatcher
# ---------------------------------------------------------------------------

async def handle_callback(client, nicknames, method, params):
    if method == "ManiaPlanet.PlayerConnect":
        login = params[0]
        try:
            info = await client.send("GetDetailedPlayerInfo", login)
            nick = info.get("NickName", login) if isinstance(info, dict) else login
            if nicknames.get(login) != nick:
                nicknames.set(login, nick)
                nicknames.save()
            path = info.get("Path", "") if isinstance(info, dict) else ""
            parts = path.split("|")
            country = parts[2] if len(parts) >= 3 else parts[-1] if parts else "Unknown"
        except Exception:
            nick = login
            country = "Unknown"
        display_nick = nicknames.get_custom(login) or nick
        await client.chat_send(
            f"$z$s$999[$d0f+$999] $fff{display_nick} $z$s$999joined from $d0f{country}"
        )
        log.info("Player connected: %s (%s) from %s", login, strip_tm_formatting(display_nick), country)
        return

    if method == "ManiaPlanet.PlayerDisconnect":
        login = params[0]
        name = nicknames.get_custom(login) or nicknames.get(login) or login
        await client.chat_send(f"$z$s$999[$d0f-$999] $fff{name} $z$s$999left the server")
        _better_chat_logins.discard(login)
        return

    if method != "ManiaPlanet.PlayerChat":
        return

    player_uid, login, text, *_ = params
    if player_uid == 0:
        return

    text = text.strip()
    if not text.startswith("/"):
        custom = nicknames.get_custom(login)
        nick = strip_shadow(custom or nicknames.get(login) or login)
        chat_text = strip_shadow(text)

        if _better_chat_logins:
            try:
                players = await client.send("GetPlayerList", -1, 0)
                all_logins = {p["Login"] for p in players}
            except Exception:
                all_logins = None

            if all_logins is not None:
                bc = _better_chat_logins & all_logins
                non_bc = all_logins - bc

                if bc:
                    json_msg = json.dumps(
                        {"login": login, "nickname": nick, "text": chat_text},
                        ensure_ascii=False,
                    )
                    await client.chat_send_to(
                        f"CHAT_JSON:{json_msg}", ",".join(bc)
                    )
                if non_bc:
                    if custom:
                        await client.chat_send_to(
                            f"$z$s[$<{nick}$>]$z$s {chat_text}",
                            ",".join(non_bc),
                        )
                    else:
                        await client.chat_forward(
                            chat_text, login, ",".join(non_bc)
                        )
                return

        # No Better Chat users (or player list fetch failed) — simple path
        if custom:
            await client.chat_send(f"$z$s[$<{nick}$>]$z$s {chat_text}")
        else:
            await client.chat_forward(chat_text, login)
        return

    parts = text.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    entry = _registry.get(cmd)
    if entry is None:
        available = " $999| $fff".join(sorted(_registry))
        await client.chat_send_to(
            f"$z$s$f00Unknown command: $fff{cmd}$f00. "
            f"$999Available: $fff{available}",
            login,
        )
        return

    if entry["protected"]:
        reply = lambda msg: client.chat_send_to(msg, login)
        if login not in ADMIN_LOGINS:
            await reply(f"$z$s$f00Access denied: $fff{login} $f00is not an admin.")
            return
    else:
        reply = client.chat_send

    await entry["handler"](client, nicknames, login, arg, reply)
