import copy
import datetime as dt
import unittest

from epic_games import EpicGamesError, parse_free_games


NOW = dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc)


def game():
    return {
        "id": "one", "namespace": "test", "title": "Gra", "offerType": "BASE_GAME",
        "price": {"totalPrice": {"discountPrice": 0, "originalPrice": 1000}},
        "offerMappings": [{"pageType": "productHome", "pageSlug": "gra"}],
        "promotions": {"promotionalOffers": [{"promotionalOffers": [{
            "startDate": "2026-10-09T00:00:00Z", "endDate": "2026-10-11T00:00:00Z",
            "discountSetting": {"discountType": "PERCENTAGE", "discountPercentage": 0},
        }]}]},
    }


def payload(*items):
    return {"data": {"Catalog": {"searchStore": {"elements": list(items)}}}}


class EpicGamesTest(unittest.TestCase):
    def test_active_game_and_duplicate(self):
        item = game()
        result = parse_free_games(payload(item, copy.deepcopy(item)), NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].url, "https://store.epicgames.com/pl/p/gra")
        self.assertEqual(result[0].ends_at, NOW + dt.timedelta(days=1))

    def test_excludes_ineligible_offers(self):
        for variant in ("upcoming", "expired", "paid", "permanent", "dlc", "no_promotions", "partial_discount"):
            with self.subTest(variant=variant):
                item = game()
                offer = item["promotions"]["promotionalOffers"][0]["promotionalOffers"][0]
                if variant == "upcoming":
                    offer["startDate"] = "2026-10-11T00:00:00Z"
                elif variant == "expired":
                    offer["endDate"] = NOW.isoformat()
                elif variant == "paid":
                    item["price"]["totalPrice"]["discountPrice"] = 100
                elif variant == "permanent":
                    item["price"]["totalPrice"]["originalPrice"] = 0
                elif variant == "dlc":
                    item["offerType"] = "DLC"
                elif variant == "partial_discount":
                    offer["discountSetting"]["discountPercentage"] = 50
                else:
                    item["promotions"] = None
                self.assertEqual(parse_free_games(payload(item), NOW), [])

    def test_start_boundary_and_slug_fallback(self):
        item = game()
        item["offerMappings"] = []
        item["productSlug"] = "gra/home"
        result = parse_free_games(payload(item), NOW - dt.timedelta(days=1))
        self.assertEqual(result[0].url, "https://store.epicgames.com/pl/p/gra")

    def test_empty_catalog_and_invalid_response(self):
        self.assertEqual(parse_free_games(payload(), NOW), [])
        for invalid in ({}, {"data": None}, payload(None)):
            with self.assertRaises(EpicGamesError):
                parse_free_games(invalid, NOW)


if __name__ == "__main__":
    unittest.main()
