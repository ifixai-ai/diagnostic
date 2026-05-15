import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    try:
        markexpr: str = config.option.markexpr or ""
    except AttributeError:
        markexpr = ""
    if "acceptance" not in markexpr:
        skip = pytest.mark.skip(
            reason="acceptance tests are opt-in; run with: pytest -m acceptance"
        )
        for item in items:
            if item.get_closest_marker("acceptance"):
                item.add_marker(skip)
