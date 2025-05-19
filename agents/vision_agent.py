from typing import Dict, List, Optional, Tuple
from game_context.game_state import GameStateContext, TeamState, ChampionState
from vision.champion_detector import detect_champion_positions, calculate_champion_distances
import logging
import json
from game_context.game_state import parse_game_state

# # Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

class VisionAgent:
    def __init__(self):
        # Lane mapping for bot/support
        self.lane_mapping = {
            "BOTTOM": "BOTTOM",
            "UTILITY": "BOTTOM",
            "MIDDLE": "MIDDLE",
            "TOP": "TOP",
            "JUNGLE": "JUNGLE"
        }
        self.threshold = 4000
        self.threshold_jungler = 3000
        self.ally_close_threshold = 2500
        self.conversation_history = []
    
    def get_my_champion(self, game_state: GameStateContext) -> ChampionState:
        return game_state.player_team.champions[game_state.role]

    def same_lane(self, ally: ChampionState, enemy: ChampionState) -> bool:
        return self.lane_mapping.get(ally.lane) == self.lane_mapping.get(enemy.lane)
    
    def same_role(self, ally: ChampionState, enemy: ChampionState) -> bool:
        return ally.lane == enemy.lane
    
    def get_name_from_role(self, role: str, team: TeamState) -> str:
        return next((c.name for c in team.champions.values() if c.lane == role), None)
    
    def get_names_from_team(self, team: TeamState) -> List[str]:
        return [c.name for c in team.champions.values()]

    def get_cross_lane_distances(self, game_state: GameStateContext, positions_xy: Dict[str, Tuple[float, float]]) -> Dict[str, Dict[str, float]]:
        """
        Calculate distances between each ally champion and enemy champions from different lanes.
        
        Args:
            game_state: Current game state containing champion information
            minimap_path: Path to the minimap screenshot
            
        Returns:
            Tuple containing:
            - Dictionary mapping each ally champion to a dictionary of enemy champions and their distances
            - Formatted string describing threats
        """
        # Calculate distances for each ally champion
        distances = {}
        for ally_role, ally_champion in game_state.player_team.champions.items():
            # Get enemy champions from different lanes, unless it is the jungler where we will check all enemies
            cross_lane_enemies = [
                enemy for role, enemy in game_state.enemy_team.champions.items()
                if not self.same_lane(ally_champion, enemy)
            ]
            if ally_role == "JUNGLE":
                cross_lane_enemies = game_state.enemy_team.champions.values()
            
            # Calculate distances to cross-lane enemies
            if cross_lane_enemies:
                champ_distances = calculate_champion_distances(
                    positions_xy,
                    ally_champion.name,
                    [enemy.name for enemy in cross_lane_enemies]
                )
                distances[ally_champion.name] = champ_distances
        
        return distances

    def format_ally_is_close(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]]) -> str:
        """
        Check if the active player is close to any ally from another lane in the early game (before first 15 minutes)
        distances: distances of allies to my champion (including my champion)
        """
        #check if the active player is close to any ally from another lane in the early game (before first 15 minutes)
        game_time = game_state.timestamp
        if game_time > 900:
            return ""
        lines = []
        for ally_lane, c in game_state.player_team.champions.items():
            ally_champion = c.name
            # Check if ally_champion exists in distances and has distances to other champions
            if (ally_champion in distances and 
                not self.same_lane(c, self.get_my_champion(game_state)) and                             # not the same lane ally
                ally_champion != game_state.player_champion and                                         # not myself
                distances[ally_champion] is not None and
                distances[ally_champion] < self.ally_close_threshold):                                  # close enough
                #if it's the jungler say 'Gank incoming'
                if ally_lane == "JUNGLE":
                    lines.append(f"{ally_champion} is on the way to gank the enemy")
                else:
                    lines.append(f"{ally_champion} is helping you")
        return "\n".join(lines) if lines else ""
        
    def format_ally_threats(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]]) -> str:
        """
        Format the distances and positions into a readable string, checking against thresholds.
        
        Args:
            game_state: Current game state
            distances: Dictionary of champion distances from get_cross_lane_distances
            
        Returns:
            Formatted string describing threats to each ally champion
        """
        game_time = game_state.timestamp
        if game_time > 900:
            return ""
        
        lines = []
        
        for ally, enemy_distances in distances.items():
            if ally == game_state.player_champion:
                continue
            else:
                ally_role = next((role for role, c in game_state.player_team.champions.items() if c.name == ally), None)
                threshold = self.threshold_jungler if self.lane_mapping.get(ally_role) == "JUNGLE" else self.threshold
                
                # Filter enemies within threshold
                threats = {
                    enemy: dist for enemy, dist in enemy_distances.items()
                    if dist is not None and dist <= threshold
                }
                
                if threats:
                    # Use "You" if this is the active player
                    display_name = "Be careful, You are" if ally == game_state.player_champion else ally + " is"
                    lines.append(f"{display_name} threatened by:")
                    for enemy, distance in sorted(threats.items(), key=lambda x: x[1]):
                        lines.append(f"- {enemy} ({distance:.0f} units away)")
            
        return "\n".join(lines) if lines else ""
    
    def format_my_threats(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]]) -> str:
        lines = []
        game_time = game_state.timestamp
        if game_time > 1200:
            return ""

        threshold = self.threshold_jungler if self.lane_mapping.get(game_state.role) == "JUNGLE" else self.threshold
        enemy_distances = distances[game_state.player_champion]
        # Filter enemies within threshold
        threats = {
            enemy: dist for enemy, dist in enemy_distances.items()
            if dist is not None and dist <= threshold
        }
        
        if threats:
            lines.append(f"Be careful!")
            for enemy, distance in sorted(threats.items(), key=lambda x: x[1]):
                lines.append(f"- {enemy} is close, ({distance:.0f} units away)")
        
        return "\n".join(lines) if lines else ""
    
    
    def format_my_jungler_threats(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]]) -> str:
        if game_state.role == "JUNGLE":
            return ""
        game_time = game_state.timestamp
        if game_time > 900:
            return ""

        lines = []
        ally_jungler = self.get_name_from_role('JUNGLE', game_state.player_team)
        enemy_jungler = self.get_name_from_role('JUNGLE', game_state.enemy_team)
        
        enemy_distances = distances[ally_jungler]
        threats = {
            enemy: dist for enemy, dist in enemy_distances.items()
            if dist is not None and dist <= self.threshold_jungler and enemy == enemy_jungler
        }
        if threats:
            lines.append(f"Your jungler {ally_jungler} is in danger:")
            for enemy, distance in sorted(threats.items(), key=lambda x: x[1]):
                lines.append(f"- {enemy} ({distance:.0f} units away)")

        return "\n".join(lines) if lines else ""

    def run(self, game_state: Optional[GameStateContext] = None, user_message: str = None, image_path: str = None) -> Tuple[str, str, str]:
        """
        Main method to run the vision agent.
        
        Args:
            game_state: Current game state
            user_message: Optional user message
            image_path: Path to the minimap screenshot
            
        Returns:
            Tuple containing:
            - Prompt string
            - Response string
        """

        if user_message is not None and game_state is None:
            return user_message, "", ""

        if not image_path:
            return "No minimap available", "", ""
        
        minutes = int(game_state.timestamp) // 60
        seconds = int(game_state.timestamp) % 60
        time_str = f"{minutes}:{seconds:02d}"
        logging.debug(f"Game time: {time_str}")
        
        # Get champion positions from minimap
        try:
            _, positions_xy = detect_champion_positions(
                image_path, 
                self.get_names_from_team(game_state.player_team), 
                self.get_names_from_team(game_state.enemy_team), 
                debug=False
            )
        except Exception as e:
            logging.error(f"Error detecting champion positions: {e}")
            return "Error detecting champion positions", "", ""
        
        # Calculate distances
        distances = self.get_cross_lane_distances(game_state, positions_xy)
        distances_allies = calculate_champion_distances(positions_xy, game_state.player_champion, self.get_names_from_team(game_state.player_team))
        logging.debug(f"Cross lane distances: {distances}")
        logging.debug(f"Ally distances: {distances_allies}")

        # Format threats
        ally_close_str = self.format_ally_is_close(game_state, distances_allies)
        # ally_threats_str = self.format_ally_threats(game_state, distances)
        my_jungler_threats_str = self.format_my_jungler_threats(game_state, distances)
        my_threats_str = self.format_my_threats(game_state, distances)

        # logging.debug(f"Ally threats: {ally_threats_str}")
        logging.debug(f"Ally close: {ally_close_str}")
        logging.debug(f"Jungler threats: {my_jungler_threats_str}")
        logging.debug(f"My threats: {my_threats_str}")

        # Create prompt and response
        prompt = user_message + "\n" + "What are the threats? " + time_str
        if my_threats_str or ally_close_str:
            response = my_threats_str + "\n" + my_jungler_threats_str + "\n" + ally_close_str
        else:
            response = ""
        logging.debug(f"Final response: {response}")
        
        return prompt, response, response
    
if __name__ == "__main__":
    vision_agent = VisionAgent()
    with open("data/examples/with_minimap.json", "r") as file:
        game_state_json = json.load(file)
    img_path = 'data/example_screenshots/20250519_142807_minimap.png'
    game_state = parse_game_state(game_state_json)
    game_state.role = "MIDDLE"

    prompt, response, response_str = vision_agent.run(game_state, "yo", image_path=img_path)
    print(prompt)
    print(response)
    print(response_str)