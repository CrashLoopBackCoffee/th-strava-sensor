import pathlib

import pytest


@pytest.fixture
def fixture_dir() -> pathlib.Path:
    """Return the path to the fixtures directory."""
    return pathlib.Path(__file__).parent / 'fixtures'
