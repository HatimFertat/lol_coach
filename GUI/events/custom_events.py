from PySide6.QtCore import QEvent

# Define custom event types
class EventType:
    UpdateText = QEvent.Type(QEvent.registerEventType())
    UpdateGameState = QEvent.Type(QEvent.registerEventType())
    ScreenshotReady = QEvent.Type(QEvent.registerEventType())
    ScreenshotError = QEvent.Type(QEvent.registerEventType())
    BuildAgentTrigger = QEvent.Type(QEvent.registerEventType())
    MacroAgentTrigger = QEvent.Type(QEvent.registerEventType())
    VisionAgentTrigger = QEvent.Type(QEvent.registerEventType())
    TTSStopTrigger = QEvent.Type(QEvent.registerEventType())

class _UpdateTextEvent(QEvent):
    def __init__(self, sender, message, curated_message=None):
        super().__init__(EventType.UpdateText)
        self.sender = sender
        self.message = message
        self.curated_message = curated_message

class _UpdateGameStateEvent(QEvent):
    def __init__(self, prompt, response, curated_response=None):
        super().__init__(EventType.UpdateGameState)
        self.prompt = prompt
        self.response = response
        self.curated_response = curated_response

class _ScreenshotReadyEvent(QEvent):
    def __init__(self, image_path, agent_name):
        super().__init__(EventType.ScreenshotReady)
        self.image_path = image_path
        self.agent_name = agent_name

class _ScreenshotErrorEvent(QEvent):
    def __init__(self, error_msg):
        super().__init__(EventType.ScreenshotError)
        self.error_msg = error_msg 