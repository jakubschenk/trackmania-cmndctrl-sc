import json
import os
import tempfile
import unittest

from nicknames import NicknameCache


def _make_cache(d, nicks=None, custom=None):
    nick_path = os.path.join(d, "nicks.json")
    custom_path = os.path.join(d, "custom.json")
    if nicks:
        with open(nick_path, "w") as f:
            json.dump(nicks, f)
    if custom:
        with open(custom_path, "w") as f:
            json.dump(custom, f)
    return NicknameCache(nick_path, custom_path)


class TestNicknameCache(unittest.TestCase):
    def test_loads_from_json_file(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d, nicks={"player1": "$fffNick1"})
            self.assertEqual(cache.get("player1"), "$fffNick1")

    def test_returns_empty_if_file_missing(self):
        cache = NicknameCache("/nonexistent/path.json", "/nonexistent/custom.json")
        self.assertIsNone(cache.get("anyone"))

    def test_returns_empty_if_invalid_json(self):
        with tempfile.TemporaryDirectory() as d:
            nick_path = os.path.join(d, "nicks.json")
            with open(nick_path, "w") as f:
                f.write("not json{{{")
            cache = NicknameCache(nick_path, os.path.join(d, "custom.json"))
            self.assertIsNone(cache.get("anyone"))

    def test_save_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            cache.set("p1", "$fffNick")
            cache.save()
            with open(os.path.join(d, "nicks.json")) as f:
                data = json.load(f)
            self.assertEqual(data, {"p1": "$fffNick"})

    def test_display_name_with_different_nick(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            cache.set("player1", "$fffCoolName")
            self.assertEqual(
                cache.display_name("player1"), "$fffCoolName$z$s (player1)"
            )

    def test_display_name_bare_login_when_no_nick(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            self.assertEqual(cache.display_name("player1"), "player1")

    def test_display_name_bare_login_when_nick_equals_login(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            cache.set("player1", "$fffplayer1")
            self.assertEqual(cache.display_name("player1"), "player1")


class TestCustomNames(unittest.TestCase):
    def test_custom_name_overrides_display_name(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            cache.set("player1", "$fffOriginal")
            cache.set_custom("player1", "$f00Custom")
            self.assertEqual(
                cache.display_name("player1"), "$f00Custom$z$s (player1)"
            )

    def test_remove_custom_reverts_to_server_nick(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            cache.set("player1", "$fffOriginal")
            cache.set_custom("player1", "$f00Custom")
            cache.remove_custom("player1")
            self.assertEqual(
                cache.display_name("player1"), "$fffOriginal$z$s (player1)"
            )

    def test_save_custom_persists(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d)
            cache.set_custom("p1", "$f00Red")
            cache.save_custom()
            custom_path = os.path.join(d, "custom.json")
            with open(custom_path) as f:
                data = json.load(f)
            self.assertEqual(data, {"p1": "$f00Red"})

    def test_loads_custom_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            cache = _make_cache(d, custom={"p1": "$f00Red"})
            self.assertEqual(cache.get_custom("p1"), "$f00Red")
            self.assertEqual(
                cache.display_name("p1"), "$f00Red$z$s (p1)"
            )


if __name__ == "__main__":
    unittest.main()
