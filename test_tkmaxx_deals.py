import unittest

from tkmaxx_deals import (
    Product,
    compute_discount,
    find_best_deals_by_brand,
    product_from_bloomreach_doc,
    select_products_for_export,
)


class PriceParsingTests(unittest.TestCase):
    def test_compute_discount(self) -> None:
        self.assertEqual(compute_discount(39.99, 100.0), 60.01)
        self.assertIsNone(compute_discount(None, 100.0))
        self.assertIsNone(compute_discount(10.0, None))
        self.assertIsNone(compute_discount(10.0, 0.0))

    def test_product_from_bloomreach_doc(self) -> None:
        product = product_from_bloomreach_doc(
            {
                "pid": "13028706",
                "title": "Black GG1081S 001 Oversized Sunglasses",
                "brand": "Gucci",
                "price": 99.99,
                "rrp": 350.0,
                "percent_saving": 71,
                "url": "/women/sunglasses/p/13028706",
                "stock": 1421,
                "stock_status": "inStock",
                "mh_dept_name": "Department: 013 SUNGLASSES & OPTICALS",
                "mh_class_name": "Class: 80 GOLD LABEL",
                "thumb_image": "https://example.com/product.jpg",
            },
            source_query="gucci",
        )

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.brand, "Gucci")
        self.assertEqual(product.sale_price, 99.99)
        self.assertEqual(product.original_price, 350.0)
        self.assertEqual(product.discount_pct, 71)
        self.assertEqual(product.department, "013 SUNGLASSES & OPTICALS")
        self.assertEqual(product.product_class, "80 GOLD LABEL")
        self.assertEqual(
            product.url,
            "https://www.tkmaxx.com/uk/en/women/sunglasses/p/13028706",
        )


class DealSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.products = [
            Product("Brand A", "Small discount", 90.0, 100.0, 10.0, "https://example/a", "1", "q"),
            Product("Brand A", "Big discount", 40.0, 100.0, 60.0, "https://example/b", "2", "q"),
            Product("Brand B", "No RRP", 25.0, None, None, "https://example/c", "3", "q"),
            Product("Brand C", "Deal", 50.0, 100.0, 50.0, "https://example/d", "4", "q"),
        ]

    def test_find_best_deal_per_brand(self) -> None:
        result = find_best_deals_by_brand(self.products)

        self.assertEqual([item.brand for item in result], ["Brand A", "Brand C"])
        self.assertEqual(result[0].name, "Big discount")

    def test_select_all_products_for_export(self) -> None:
        result = select_products_for_export(self.products, "all")

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].name, "Big discount")
        self.assertEqual(result[-1].name, "No RRP")

    def test_select_best_by_brand_for_export(self) -> None:
        result = select_products_for_export(self.products, "best-by-brand")

        self.assertEqual([item.brand for item in result], ["Brand A", "Brand C"])


if __name__ == "__main__":
    unittest.main()
