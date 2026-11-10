"""Tests for the macos module (pyobjc frameworks are mocked)."""

from unittest.mock import MagicMock, call

import pytest

import macos


@pytest.fixture
def frameworks(monkeypatch):
    """Replace every framework macos uses with a fresh mock."""
    mocks = {}
    for name in ("AVFoundation", "HIServices", "Quartz", "ServiceManagement", "NSPasteboard"):
        mocks[name] = MagicMock()
        monkeypatch.setattr(macos, name, mocks[name])
    mocks["NSPasteboardItem"] = MagicMock()
    monkeypatch.setattr(macos, "NSPasteboardItem", mocks["NSPasteboardItem"])
    return mocks


def _grant(frameworks, accessibility=True, input_monitoring=True, microphone=True):
    av = frameworks["AVFoundation"]
    frameworks["HIServices"].AXIsProcessTrusted.return_value = accessibility
    frameworks["Quartz"].CGPreflightListenEventAccess.return_value = input_monitoring
    av.AVAuthorizationStatusAuthorized = 3
    av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 3 if microphone else 2


class TestPermissions:
    def test_permission_status_all_granted(self, frameworks):
        _grant(frameworks)
        assert macos.permission_status() == {
            macos.ACCESSIBILITY: True,
            macos.INPUT_MONITORING: True,
            macos.MICROPHONE: True,
        }

    def test_permission_status_reports_each_missing(self, frameworks):
        _grant(frameworks, accessibility=False, microphone=False)
        assert macos.permission_status() == {
            macos.ACCESSIBILITY: False,
            macos.INPUT_MONITORING: True,
            macos.MICROPHONE: False,
        }

    def test_request_permissions_prompts_only_for_missing(self, frameworks):
        macos.request_permissions(
            {macos.ACCESSIBILITY: False, macos.INPUT_MONITORING: True, macos.MICROPHONE: False}
        )
        frameworks["HIServices"].AXIsProcessTrustedWithOptions.assert_called_once()
        frameworks["Quartz"].CGRequestListenEventAccess.assert_not_called()
        frameworks[
            "AVFoundation"
        ].AVCaptureDevice.requestAccessForMediaType_completionHandler_.assert_called_once()

    def test_request_permissions_nothing_missing(self, frameworks):
        macos.request_permissions({name: True for name in macos.PERMISSIONS})
        frameworks["HIServices"].AXIsProcessTrustedWithOptions.assert_not_called()
        frameworks["Quartz"].CGRequestListenEventAccess.assert_not_called()

    def test_open_settings_opens_pane(self, monkeypatch):
        run = MagicMock()
        monkeypatch.setattr(macos.subprocess, "run", run)
        macos.open_settings(macos.INPUT_MONITORING)
        assert run.call_args.args[0] == ["open", macos.SETTINGS_URLS[macos.INPUT_MONITORING]]


class TestEventTap:
    def test_event_tap_enabled(self, frameworks):
        frameworks["Quartz"].CGEventTapIsEnabled.return_value = False
        assert macos.event_tap_enabled("tap") is False

    def test_enable_event_tap(self, frameworks):
        macos.enable_event_tap("tap")
        frameworks["Quartz"].CGEventTapEnable.assert_called_once_with("tap", True)


class TestClipboard:
    def test_read_clipboard_snapshots_all_types(self, frameworks):
        item = MagicMock()
        item.types.return_value = ["public.utf8-plain-text", "public.rtf"]
        item.dataForType_.side_effect = lambda kind: f"data:{kind}"
        pasteboard = frameworks["NSPasteboard"].generalPasteboard.return_value
        pasteboard.pasteboardItems.return_value = [item]

        assert macos.read_clipboard() == [
            {
                "public.utf8-plain-text": "data:public.utf8-plain-text",
                "public.rtf": "data:public.rtf",
            }
        ]

    def test_read_clipboard_empty(self, frameworks):
        pasteboard = frameworks["NSPasteboard"].generalPasteboard.return_value
        pasteboard.pasteboardItems.return_value = None
        assert macos.read_clipboard() == []

    def test_write_clipboard_text_returns_change_count(self, frameworks):
        pasteboard = frameworks["NSPasteboard"].generalPasteboard.return_value
        pasteboard.changeCount.return_value = 42
        assert macos.write_clipboard_text("hello") == 42
        pasteboard.clearContents.assert_called_once()
        assert pasteboard.setString_forType_.call_args.args[0] == "hello"

    def test_restore_clipboard_writes_items(self, frameworks):
        pasteboard = frameworks["NSPasteboard"].generalPasteboard.return_value
        new_item = frameworks["NSPasteboardItem"].alloc.return_value.init.return_value

        macos.restore_clipboard([{"public.rtf": "rtf", "public.png": None}])

        pasteboard.clearContents.assert_called_once()
        new_item.setData_forType_.assert_called_once_with("rtf", "public.rtf")
        pasteboard.writeObjects_.assert_called_once_with([new_item])

    def test_restore_empty_snapshot_clears(self, frameworks):
        pasteboard = frameworks["NSPasteboard"].generalPasteboard.return_value
        macos.restore_clipboard([])
        pasteboard.clearContents.assert_called_once()
        pasteboard.writeObjects_.assert_not_called()

    def test_clipboard_change_count(self, frameworks):
        frameworks["NSPasteboard"].generalPasteboard.return_value.changeCount.return_value = 7
        assert macos.clipboard_change_count() == 7


class TestLoginItem:
    @pytest.fixture
    def service(self, frameworks):
        sm = frameworks["ServiceManagement"]
        sm.SMAppServiceStatusNotRegistered = 0
        sm.SMAppServiceStatusEnabled = 1
        sm.SMAppServiceStatusRequiresApproval = 2
        return sm.SMAppService.mainAppService.return_value

    @pytest.mark.parametrize(("status", "expected"), [(0, False), (1, True), (2, True)])
    def test_login_item_enabled(self, service, status, expected):
        service.status.return_value = status
        assert macos.login_item_enabled() is expected

    def test_set_login_item_registers(self, service):
        service.registerAndReturnError_.return_value = (True, None)
        service.status.return_value = 1
        macos.set_login_item(True)
        service.registerAndReturnError_.assert_called_once_with(None)

    def test_set_login_item_unregisters(self, service):
        service.unregisterAndReturnError_.return_value = (True, None)
        macos.set_login_item(False)
        service.unregisterAndReturnError_.assert_called_once_with(None)

    def test_set_login_item_failure_raises(self, service):
        service.registerAndReturnError_.return_value = (False, "not in a bundle")
        with pytest.raises(OSError, match="not in a bundle"):
            macos.set_login_item(True)

    def test_set_login_item_requires_approval_opens_settings(self, frameworks, service):
        service.registerAndReturnError_.return_value = (True, None)
        service.status.return_value = 2
        macos.set_login_item(True)
        sm = frameworks["ServiceManagement"]
        assert sm.SMAppService.openSystemSettingsLoginItems.call_args_list == [call()]
