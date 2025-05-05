# main.py

from game_state import GameStateContext, TeamState, ChampionState, ObjectiveTimers
from agents.build_agent import BuildAgent
from agents.macro_agent import MacroAgent
import time

# Simulated context (stub values)
context = GameStateContext(
    timestamp=time.time(),
    player_champion="Kog'Maw",
    role="ADC",
    player_team=TeamState(
        champions=[ChampionState(name="Kog'Maw", current_gold=1300, items=["Doran's Blade"], lane="Bot", level=8)],
        total_gold=18000,
        towers_destroyed=3,
        dragons_taken=1,
        barons_taken=0,
    ),
    enemy_team=TeamState(
        champions=[ChampionState(name="Lucian", current_gold=900, items=["Long Sword"], lane="Bot", level=8)],
        total_gold=17500,
        towers_destroyed=2,
        dragons_taken=0,
        barons_taken=0,
    ),
    objectives=ObjectiveTimers(dragon_spawn=90, baron_spawn=300)
)

# Instantiate agents
agents = [BuildAgent(), MacroAgent()]

# Run agents
for agent in agents:
    print(agent.run(context))