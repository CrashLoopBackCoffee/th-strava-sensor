import pathlib

import pytest

from strava_sensor.fitfile.fitfile import FitFile


@pytest.fixture
def fixture_dir() -> pathlib.Path:
    """Return the path to the fixtures directory."""
    return pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def fitfile_fixture(fixture_dir: pathlib.Path) -> FitFile:
    """Return a parsed FIT file for reuse in tests."""
    return FitFile.from_file(fixture_dir / 'test-1.fit')
