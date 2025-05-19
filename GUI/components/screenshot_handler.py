import logging
import os
import threading
from PySide6.QtCore import QObject, Signal, QEvent
from PySide6.QtWidgets import QApplication

from vision.screenshot_listener import take_screenshot_and_crop
from GUI.events.custom_events import EventType, _ScreenshotReadyEvent, _ScreenshotErrorEvent

class ScreenshotHandler(QObject):
    def __init__(self, main_window=None):
        super().__init__()
        self._main_window = main_window
        self._setup_event_handling()
        self.SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'vision', 'screenshots')

    def _setup_event_handling(self):
        # Install event filter to handle screenshot events
        QApplication.instance().installEventFilter(self)

    def set_main_window(self, main_window):
        """Set the main window reference after initialization if needed"""
        self._main_window = main_window

    def take_screenshot(self, agent_name):
        """
        Public method to trigger a screenshot for the specified agent.
        This is called by EventHandlers.
        """
        logging.debug(f"Take screenshot requested for {agent_name}")
        self._trigger_agent_update(agent_name)

    def eventFilter(self, obj, event):
        if event.type() == EventType.MacroAgentTrigger:
            self._trigger_agent_update("MacroAgent")
            return True
        elif event.type() == EventType.VisionAgentTrigger:
            self._trigger_agent_update("VisionAgent")
            return True
        return super().eventFilter(obj, event)

    def _trigger_agent_update(self, agent_name):
        def process_screenshot():
            try:
                # Take a screenshot
                image_path = take_screenshot_and_crop()
                if image_path:
                    # Get a valid receiver for the event
                    receiver = self._get_valid_event_receiver()
                    if receiver:
                        # Post event to notify that screenshot is ready
                        QApplication.instance().postEvent(
                            receiver,
                            _ScreenshotReadyEvent(image_path, agent_name)
                        )
                    else:
                        logging.error("Cannot post screenshot event: No valid receiver")
                else:
                    # Get a valid receiver for the event
                    receiver = self._get_valid_event_receiver()
                    if receiver:
                        # Post event to notify about screenshot error
                        QApplication.instance().postEvent(
                            receiver,
                            _ScreenshotErrorEvent("Failed to take screenshot")
                        )
                    else:
                        logging.error("Cannot post error event: No valid receiver")
            except Exception as e:
                logging.exception(f"Error in process_screenshot for {agent_name}")
                # Get a valid receiver for the event
                receiver = self._get_valid_event_receiver()
                if receiver:
                    # Post event to notify about screenshot error
                    QApplication.instance().postEvent(
                        receiver,
                        _ScreenshotErrorEvent(str(e))
                    )
                else:
                    logging.error(f"Cannot post error event: No valid receiver. Error: {e}")

        # Start screenshot processing in a background thread
        threading.Thread(target=process_screenshot, daemon=True).start()
        
    def _get_valid_event_receiver(self):
        """Return a valid event receiver, prioritizing the stored main window reference"""
        if self._main_window is not None:
            return self._main_window
        
        # Fallback to active window if no main window reference
        active_window = QApplication.instance().activeWindow()
        if active_window is not None:
            return active_window
            
        # Last resort: use the application instance itself
        return QApplication.instance() 