
from ifixai.types import InspectionCategory

DEFAULT_CATEGORY_WEIGHTS: dict[InspectionCategory, float] = {
    InspectionCategory.FABRICATION: 0.20,
    InspectionCategory.MANIPULATION: 0.35,
    InspectionCategory.DECEPTION: 0.15,
    InspectionCategory.UNPREDICTABILITY: 0.15,
    InspectionCategory.OPACITY: 0.15,
}

STRATEGIC_TEST_IDS: list[str] = [
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B25",
]
