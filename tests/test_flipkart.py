from app.platforms.flipkart import parse_product, parse_search
from tests.conftest import FIXTURES


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_search_results_carry_title_link_and_highlights():
    listings = parse_search(read("flipkart_search_s25.html"))
    assert len(listings) >= 10
    black = next(l for l in listings if "Titanium Black, 256 GB" in l.title)
    assert black.title == "Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB)"
    assert black.url.startswith("https://www.flipkart.com/samsung-galaxy-s25-ultra-5g")
    assert "pid=MOBH8K8UVNGVNGKN" in black.url and "lid=" not in black.url
    assert "12 GB RAM" in black.specs["highlights"]


def test_in_stock_product_page():
    listing = parse_product(read("flipkart_product_s25.html"), "u")
    assert listing.title == "Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB) (12 GB RAM)"
    assert listing.brand == "Samsung"
    assert listing.specs["colour"] == "Titanium Black"
    assert listing.in_stock is True


def test_unavailable_product_page():
    listing = parse_product(read("flipkart_product_a08_unavailable.html"), "u")
    assert listing.title.startswith("Samsung Galaxy A08 LTE")
    assert listing.in_stock is False
