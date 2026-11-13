import json

from fastapi.testclient import TestClient

from app.errors import FetchBlocked
from app.main import create_app
from tests.conftest import FIXTURES
from tests.test_service import real_service

PAGES = {
    "amazon.in/dp/B0DSKNQW8F": FIXTURES / "amazon_product_s25.html",
    "flipkart.com/search": FIXTURES / "flipkart_search_s25.html",
    "itm09d676ceb930d": FIXTURES / "flipkart_product_s25.html",
    "croma.com": FetchBlocked("croma.com blocked the request: the site answered HTTP 403"),
}


def events(text: str) -> list[tuple[str, dict]]:
    parsed = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        parsed.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return parsed


def client(pages: dict) -> TestClient:
    def builder(settings):
        service = real_service(pages)
        return service, service._readers[0]._fetcher
    return TestClient(create_app(builder))


def test_page_is_served():
    with client(PAGES) as web:
        response = web.get("/")
        assert response.status_code == 200 and "Same product, other shops" in response.text


def test_check_streams_product_then_one_result_per_platform():
    with client(PAGES) as web:
        stream = events(web.get("/check", params={"url": "https://www.amazon.in/dp/B0DSKNQW8F"}).text)
    names = [name for name, _ in stream]
    assert names[0] == "product" and names[-1] == "done" and names.count("result") == 2
    product = stream[0][1]
    assert product["brand"] == "Samsung" and product["model"] == "galaxy s25 ultra 5g"
    assert product["matched_on"] == ["RAM 12 GB", "Storage 256 GB"]
    results = {data["platform"]: data for name, data in stream if name == "result"}
    assert results["flipkart"]["status"] == "in_stock"
    assert results["flipkart"]["url"].startswith("https://www.flipkart.com/")
    assert results["croma"]["status"] == "could_not_check"       # blocked, not "not listed"
    assert "blocked" in results["croma"]["error"] and results["croma"]["url"] is None


def test_unsupported_link_is_reported_not_crashed():
    with client(PAGES) as web:
        stream = events(web.get("/check", params={"url": "https://example.com/x"}).text)
    assert stream[0] == ("failed", {"message": "This is not an Amazon.in product link"})
    assert stream[-1][0] == "done"
