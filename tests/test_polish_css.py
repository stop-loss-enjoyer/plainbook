"""The look rules of the polish batch: focus rings, motion off, tokens."""
import unittest

from plainbook import html


class PolishCss(unittest.TestCase):
    def test_focus_rings_and_reduced_motion(self):
        css = html.CSS
        self.assertIn("a:focus-visible,button:focus-visible", css)
        self.assertIn("input[type=checkbox]:focus-visible", css)
        block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn("transition:none", block)
        self.assertIn("animation:none", block)

    def test_no_long_dashes_in_css(self):
        self.assertFalse(set(html.CSS) & {chr(0x2013), chr(0x2014)})

    def test_vocabulary_checkbox_class(self):
        self.assertIn("label.opt{", html.CSS)
        self.assertRegex(html.CSS, r"\.tile \.value:has\(\.ev\)\{")


if __name__ == "__main__":
    unittest.main()
