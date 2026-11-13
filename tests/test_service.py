from app.attributes import all_attributes
from app.errors import FetchBlocked
from app.fetch import FakeFetcher
from app.matching import Describer, MatchEngine, all_matchers
from app.models import Fingerprint, PlatformResult, RawProduct, Status
from app.platforms.flipkart import FlipkartAdapter
from app.service import LookupService
from app.tiebreak import NoTieBreaker
from tests.conftest import FIXTURES, M08_LTE, S25_ULTRA


class FakeAmazon:
    def __init__(self, product: RawProduct) -> None:
        self._product = product

    def can_read(self, url: str) -> bool:
        return "amazon.in" in url

    async def read(self, url: str) -> RawProduct:
        return self._product


def service(product: RawProduct, pages: dict) -> LookupService:
    fetcher = FakeFetcher(pages)
    return LookupService(
        readers=[FakeAmazon(product)], platforms={"flipkart": FlipkartAdapter(fetcher)},
        engine=MatchEngine(all_attributes(), all_matchers()),
        describer=Describer(all_attributes()), tiebreaker=NoTieBreaker())


async def run(svc: LookupService, url: str = "https://www.amazon.in/dp/X"):
    events = [event async for event in svc.check(url)]
    fingerprint = events[0]
    results = {r.platform: r for r in events[1:]}
    assert isinstance(fingerprint, Fingerprint)
    assert all(isinstance(r, PlatformResult) for r in results.values())
    return fingerprint, results


async def test_in_stock_with_link_and_same_colour_preferred():
    fingerprint, results = await run(service(S25_ULTRA, {
        "flipkart.com/search": FIXTURES / "flipkart_search_s25.html",
        "itm09d676ceb930d": FIXTURES / "flipkart_product_s25.html"}))
    assert fingerprint.source.model == "galaxy s25 ultra 5g"
    assert fingerprint.matched_on == ["RAM 12 GB", "Storage 256 GB"]
    assert fingerprint.search_queries[0] == "samsung galaxy s25 ultra 5g 12 gb ram 256 gb"
    flipkart = results["flipkart"]
    assert flipkart.status is Status.IN_STOCK
    assert "Titanium Black, 256 GB" in flipkart.matched_title     # the Amazon colour
    assert flipkart.url.endswith("pid=MOBH8K8UVNGVNGKN")


async def test_not_listed_when_only_sister_models_and_accessories_exist():
    _, results = await run(service(M08_LTE, {
        "flipkart.com/search": FIXTURES / "flipkart_search_m08.html"}))
    assert results["flipkart"].status is Status.NOT_LISTED
    assert results["flipkart"].url is None


async def test_blocked_search_is_could_not_check_never_not_listed():
    _, results = await run(service(S25_ULTRA, {
        "flipkart.com/search": FetchBlocked("flipkart.com blocked the request")}))
    assert results["flipkart"].status is Status.COULD_NOT_CHECK
    assert "blocked" in results["flipkart"].error


async def test_platform_without_an_adapter_is_reported():
    _, results = await run(service(S25_ULTRA, {
        "flipkart.com/search": FIXTURES / "flipkart_search_s25.html",
        "itm09d676ceb930d": FIXTURES / "flipkart_product_s25.html"}))
    assert results["croma"].status is Status.COULD_NOT_CHECK
    assert results["croma"].error == "Croma is not set up yet"


def real_service(pages: dict) -> LookupService:
    """Every real reader and adapter, fed from saved pages instead of the network."""
    from app.platforms import build_platforms
    from app.sources.amazon import AmazonReader
    fetcher = FakeFetcher(pages)
    return LookupService(
        readers=[AmazonReader(fetcher)], platforms=build_platforms(fetcher),
        engine=MatchEngine(all_attributes(), all_matchers()),
        describer=Describer(all_attributes()), tiebreaker=NoTieBreaker())


async def test_phone_end_to_end_from_saved_pages():
    fingerprint, results = await run(real_service({
        "amazon.in/dp/B0DSKNQW8F": FIXTURES / "amazon_product_s25.html",
        "flipkart.com/search": FIXTURES / "flipkart_search_s25.html",
        "itm09d676ceb930d": FIXTURES / "flipkart_product_s25.html",
        "croma.com/searchB": FIXTURES / "croma_search_s25.html",
        "croma.com/samsung-galaxy-s25-ultra-5g-12gb-ram-256gb-titanium-silverblue":
            FIXTURES / "croma_product_s25.html",
    }), "https://www.amazon.in/Samsung-Smartphone/dp/B0DSKNQW8F/ref=sspa_dk?pd_rd_i=B0DSKNQW8F&th=1")

    assert fingerprint.category == "smartphone" and fingerprint.source.brand == "Samsung"
    assert fingerprint.platforms == {"flipkart": "Flipkart", "croma": "Croma"}
    assert results["flipkart"].status is Status.IN_STOCK
    assert "Titanium Black" in results["flipkart"].matched_title
    assert results["croma"].status is Status.IN_STOCK              # other colours only
    assert "Titanium Silverblue" in results["croma"].matched_title
    assert any("pincode" in note for note in results["croma"].notes)


