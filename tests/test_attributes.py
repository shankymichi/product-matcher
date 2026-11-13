import pytest

from app.attributes import all_attributes
from app.models import Decision

A = all_attributes()


@pytest.mark.parametrize("title, ram, storage", [
    ("Samsung Galaxy S25 Ultra 5G (Titanium Black, 256 GB) (12 GB RAM)", 12, 256),
    ("SAMSUNG Galaxy S25 Ultra 5G (12GB RAM, 256GB, Titanium Silverblue)", 12, 256),
    ("Samsung Galaxy M08 LTE (Silver, 4GB RAM, 64GB Storage), 6000mAh Battery", 4, 64),
    ("Samsung Galaxy S25 Ultra 5G (Titanium Gray, 1 TB) (12 GB RAM)", 12, 1024),
    ("Samsung Galaxy F08 (Dark Blue, 64 GB)", None, 64),
])
def test_ram_and_storage_from_titles(title, ram, storage):
    assert A["ram_gb"].extract(title, {}) == ram
    assert A["storage_gb"].extract(title, {}) == storage


def test_search_highlights_supply_missing_ram():
    specs = {"highlights": "4 GB RAM | 64 GB ROM | Expandable Upto 2 TB"}
    assert A["ram_gb"].extract("Samsung Galaxy F08 (Dark Blue, 64 GB)", specs) == 4
    assert A["storage_gb"].extract("Samsung Galaxy F08 (Dark Blue, 64 GB)", specs) == 64


def test_amazon_spec_table_wins_over_title():
    specs = {"RAM Memory Installed Size": "12 GB", "Memory Storage Capacity": "256 GB",
             "Flash Memory Supported Size Maximum": "512 GB"}
    assert A["ram_gb"].extract("some title", specs) == 12
    assert A["storage_gb"].extract("some title", specs) == 256


@pytest.mark.parametrize("text, size", [
    ("Samsung 138 cm (55 inches) Crystal 4K Smart LED TV", 55),
    ("SAMSUNG Crystal 4K 108 cm (43 inch) Ultra HD LED TV", 43),
    ("LG 139 cm OLED TV", 55),
    ('Sony Bravia 65" 4K TV', 65),
])
def test_screen_size(text, size):
    assert A["screen_inches"].extract(text, {}) == size


def test_exact_fields_compare():
    spec = A["storage_gb"]
    assert spec.compare(256, 256) is Decision.MATCH
    assert spec.compare(256, 512) is Decision.MISMATCH
    assert spec.compare(256, None) is Decision.UNCLEAR


@pytest.mark.parametrize("source, candidate, verdict", [
    ("Core Black", "Black", Decision.MATCH),
    ("Titanium Black", "Titanium Silverblue", Decision.MISMATCH),
    ("Off White", "White", Decision.MATCH),
    ("Navy Blue", "Blue", Decision.MATCH),
    ("White / Grey", "Grey / White", Decision.UNCLEAR),
    ("Black", "", Decision.UNCLEAR),
])
def test_colour(source, candidate, verdict):
    spec = A["colour"]
    assert spec.compare(spec.extract("", {"Colour": source}),
                        spec.extract("", {"Colour": candidate})) is verdict
