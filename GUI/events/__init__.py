"""
GUI events package containing custom event types and handlers.
"""

from .custom_events import (
    EventType,
    _UpdateTextEvent,
    _UpdateGameStateEvent,
    _ScreenshotReadyEvent,
    _ScreenshotErrorEvent
)

__all__ = [
    'EventType',
    '_UpdateTextEvent',
    '_UpdateGameStateEvent',
    '_ScreenshotReadyEvent',
    '_ScreenshotErrorEvent'
] 