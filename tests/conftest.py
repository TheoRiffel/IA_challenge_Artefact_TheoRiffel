"""Shared test fixtures."""

from __future__ import annotations

import pytest

from emporio_agente.data.store import StoreData


@pytest.fixture(scope="session")
def store() -> StoreData:
    return StoreData()
