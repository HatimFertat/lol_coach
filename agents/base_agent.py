# base_agent.py

from abc import ABC, abstractmethod
from game_context.game_state import GameStateContext

class Agent(ABC):
    @abstractmethod
    def run(self, game_state: GameStateContext) -> str:
        pass