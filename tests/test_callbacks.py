import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands import handle_callback
from nicknames import NicknameCache


class TestPlayerConnect(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.nicknames = NicknameCache(
            os.path.join(self.tmpdir, "nicks.json"),
            os.path.join(self.tmpdir, "custom.json"),
        )
        self.client = MagicMock()
        self.client.send = AsyncMock()
        self.client.chat_send = AsyncMock()

    async def test_caches_nickname_and_sends_join_with_country(self):
        self.client.send.return_value = {
            "NickName": "$fffCoolPlayer",
            "Path": "World|Europe|Netherlands|North Holland",
        }
        await handle_callback(
            self.client, self.nicknames,
            "ManiaPlanet.PlayerConnect", ["player1", False],
        )
        self.assertEqual(self.nicknames.get("player1"), "$fffCoolPlayer")
        msg = self.client.chat_send.call_args[0][0]
        self.assertIn("Netherlands", msg)
        self.assertIn("joined", msg)

    async def test_extracts_country_from_3rd_path_segment(self):
        self.client.send.return_value = {
            "NickName": "Test",
            "Path": "World|Asia|Japan|Tokyo",
        }
        await handle_callback(
            self.client, self.nicknames,
            "ManiaPlanet.PlayerConnect", ["p1", False],
        )
        msg = self.client.chat_send.call_args[0][0]
        self.assertIn("Japan", msg)

    async def test_uses_custom_name_in_join_message(self):
        self.nicknames.set_custom("player1", "$f00Custom")
        self.client.send.return_value = {
            "NickName": "$fffOriginal",
            "Path": "World|Europe|France",
        }
        await handle_callback(
            self.client, self.nicknames,
            "ManiaPlanet.PlayerConnect", ["player1", False],
        )
        msg = self.client.chat_send.call_args[0][0]
        self.assertIn("Custom", msg)
        self.assertIn("joined", msg)


class TestPlayerDisconnect(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.nicknames = NicknameCache(
            os.path.join(self.tmpdir, "nicks.json"),
            os.path.join(self.tmpdir, "custom.json"),
        )
        self.client = MagicMock()
        self.client.send = AsyncMock()
        self.client.chat_send = AsyncMock()

    async def test_sends_leave_and_keeps_nick(self):
        self.nicknames.set("player1", "$fffCoolPlayer")
        await handle_callback(
            self.client, self.nicknames,
            "ManiaPlanet.PlayerDisconnect", ["player1", ""],
        )
        msg = self.client.chat_send.call_args[0][0]
        self.assertIn("left the server", msg)
        self.assertEqual(self.nicknames.get("player1"), "$fffCoolPlayer")


if __name__ == "__main__":
    unittest.main()
