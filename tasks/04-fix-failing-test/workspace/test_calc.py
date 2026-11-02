import unittest
from calc import media, soma


class TestCalc(unittest.TestCase):
    def test_soma(self):
        self.assertEqual(soma([1, 2, 3]), 6)

    def test_media(self):
        self.assertEqual(media([2, 4, 6]), 4.0)

    def test_media_single(self):
        self.assertEqual(media([10]), 10.0)


if __name__ == "__main__":
    unittest.main()
