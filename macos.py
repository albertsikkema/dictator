"""Thin wrappers around the macOS APIs Dictator needs: privacy permissions,
the key event tap, the clipboard and the login item."""

import subprocess

import AVFoundation
import HIServices
import Quartz
import ServiceManagement
from AppKit import NSPasteboard, NSPasteboardItem, NSPasteboardTypeString

ACCESSIBILITY = "Accessibility"
INPUT_MONITORING = "Input Monitoring"
MICROPHONE = "Microphone"

PERMISSIONS = (ACCESSIBILITY, INPUT_MONITORING, MICROPHONE)

SETTINGS_URLS = {
    ACCESSIBILITY: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    INPUT_MONITORING: "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    MICROPHONE: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


def accessibility_granted() -> bool:
    """Whether Dictator may post key events (needed to paste)."""
    return bool(HIServices.AXIsProcessTrusted())


def input_monitoring_granted() -> bool:
    """Whether Dictator may listen to key events (needed for the hotkey)."""
    return bool(Quartz.CGPreflightListenEventAccess())


def microphone_granted() -> bool:
    """Whether Dictator may record from the microphone."""
    status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
        AVFoundation.AVMediaTypeAudio
    )
    return status == AVFoundation.AVAuthorizationStatusAuthorized


def permission_status() -> dict[str, bool]:
    """Whether each permission Dictator needs is granted."""
    return {
        ACCESSIBILITY: accessibility_granted(),
        INPUT_MONITORING: input_monitoring_granted(),
        MICROPHONE: microphone_granted(),
    }


def request_permissions(status: dict[str, bool]) -> None:
    """Ask macOS to prompt for each permission that is not granted.

    macOS prompts only once per permission; after that the user has to
    change it in System Settings (see open_settings).
    """
    if not status[ACCESSIBILITY]:
        HIServices.AXIsProcessTrustedWithOptions({HIServices.kAXTrustedCheckOptionPrompt: True})
    if not status[INPUT_MONITORING]:
        Quartz.CGRequestListenEventAccess()
    if not status[MICROPHONE]:
        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeAudio, lambda granted: None
        )


def open_settings(permission: str) -> None:
    """Open the System Settings pane for a permission."""
    subprocess.run(["open", SETTINGS_URLS[permission]], check=False)


def event_tap_enabled(tap) -> bool:
    """Whether macOS still delivers events to the tap.

    macOS disables a tap whose callback is too slow and does not turn it
    back on.
    """
    return bool(Quartz.CGEventTapIsEnabled(tap))


def enable_event_tap(tap) -> None:
    """Turn a disabled event tap back on."""
    Quartz.CGEventTapEnable(tap, True)


def clipboard_change_count() -> int:
    """Counter that macOS increments whenever the clipboard changes."""
    return NSPasteboard.generalPasteboard().changeCount()


def read_clipboard() -> list[dict]:
    """Snapshot the clipboard: every item, with the data for each of its types."""
    pasteboard = NSPasteboard.generalPasteboard()
    return [
        {kind: item.dataForType_(kind) for kind in item.types()}
        for item in pasteboard.pasteboardItems() or []
    ]


def write_clipboard_text(text: str) -> int:
    """Replace the clipboard with text; returns the new change count."""
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, NSPasteboardTypeString)
    return pasteboard.changeCount()


def restore_clipboard(snapshot: list[dict]) -> None:
    """Put a snapshot from read_clipboard back on the clipboard."""
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    items = []
    for kinds in snapshot:
        item = NSPasteboardItem.alloc().init()
        for kind, data in kinds.items():
            if data is not None:
                item.setData_forType_(data, kind)
        items.append(item)
    if items:
        pasteboard.writeObjects_(items)


def login_item_enabled() -> bool:
    """Whether Dictator is registered to start at login."""
    service = ServiceManagement.SMAppService.mainAppService()
    return service.status() in (
        ServiceManagement.SMAppServiceStatusEnabled,
        ServiceManagement.SMAppServiceStatusRequiresApproval,
    )


def set_login_item(enabled: bool) -> None:
    """Register or unregister Dictator as a login item.

    Raises OSError when macOS refuses, e.g. when running from source
    rather than from the app bundle.
    """
    service = ServiceManagement.SMAppService.mainAppService()
    change = service.registerAndReturnError_ if enabled else service.unregisterAndReturnError_
    ok, error = change(None)
    if not ok:
        raise OSError(str(error))
    if service.status() == ServiceManagement.SMAppServiceStatusRequiresApproval:
        ServiceManagement.SMAppService.openSystemSettingsLoginItems()
