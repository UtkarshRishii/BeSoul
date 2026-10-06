"""Optional UI Automation metadata probe, executed in a short-lived bounded process.

The probe never reads ValuePattern values, text contents, or password contents. Labels and
geometry are untrusted hints for visual grounding; no input is performed through UIA.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import deque


def _element_data(element) -> dict:
    rectangle = element.CurrentBoundingRectangle
    control_type = int(element.CurrentControlType)
    return {"name": str(element.CurrentName or "")[:160], "automation_id": str(element.CurrentAutomationId or "")[:120],
            "class_name": str(element.CurrentClassName or "")[:120],
            "control_type": control_type, "bounds": [int(rectangle.left), int(rectangle.top),
                                                      int(rectangle.right), int(rectangle.bottom)],
            "enabled": bool(element.CurrentIsEnabled), "offscreen": bool(element.CurrentIsOffscreen),
            "focused": bool(element.CurrentHasKeyboardFocus), "password": bool(element.CurrentIsPassword),
            "editable": control_type in {50004, 50030}, "pid": int(element.CurrentProcessId)}


def inspect_window(handle: int) -> dict:
    if os.name != "nt":
        return {"available": False, "elements": [], "reason": "unsupported"}
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    try:
        module = comtypes.client.GetModule("UIAutomationCore.dll")
        automation = comtypes.client.CreateObject(module.CUIAutomation, interface=module.IUIAutomation)
        root = automation.ElementFromHandle(handle)
        walker = automation.ControlViewWalker
        pending = deque([(root, 0)])
        elements = []
        deadline = time.monotonic() + 0.6
        while pending and len(elements) < 120 and time.monotonic() < deadline:
            element, depth = pending.popleft()
            try:
                item = _element_data(element)
                if item["enabled"] and not item["offscreen"] and item["bounds"][2] > item["bounds"][0]:
                    elements.append(item)
                if depth < 5:
                    child = walker.GetFirstChildElement(element)
                    while child and len(pending) < 160 and time.monotonic() < deadline:
                        pending.append((child, depth + 1))
                        child = walker.GetNextSiblingElement(child)
            except Exception:
                continue
        try:
            focused = _element_data(automation.GetFocusedElement())
        except Exception:
            focused = None
        return {"available": True, "elements": elements, "focused": focused,
                "truncated": bool(pending), "source": "windows_uia"}
    finally:
        comtypes.CoUninitialize()


def main() -> None:
    try:
        result = inspect_window(int(sys.argv[1]))
    except Exception:
        result = {"available": False, "elements": [], "reason": "provider_unavailable"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
