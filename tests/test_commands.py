import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from nicknames import NicknameCache


def _make_fixtures():
    tmpdir = tempfile.mkdtemp()
    nick_path = os.path.join(tmpdir, "nicks.json")
    custom_path = os.path.join(tmpdir, "custom.json")
    nicknames = NicknameCache(nick_path, custom_path)
    client = MagicMock()
    client.send = AsyncMock(return_value=True)
    client.chat_send = AsyncMock()
    client.chat_send_to = AsyncMock()
    client.chat_forward = AsyncMock()
    return tmpdir, nicknames, client


class TestAddGuest(unittest.IsolatedAsyncioTestCase):
    @patch("commands.ADMIN_LOGINS", {"admin1"})
    @patch("commands.GUESTLIST_FILE", "guest.txt")
    async def test_addguest_calls_add_and_save(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//addguest target", True],
        )
        client.send.assert_any_call("AddGuest", "target")
        client.send.assert_any_call("SaveGuestList", "guest.txt")
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Guest added", msg)
        client.chat_send.assert_not_called()

    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_addguest_no_arg_sends_usage(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//addguest", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Usage", msg)
        client.chat_send.assert_not_called()


class TestRemoveGuest(unittest.IsolatedAsyncioTestCase):
    @patch("commands.ADMIN_LOGINS", {"admin1"})
    @patch("commands.GUESTLIST_FILE", "guest.txt")
    async def test_removeguest_calls_remove_and_save(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//removeguest target", True],
        )
        client.send.assert_any_call("RemoveGuest", "target")
        client.send.assert_any_call("SaveGuestList", "guest.txt")
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Guest removed", msg)
        client.chat_send.assert_not_called()


class TestGuestList(unittest.IsolatedAsyncioTestCase):
    async def test_guestlist_formats_output(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        nicknames.set("p1", "$fffNick1")
        client.send.return_value = [{"Login": "p1"}, {"Login": "p2"}]
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "anyone", "/guestlist", True],
        )
        msg = client.chat_send.call_args[0][0]
        self.assertIn("Guests", msg)
        self.assertIn("(2)", msg)

    async def test_guestlist_empty(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        client.send.return_value = []
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "anyone", "/guestlist", True],
        )
        msg = client.chat_send.call_args[0][0]
        self.assertIn("empty", msg)


class TestAdmins(unittest.IsolatedAsyncioTestCase):
    @patch("commands.ADMIN_LOGINS", {"admin1", "admin2"})
    async def test_admins_lists_with_display_names(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        nicknames.set("admin1", "$fffBoss")
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "anyone", "/admins", True],
        )
        msg = client.chat_send.call_args[0][0]
        self.assertIn("Admins", msg)
        self.assertIn("(2)", msg)
        self.assertIn("Boss", msg)


class TestAddGuestUser(unittest.IsolatedAsyncioTestCase):
    @patch("commands.ADMIN_LOGINS", {"admin1"})
    @patch("commands.GUESTLIST_FILE", "guest.txt")
    async def test_addguestuser_finds_by_nickname(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        client.send.side_effect = [
            [{"Login": "target1", "NickName": "$fffCoolPlayer"}],  # GetPlayerList
            True,  # AddGuest
            True,  # SaveGuestList
        ]
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//addguestuser coolplayer", True],
        )
        client.send.assert_any_call("AddGuest", "target1")
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Guest added", msg)
        client.chat_send.assert_not_called()

    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_addguestuser_no_match(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        client.send.return_value = [{"Login": "p1", "NickName": "Other"}]
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//addguestuser nobody", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("No online player", msg)

    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_addguestuser_multiple_matches(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        client.send.return_value = [
            {"Login": "p1", "NickName": "$fffCoolA"},
            {"Login": "p2", "NickName": "$fffCoolB"},
        ]
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//addguestuser cool", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Multiple matches", msg)


class TestSetName(unittest.IsolatedAsyncioTestCase):
    async def test_setname_stores_custom_name(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/setname $f00Red$fffName", True],
        )
        self.assertEqual(nicknames.get_custom("player1"), "$f00Red$fffName")
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Name set to", msg)
        client.chat_send.assert_not_called()

    async def test_setname_no_arg_sends_usage(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/setname", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Usage", msg)


class TestResetName(unittest.IsolatedAsyncioTestCase):
    async def test_resetname_removes_custom_name(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        nicknames.set_custom("player1", "$f00Custom")
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/resetname", True],
        )
        self.assertIsNone(nicknames.get_custom("player1"))
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("reset", msg)
        client.chat_send.assert_not_called()


class TestAccessControl(unittest.IsolatedAsyncioTestCase):
    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_non_admin_gets_denied_on_protected(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "noob", "//addguest someone", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Access denied", msg)
        client.chat_send.assert_not_called()

    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_non_admin_can_use_unprotected(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "noob", "/admins", True],
        )
        msg = client.chat_send.call_args[0][0]
        self.assertIn("Admins", msg)

    async def test_server_messages_ignored(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [0, "server", "//addguest x", True],
        )
        client.chat_send.assert_not_called()
        client.chat_send_to.assert_not_called()

    async def test_regular_chat_forwarded(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "hello world", True],
        )
        client.chat_forward.assert_called_once_with("hello world", "player1")
        client.chat_send.assert_not_called()
        client.chat_send_to.assert_not_called()

    async def test_chat_with_custom_name_sends_server_message(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        nicknames.set_custom("player1", "$f00Red")
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "hello world", True],
        )
        client.chat_send.assert_called_once_with(
            "$z$s[$<$f00Red$>]$z$s hello world"
        )
        client.chat_forward.assert_not_called()

    async def test_chat_without_custom_name_forwards_normally(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "just chatting", True],
        )
        client.chat_forward.assert_called_once_with("just chatting", "player1")
        client.chat_send.assert_not_called()

    async def test_unknown_command_shows_fallback(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/notreal", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Unknown command", msg)
        self.assertIn("/notreal", msg)
        self.assertIn("Available", msg)
        client.chat_send.assert_not_called()


