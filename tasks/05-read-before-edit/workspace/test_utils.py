import unittest
from utils import (
    capitalize_words,
    count_words,
    reverse_string,
    slugify,
    trim_spaces,
    truncate,
)


class TestUtils(unittest.TestCase):
    def test_capitalize_words(self):
        self.assertEqual(capitalize_words("hello world"), "Hello World")

    def test_trim_spaces(self):
        self.assertEqual(trim_spaces("  hello   world  "), "hello world")

    def test_reverse_string(self):
        self.assertEqual(reverse_string("abc"), "cba")

    def test_truncate(self):
        self.assertEqual(truncate("hello world", 5), "hello")
        self.assertEqual(truncate("hi", 5), "hi")

    def test_count_words(self):
        self.assertEqual(count_words("one two three"), 3)

    def test_slugify(self):
        self.assertEqual(slugify("Hello World"), "hello-world")
        self.assertEqual(slugify("  some   text  here "), "some-text-here")
        self.assertEqual(slugify("Python 3.13"), "python-3-13")


if __name__ == "__main__":
    unittest.main()
