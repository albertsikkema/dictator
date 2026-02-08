"""Shared test fixtures for mocking macOS-specific modules."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_sounddevice():
    """Mock sounddevice module for audio.py tests."""
    mock_sd = MagicMock()
    with patch.dict(sys.modules, {"sounddevice": mock_sd}):
        yield mock_sd


@pytest.fixture
def mock_rumps():
    """Mock rumps module for main.py tests."""
    mock = MagicMock()
    # rumps.App needs to be a proper class for inheritance
    mock.App = type("MockApp", (), {"__init__": lambda self, *a, **kw: None})
    mock.MenuItem = MagicMock
    mock.separator = MagicMock()
    with patch.dict(sys.modules, {"rumps": mock}):
        yield mock


@pytest.fixture
def mock_pynput():
    """Mock pynput module for main.py tests."""
    mock = MagicMock()
    mock_keyboard = MagicMock()
    with patch.dict(
        sys.modules,
        {
            "pynput": mock,
            "pynput.keyboard": mock_keyboard,
        },
    ):
        yield mock, mock_keyboard


@pytest.fixture
def mock_pywhispercpp():
    """Mock pywhispercpp module for transcriber.py tests."""
    mock = MagicMock()
    mock_model_module = MagicMock()
    with patch.dict(
        sys.modules,
        {
            "pywhispercpp": mock,
            "pywhispercpp.model": mock_model_module,
        },
    ):
        yield mock_model_module
