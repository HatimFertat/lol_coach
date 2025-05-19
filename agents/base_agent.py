# base_agent.py

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any, Dict
from game_context.game_state import GameStateContext

class Agent(ABC):
    @abstractmethod
    def run(self, game_state: Optional[GameStateContext] = None, user_message: str = None, image_path: str = None) -> Tuple[str, str, str]:
        """
        Run the agent with the given game state, user message, and optional image path.
        
        Args:
            game_state: The current game state, if available.
            user_message: The user message to process.
            image_path: Path to an image, if available.
            
        Returns:
            Tuple containing:
            - Prompt string used
            - Full response string
            - Curated/summarized response (if applicable)
        """
        pass
    
    def format_prompt(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Format a prompt using the given template and context.
        
        Args:
            template_name: The name of the template to use.
            context: Dictionary of values to format into the template.
            
        Returns:
            The formatted prompt string.
        """
        pass