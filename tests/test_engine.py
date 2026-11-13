from dataclasses import replace

import pytest

from app.models import Decision, Listing
from tests.conftest import M08_LTE, RULES, S25_ULTRA

PHONE = RULES["smartphone"]


def candidate(describer, title, rule=PHONE, brand="Samsung", **extra):
    return describer.fill(Listing(platform="flipkart", url="u", title=title, **extra),
                          rule, brand=brand)


@pytest.mark.parametrize("title, verdict", [
    ("Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB) (12 GB RAM)", Decision.MATCH),
    ("SAMSUNG Galaxy S25 Ultra 5G (12GB RAM, 256GB, Titanium Silverblue)", Decision.MATCH),
    ("Samsung Galaxy S25 Ultra 5G (Titanium Black, 512 GB) (12 GB RAM)", Decision.MISMATCH),
    ("Samsung Galaxy S25 5G (Navy, 256 GB) (12 GB RAM)", Decision.MISMATCH),
    ("Samsung Galaxy S25 FE 5G (Black, 256 GB) (12 GB RAM)", Decision.MISMATCH),
    ("Samsung S25 Ultra 5G (Titanium Gray, 256 GB) (12 GB RAM)", Decision.UNCLEAR),
    ("Spigen Case for Samsung Galaxy S25 Ultra 5G", Decision.MISMATCH),
])
def test_s25_ultra_candidates(describer, engine, title, verdict):
    source = describer.fingerprint(S25_ULTRA, PHONE).source
    assert engine.compare(PHONE, source, candidate(describer, title)).decision is verdict


@pytest.mark.parametrize("title", [
    "Samsung Galaxy F08 (Dark Blue, 64 GB) (4 GB RAM)",
    "Samsung Galaxy A08 LTE (Silver, 64 GB) (4 GB RAM)",
    "Samsung Galaxy M07 (Black, 64 GB) (4 GB RAM)",
])
def test_sister_models_with_equal_specs_are_not_the_m08(describer, engine, title):
    source = describer.fingerprint(M08_LTE, PHONE).source
    assert engine.compare(PHONE, source, candidate(describer, title)).decision \
        is Decision.MISMATCH


def test_missing_field_is_reported_not_guessed(describer, engine):
    source = describer.fingerprint(S25_ULTRA, PHONE).source
    result = engine.compare(
        PHONE, source, candidate(describer, "Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB)"))
    assert result.decision is Decision.UNCLEAR and result.missing == ["ram_gb"]


def test_colour_becomes_a_match_field_by_config_alone(describer, engine):
    with_colour = replace(PHONE, must_match=("ram_gb", "storage_gb", "colour"))
    source = describer.fingerprint(S25_ULTRA, with_colour).source
    black = candidate(describer, "Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB) (12 GB RAM)",
                      with_colour)
    blue = candidate(describer, "Samsung Galaxy S25 Ultra 5G (Titanium Silverblue, 256 GB) (12 GB RAM)",
                     with_colour)
    assert engine.compare(with_colour, source, black).decision is Decision.MATCH
    assert engine.compare(with_colour, source, blue).decision is Decision.MISMATCH


def test_model_number_mismatch_is_noted_not_rejected(describer, engine):
    tv = RULES["television"]
    source = describer.fill(Listing(
        platform="amazon", url="a", brand="Samsung", model="crystal 4k vista pro",
        model_code="UA55UE86AFULXL", title="Samsung 138 cm (55 inches) Crystal 4K Vista Pro TV"), tv)
    other = describer.fill(Listing(
        platform="flipkart", url="f", brand="Samsung", model="crystal 4k vista pro",
        model_code="UA55UE81AFULXL", title="SAMSUNG Crystal 4K Vista Pro 138 cm (55 inch) TV"), tv)
    result = engine.compare(tv, source, other)
    assert result.decision is Decision.MATCH
    assert "UA55UE86AFULXL" in result.notes[0] and "UA55UE81AFULXL" in result.notes[0]


@pytest.mark.parametrize("a, b, verdict", [
    ("smash pop", "smash pop", Decision.MATCH),
    ("pop smash", "smash pop", Decision.MATCH),                 # word order is ignored
    ("smashic comfort", "smash comfort", Decision.UNCLEAR),     # 93% alike, different shoe
    ("smashic comfort", "smashic", Decision.UNCLEAR),           # a shorter name
    ("smash v2", "smash v1", Decision.MISMATCH),
    ("574 core", "530", Decision.MISMATCH),
    ("court vision low", "air zoom pegasus running", Decision.MISMATCH),
])
def test_name_matcher(engine, a, b, verdict):
    rule = RULES["sneaker"]
    left = Listing(platform="amazon", url="a", title=a, brand="X", model=a, attributes={"colour": ["white"]})
    right = Listing(platform="myntra", url="m", title=b, brand="X", model=b, attributes={"colour": ["white"]})
    assert engine.compare(rule, left, right).decision is verdict


def test_short_model_code_inside_the_full_model_number(describer, engine):
    tv = RULES["television"]
    source = describer.fill(Listing(
        platform="amazon", url="a", brand="Samsung", model_code="UA55UE81AFULXL",
        title="Samsung 138 cm (55 inches) Crystal 4K Vista Pro Ultra HD Smart LED TV"), tv)
    croma = describer.fill(Listing(
        platform="croma", url="c",
        title="SAMSUNG UE81A 140 cm (55 inch) 4K Ultra HD LED Smart Tizen TV with Alexa (2025 Model)"),
        tv, brand="Samsung")
    result = engine.compare(tv, source, croma)
    assert result.decision is Decision.MATCH and "UE81A" in " ".join(result.reasons)


@pytest.mark.parametrize("a, b, close", [
    ("K-55S30B", "K-55S30", True),        # colour suffix
    ("K-55S30", "K-55S30B", True),
    ("K-43S22BM2", "K-43S22M2", False),   # a different model, not a suffix
    ("K-55S30B", "K-55XR35M2", False),
    ("K-55S30B", "K-55S30B", False),      # equal is not "close"
    ("S30B", "S30", False),               # too short to judge
])
def test_model_numbers_that_differ_only_by_a_suffix(a, b, close):
    from app.matching.normalise import codes_close
    assert codes_close(a, b) is close
