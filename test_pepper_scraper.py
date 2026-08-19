import unittest

from pepper_scraper import Deal, parse_deals


HTML = """
<article data-t="thread">
  <img class="thread-image" src="https://example.test/image.jpg">
  <button class="cept-vote-temp"><span>321°</span></button>
  <a data-t="threadLink" title="Testowa okazja" href="https://example.test/deal">link</a>
  <span class="thread-price">19,99 zł</span>
</article>
<article data-t="thread">
  <a data-t="threadLink" title="Darmowa rzecz" href="https://example.test/free">link</a>
  <button class="cept-vote-temp"><span>250°</span></button>
</article>
"""


class ParseDealsTest(unittest.TestCase):
    def test_parses_and_limits_deals(self) -> None:
        self.assertEqual(
            parse_deals(HTML, limit=1),
            [
                Deal(
                    "Testowa okazja",
                    "https://example.test/deal",
                    "321°",
                    "19,99 zł",
                    "https://example.test/image.jpg",
                )
            ],
        )

    def test_price_is_optional(self) -> None:
        self.assertEqual(parse_deals(HTML)[1].price, "")

    def test_reads_image_url(self) -> None:
        self.assertEqual(parse_deals(HTML)[0].image_url, "https://example.test/image.jpg")


if __name__ == "__main__":
    unittest.main()
