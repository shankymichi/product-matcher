import pytest

from app.categories import find_rule
from app.platforms import croma, flipkart, myntra
from app.sources.amazon import asin_of, parse_product
from tests.conftest import FIXTURES


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- Amazon -----------------------------------------------------------------

@pytest.mark.parametrize("url, asin", [
    ("https://www.amazon.in/dp/B0DSKNQW8F", "B0DSKNQW8F"),
    ("https://www.amazon.in/Samsung-Storage-MediaTek/dp/B0HJ7Z1M6T/ref=s9_acsd?pf_rd_m=A21", "B0HJ7Z1M6T"),
    ("amazon.in/dp/B0DSKNQW8F?th=1", "B0DSKNQW8F"),
    ("https://www.amazon.com/dp/B0DSKNQW8F", None),
    ("https://www.flipkart.com/x/p/itm09d676ceb930d", None),
    ("https://www.amazon.in/s?k=phones", None),
])
def test_only_amazon_in_product_links_are_accepted(url, asin):
    assert asin_of(url) == asin


def test_amazon_product_page():
    product = parse_product(read("amazon_product_s25.html"), "u")
    assert product.title.startswith("Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black")
    assert product.brand == "Samsung"
    assert product.category_path[-1] == "Smartphones"
    assert product.specs["RAM Memory Installed Size"] == "12 GB"
    assert product.specs["Memory Storage Capacity"] == "256 GB"
    assert find_rule(product.category_path).key == "smartphone"


@pytest.mark.parametrize("path, key", [
    (["Electronics", "Home Theater, TV & Video", "Televisions", "Smart Televisions"], "television"),
    (["Shoes & Handbags", "Shoes", "Men's Shoes", "Casual Shoes", "Sneakers"], "sneaker"),
    (["Clothing & Accessories", "Men", "T-shirts, Polos & Shirts", "Polos"], "top"),
    (["Clothing & Accessories", "Men", "T-shirts, Polos & Shirts", "Shirts"], None),
    (["Electronics", "Mobiles & Accessories", "Mobile Accessories", "Cases & Covers"], None),
])
def test_category_comes_from_the_deepest_path_element(path, key):
    rule = find_rule(path)
    assert (rule.key if rule else None) == key


# --- Flipkart ---------------------------------------------------------------

def test_flipkart_tv_results_carry_the_model_id():
    listings = flipkart.parse_search(read("flipkart_search_tv.html"))
    vision = next(l for l in listings if l.title.startswith("Samsung Crystal 4K Vision AI 138 cm"))
    assert vision.model_code == "UA55UE83AHULXL"


def test_flipkart_fashion_results_join_brand_and_name():
    sneakers = flipkart.parse_search(read("flipkart_search_sneaker.html"))
    assert sneakers[0].title == "PUMA Smashic Sneakers For Men" and sneakers[0].brand == "PUMA"
    polos = flipkart.parse_search(read("flipkart_search_polo.html"))
    assert polos[0].brand == "U.S. Polo Assn. Denim Co."
    assert polos[0].title.endswith("Men Solid Polo Neck Pure Cotton Brown T-Shirt")


# --- Croma ------------------------------------------------------------------

def test_croma_search_and_product():
    listings = croma.parse_search(read("croma_search_s25.html"))
    assert len(listings) == 16
    assert listings[0].title == "SAMSUNG Galaxy S25 Ultra 5G (12GB RAM, 256GB, Titanium Silverblue)"
    assert listings[0].url == ("https://www.croma.com/samsung-galaxy-s25-ultra-5g-12gb-ram-256gb-"
                               "titanium-silverblue-/p/313330")
    product = croma.parse_product(read("croma_product_s25.html"), listings[0].url)
    assert product.title == listings[0].title and product.in_stock is True


@pytest.mark.parametrize("body, buttons, in_stock", [
    ("Delivery options for 400049", ["Buy Now", "Add to Cart"], True),
    ("Not Available for your pincode", ["Buy Now", "Add to Cart"], False),   # buttons stay
    ("Out of Stock", [], False),
    ("Some page text", ["Notify Me"], False),
])
def test_croma_stock_rules(body, buttons, in_stock):
    assert croma.stock_from(body + " " + " ".join(buttons), buttons) is in_stock


# --- Myntra -----------------------------------------------------------------

def test_myntra_search_and_product():
    listings = myntra.parse_search(read("myntra_search_smash.html"))
    assert len(listings) == 39
    pop = next(l for l in listings if l.url.endswith("/30103226/buy"))
    assert pop.title == "Puma Smash Pop Men Round Toe Sneakers"
    assert pop.brand == "Puma" and pop.specs["colour"] == "White"
    product = myntra.parse_product(read("myntra_product_smash_pop.html"), pop.url)
    assert product.title == pop.title and product.brand == "Puma"
    assert product.specs["colour"] == "White" and product.in_stock is True


def test_croma_product_page_spec_table_gives_brand_and_model_number():
    product = croma.parse_product(read("croma_product_s25.html"), "u")       # full real page
    assert product.brand == "Samsung" and product.model_code == "SM-S938BZBBINS"
    tv = croma.parse_product(read("croma_product_sony_316032.html"), "u")
    assert tv.model_code == "K-43S22BM2" and tv.specs["Model Series"] == "BRAVIA 2 II"
