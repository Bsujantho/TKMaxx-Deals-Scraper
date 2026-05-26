import unittest

from tkmaxx_deals import Product, compute_discount, find_best_deals_by_brand, parse_prices


class PriceParsingTests(unittest.TestCase):
    def test_parse_single_price(self) -> None:
        self.assertEqual(parse_prices("\u00a324.99"), (24.99, None))

    def test_parse_rrp_then_sale(self) -> None:
        self.assertEqual(parse_prices("RRP \u00a3100 \u00a339.99"), (39.99, 100.0))

    def test_parse_was_then_now_with_commas(self) -> None:
        self.assertEqual(
            parse_prices("Was \u00a31,200.00 Now \u00a3899.50"),
            (899.5, 1200.0),
        )

    def test_parse_reversed_prices(self) -> None:
        self.assertEqual(parse_prices("Now \u00a339.99 RRP \u00a3100"), (39.99, 100.0))

    def test_compute_discount(self) -> None:
        self.assertEqual(compute_discount(39.99, 100.0), 60.01)
        self.assertIsNone(compute_discount(None, 100.0))
        self.assertIsNone(compute_discount(10.0, None))
        self.assertIsNone(compute_discount(10.0, 0.0))


class DealSelectionTests(unittest.TestCase):
    def test_find_best_deal_per_brand(self) -> None:
        products = [
            Product("Brand A", "Small discount", 90.0, 100.0, 10.0, "https://example/a", "cat"),
            Product("Brand A", "Big discount", 40.0, 100.0, 60.0, "https://example/b", "cat"),
            Product("Brand B", "No RRP", 25.0, None, None, "https://example/c", "cat"),
            Product("Brand C", "Deal", 50.0, 100.0, 50.0, "https://example/d", "cat"),
        ]

        result = find_best_deals_by_brand(products)

        self.assertEqual([item.brand for item in result], ["Brand A", "Brand C"])
        self.assertEqual(result[0].name, "Big discount")


if __name__ == "__main__":
    unittest.main()
