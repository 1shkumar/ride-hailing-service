import pytest

from app.container import build_container


@pytest.fixture
def container():
    """A fresh, isolated in-memory world for every test."""
    return build_container()