async def test_sneaker_on_myntra_needs_the_same_name_and_colour():
    white_smash_pop = RawProduct(
        platform="amazon", url="https://www.amazon.in/dp/X", brand="Puma",
        title="Puma | Smash Pop Men Round Toe Sneakers",
        category_path=["Shoes & Handbags", "Shoes", "Men's Shoes", "Casual Shoes", "Sneakers"],
        specs={"Colour": "White"})
    fetcher = FakeFetcher({
        "myntra.com/puma-smash-pop": FIXTURES / "myntra_search_smash.html",
        "30103226": FIXTURES / "myntra_product_smash_pop.html"})
    from app.platforms.myntra import MyntraAdapter
    svc = LookupService(
        readers=[FakeAmazon(white_smash_pop)], platforms={"myntra": MyntraAdapter(fetcher)},
        engine=MatchEngine(all_attributes(), all_matchers()),
        describer=Describer(all_attributes()), tiebreaker=NoTieBreaker())
    _, results = await run(svc)
    myntra = results["myntra"]
    assert myntra.status is Status.IN_STOCK
    assert myntra.matched_title == "Puma Smash Pop Men Round Toe Sneakers"
    assert myntra.url.endswith("/30103226/buy")


async def test_a_link_that_is_not_amazon_is_refused():
    import pytest
    from app.errors import UnsupportedLink
    with pytest.raises(UnsupportedLink):
        await run(real_service({}), "https://www.flipkart.com/some/p/itm123")


SONY_BRAVIA_43 = RawProduct(
    platform="amazon", url="https://www.amazon.in/dp/B0F7X29WXX", brand="Sony",
    title=("Sony 108 cm (43 inches) Smartchoice BRAVIA 2M2 Series 4K Ultra HD Smart LED Google TV "
           "K-43S22BM2"),
    category_path=["Electronics", "Home Theater, TV & Video", "Televisions", "Smart Televisions"],
    specs={"Brand": "Sony", "Screen Size": "43 Inches", "Model Number": "K-43S22BM2",
           "model_code": "K-43S22BM2", "Model Series": "Bravia 2M2"})


async def test_tv_named_differently_is_found_by_its_model_number():
    """Amazon: "BRAVIA 2M2 ... K-43S22BM2". Croma: three "BRAVIA 2 II 43 inch" listings
    with different model numbers. Only p/316032 is K-43S22BM2."""
    from app.platforms.croma import CromaAdapter
    fetcher = FakeFetcher({
        "croma.com/searchB": FIXTURES / "croma_search_sony_tv.html",
        "/p/316032": FIXTURES / "croma_product_sony_316032.html",
        "/p/315862": FIXTURES / "croma_product_sony_315862.html",
        "/p/316033": FIXTURES / "croma_product_sony_316033.html"})
    svc = LookupService(
        readers=[FakeAmazon(SONY_BRAVIA_43)], platforms={"croma": CromaAdapter(fetcher)},
        engine=MatchEngine(all_attributes(), all_matchers()),
        describer=Describer(all_attributes()), tiebreaker=NoTieBreaker())
    fingerprint, results = await run(svc)

    assert fingerprint.source.model == "bravia 2m2"          # marketing word and number removed
    croma = results["croma"]
    assert croma.status is Status.IN_STOCK
    assert croma.url.endswith("/p/316032")                    # not the K-43S25M2 or K-43S22M2
    assert "model number equal" in croma.reasons
    assert not any(url.endswith("/p/308023") for url in fetcher.requested)   # 32 inch: never opened


SONY_BRAVIA_3_55 = RawProduct(
    platform="amazon", url="https://www.amazon.in/dp/B0D3DW1CJF", brand="Sony",
    title="Sony BRAVIA 3 Series 139 cm (55 inches) 4K Ultra HD AI Smart LED Google TV K-55S30B (Black)",
    category_path=["Electronics", "Home Theater, TV & Video", "Televisions", "Smart Televisions"],
    specs={"Brand": "Sony", "Screen Size": "55 Inches", "Model Number": "K-55S30B",
           "model_code": "K-55S30B", "Model Series": "3 Series"})


async def test_broad_search_finds_a_tv_the_model_search_misses():
    """Croma returns no Sony TV for "sony bravia 3 55 inch" or "sony bravia 3", but
    lists the 2024 BRAVIA 3 (K-55S30) under "sony 55 inch tv". It cannot be delivered
    to Croma's default pincode, so it is out of stock, with a link. The 2026
    BRAVIA 3 II in the same results is a different generation and is not picked."""
    from app.platforms.croma import CromaAdapter
    fetcher = FakeFetcher({
        "text=sony%20bravia%203": FIXTURES / "croma_search_sony_bravia3_no_sony.html",
        "text=sony%2055%20inch%20tv": FIXTURES / "croma_search_sony_55_tv.html",
        "/p/308065": FIXTURES / "croma_product_sony_308065.html"})
    svc = LookupService(
        readers=[FakeAmazon(SONY_BRAVIA_3_55)], platforms={"croma": CromaAdapter(fetcher)},
        engine=MatchEngine(all_attributes(), all_matchers()),
        describer=Describer(all_attributes()), tiebreaker=NoTieBreaker())
    fingerprint, results = await run(svc)

    assert fingerprint.search_queries == ["sony bravia 3 55 inch", "sony bravia 3", "sony 55 inch tv"]
    croma = results["croma"]
    assert croma.status is Status.OUT_OF_STOCK
    assert croma.url.endswith("/p/308065")
    assert any("differs only by a suffix: K-55S30B on Amazon, K-55S30 here" in n for n in croma.notes)
    assert sum("searchB" in url for url in fetcher.requested) == 3
