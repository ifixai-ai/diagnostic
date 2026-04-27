
from pathlib import Path

import yaml

from ifixai.types import GovernanceGap, RegulatoryFramework, RegulatoryMapping

_MAPPINGS_DIR = Path(__file__).parent

_FRAMEWORK_FILES = [
    "owasp_llm_top10.yaml",
    "nist_ai_rmf.yaml",
    "eu_ai_act.yaml",
    "iso_42001.yaml",
]


def load_all_mappings() -> dict[str, RegulatoryFramework]:
    frameworks: dict[str, RegulatoryFramework] = {}

    for filename in _FRAMEWORK_FILES:
        path = _MAPPINGS_DIR / filename
        if not path.exists():
            continue

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not raw or "mappings" not in raw:
            continue

        framework_name = raw.get("framework", filename)
        version = raw.get("version", "")
        url = raw.get("url", "")

        typed_mappings: dict[str, list[RegulatoryMapping]] = {}
        for test_id, controls in raw["mappings"].items():
            typed_mappings[test_id] = [
                RegulatoryMapping(
                    framework=framework_name,
                    framework_version=version,
                    control_id=c.get("control_id", ""),
                    control_name=c.get("control_name", ""),
                    relevance=c.get("relevance", ""),
                )
                for c in (controls or [])
            ]

        frameworks[framework_name] = RegulatoryFramework(
            framework=framework_name,
            version=version,
            url=url,
            mappings=typed_mappings,
        )

    return frameworks


def get_mappings_for_test(
    test_id: str,
    frameworks: dict[str, RegulatoryFramework] | None = None,
) -> list[RegulatoryMapping]:
    if frameworks is None:
        frameworks = load_all_mappings()

    mappings: list[RegulatoryMapping] = []
    for fw in frameworks.values():
        mappings.extend(fw.mappings.get(test_id, []))
    return mappings


def filter_by_framework(
    gaps: list[GovernanceGap],
    framework_name: str,
    frameworks: dict[str, RegulatoryFramework] | None = None,
) -> list[GovernanceGap]:
    if frameworks is None:
        frameworks = load_all_mappings()

    fw = frameworks.get(framework_name)
    if fw is None:
        return []

    mapped_ids = set(fw.mappings.keys())
    return [g for g in gaps if g.test_id in mapped_ids]
