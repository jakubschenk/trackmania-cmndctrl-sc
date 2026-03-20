import unittest

from formatting import strip_shadow, strip_tm_formatting


class TestStripTmFormatting(unittest.TestCase):
    def test_strips_color_codes(self):
        self.assertEqual(strip_tm_formatting("$fffHello$f00World"), "HelloWorld")

    def test_strips_style_codes(self):
        self.assertEqual(strip_tm_formatting("$oHello$sWorld$z$i"), "HelloWorld")

    def test_strips_link_codes(self):
        self.assertEqual(
            strip_tm_formatting("$l[http://example.com]click here"), "click here"
        )

    def test_handles_empty_string(self):
        self.assertEqual(strip_tm_formatting(""), "")

    def test_passes_through_plain_text(self):
        self.assertEqual(strip_tm_formatting("Hello World"), "Hello World")


class TestStripShadow(unittest.TestCase):
    def test_strips_shadow_at_start(self):
        self.assertEqual(strip_shadow("$s$fffPlayer"), "$fffPlayer")

    def test_strips_shadow_mid_string(self):
        self.assertEqual(strip_shadow("$fffHello$sWorld"), "$fffHelloWorld")

    def test_strips_uppercase_S(self):
        self.assertEqual(strip_shadow("$S$fffPlayer"), "$fffPlayer")

    def test_preserves_escaped_dollar_s(self):
        self.assertEqual(strip_shadow("$$s text"), "$$s text")

    def test_no_shadow_unchanged(self):
        self.assertEqual(strip_shadow("$fffPlayer"), "$fffPlayer")


if __name__ == "__main__":
    unittest.main()
