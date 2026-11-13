from pathlib import Path

import pytest

import app.attributes  # noqa: F401  (registers the attribute specs)
import app.matching    # noqa: F401  (registers the matchers)
from app.attributes import all_attributes
from app.categories import CATEGORY_RULES
from app.matching import Describer, MatchEngine, all_matchers
from app.models import RawProduct

FIXTURES = Path(__file__).parent / "fixtures"
RULES = {rule.key: rule for rule in CATEGORY_RULES}

S25_ULTRA = RawProduct(
    platform="amazon", url="https://www.amazon.in/dp/B0DSKNQW8F", brand="Samsung",
    title=("Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB "
           "Storage), 200MP Camera, 5000mAh Ultra Long Battery"),
    category_path=["Electronics", "Mobiles & Accessories", "Smartphones & Basic Mobiles",
                   "Smartphones"],
    specs={"RAM Memory Installed Size": "12 GB", "Memory Storage Capacity": "256 GB",
           "Flash Memory Supported Size Maximum": "256 GB", "Colour": "Titanium Black"})

M08_LTE = RawProduct(
    platform="amazon", url="https://www.amazon.in/dp/B0HJ7Z1M6T", brand="Samsung",
    title=("Samsung Galaxy M08 LTE (Silver, 4GB RAM, 64GB Storage), MediaTek Helio G99+ "
           "(6nm), 50MP Dual Camera, 6000mAh Battery"),
    category_path=["Electronics", "Mobiles & Accessories", "Smartphones & Basic Mobiles",
                   "Smartphones"],
    specs={"RAM Memory Installed Size": "4 GB", "Memory Storage Capacity": "64 GB",
           "Colour": "Silver"})


@pytest.fixture
def describer() -> Describer:
    return Describer(all_attributes())


@pytest.fixture
def engine() -> MatchEngine:
    return MatchEngine(all_attributes(), all_matchers())