class TestSay(unittest.IsolatedAsyncioTestCase):
    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_say_sends_manialink(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//say $f00Hello World!", True],
        )
        client.send.assert_any_call(
            "SendDisplayManialinkPage",
            unittest.mock.ANY, 6000, False,
        )
        xml = client.send.call_args_list[-1][0][1]
        self.assertIn("CmndCtrl_Say", xml)
        self.assertIn("$f00Hello World!", xml)

    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_say_escapes_xml(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", '//say <script>&"test"</script>', True],
        )
        xml = client.send.call_args_list[-1][0][1]
        self.assertIn("&lt;script&gt;", xml)
        self.assertIn("&amp;", xml)
        self.assertIn("&quot;", xml)
        self.assertNotIn("<script>", xml)

    @patch("commands.ADMIN_LOGINS", {"admin1"})
    async def test_say_no_arg_shows_usage(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "admin1", "//say", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Usage", msg)


class TestChatFormat(unittest.IsolatedAsyncioTestCase):
    @patch("commands._better_chat_logins", set())
    async def test_chatformat_json_adds_login(self):
        from commands import handle_callback, _better_chat_logins

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/chatformat json", True],
        )
        self.assertIn("player1", _better_chat_logins)

    @patch("commands._better_chat_logins", set())
    async def test_chatformat_text_removes_login(self):
        from commands import handle_callback, _better_chat_logins

        _better_chat_logins.add("player1")
        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/chatformat text", True],
        )
        self.assertNotIn("player1", _better_chat_logins)

    @patch("commands._better_chat_logins", set())
    async def test_chatformat_invalid_shows_error(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "/chatformat badarg", True],
        )
        msg = client.chat_send_to.call_args[0][0]
        self.assertIn("Invalid", msg)


class TestBetterChatDualSend(unittest.IsolatedAsyncioTestCase):
    @patch("commands._better_chat_logins", {"bc_user"})
    async def test_dual_send_json_to_bc_plain_to_others(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        nicknames.set("player1", "$fffNick")
        client.send.return_value = [
            {"Login": "player1"}, {"Login": "bc_user"}, {"Login": "other"},
        ]
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "hello", True],
        )
        # BC user gets JSON
        json_call = None
        forward_call = None
        for call in client.chat_send_to.call_args_list:
            msg, logins = call[0]
            if msg.startswith("CHAT_JSON:"):
                json_call = (msg, logins)
            else:
                forward_call = (msg, logins)

        self.assertIsNotNone(json_call)
        payload = json.loads(json_call[0].removeprefix("CHAT_JSON:"))
        self.assertEqual(payload["login"], "player1")
        self.assertEqual(payload["nickname"], "$fffNick")
        self.assertEqual(payload["text"], "hello")
        self.assertEqual(json_call[1], "bc_user")

        # Non-BC users get forwarded normally
        client.chat_forward.assert_called_once()
        fwd_args = client.chat_forward.call_args[0]
        self.assertEqual(fwd_args[0], "hello")
        self.assertEqual(fwd_args[1], "player1")

    @patch("commands._better_chat_logins", {"bc_user"})
    async def test_dual_send_custom_name_plain_text_to_non_bc(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        nicknames.set("player1", "$fffNick")
        nicknames.set_custom("player1", "$s$f00Red")
        client.send.return_value = [
            {"Login": "player1"}, {"Login": "bc_user"}, {"Login": "other"},
        ]
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "hey", True],
        )
        # BC user gets JSON with custom name ($s stripped)
        json_call = None
        plain_call = None
        for call in client.chat_send_to.call_args_list:
            msg, logins = call[0]
            if msg.startswith("CHAT_JSON:"):
                json_call = (msg, logins)
            else:
                plain_call = (msg, logins)

        payload = json.loads(json_call[0].removeprefix("CHAT_JSON:"))
        self.assertEqual(payload["nickname"], "$f00Red")
        self.assertNotIn("$s", payload["nickname"])

        # Non-BC users get plain text with $<...$> wrapping
        self.assertIsNotNone(plain_call)
        self.assertIn("$<$f00Red$>", plain_call[0])
        client.chat_forward.assert_not_called()

    @patch("commands._better_chat_logins", set())
    async def test_no_bc_users_falls_back_to_simple_path(self):
        from commands import handle_callback

        _, nicknames, client = _make_fixtures()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerChat",
            [1, "player1", "hi there", True],
        )
        client.chat_forward.assert_called_once_with("hi there", "player1")
        client.chat_send_to.assert_not_called()


class TestDisconnectCleansBetterChat(unittest.IsolatedAsyncioTestCase):
    @patch("commands._better_chat_logins", set())
    async def test_disconnect_removes_bc_login(self):
        from commands import handle_callback, _better_chat_logins

        _better_chat_logins.add("player1")
        _, nicknames, client = _make_fixtures()
        nicknames.set("player1", "Nick")
        client.chat_send = AsyncMock()
        await handle_callback(
            client, nicknames, "ManiaPlanet.PlayerDisconnect",
            ["player1", ""],
        )
        self.assertNotIn("player1", _better_chat_logins)


if __name__ == "__main__":
    unittest.main()
