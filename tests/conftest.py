"""Shared test configuration."""

import sys
from unittest.mock import MagicMock

# macOS-only pyobjc frameworks; tests never touch the real ones
for _name in (
    "AppKit",
    "AVFoundation",
    "HIServices",
    "PyObjCTools",
    "Quartz",
    "ServiceManagement",
):
    sys.modules.setdefault(_name, MagicMock())
