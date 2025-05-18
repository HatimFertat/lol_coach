from typing import Dict, List, Optional, Tuple
from game_context.game_state import GameStateContext
from vision.champion_detector import detect_champion_positions, calculate_champion_distances

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
        self.threshold = 3000
        self.threshold_jungler = 4000
        self.ally_close_threshold = 1500
        self.conversation_history = []
        self.ally_lanes_to_champion = None
        self.enemy_lanes_to_champion = None

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

        # Create mapping of champion names to their lanes
        if not self.ally_lanes_to_champion:
            self.ally_lanes_to_champion = {self.lane_mapping.get(lane, lane): c.name for lane, c in game_state.player_team.champions.items()}
        if not self.enemy_lanes_to_champion:
            self.enemy_lanes_to_champion = {self.lane_mapping.get(lane, lane): c.name for lane, c in game_state.enemy_team.champions.items()}
        
        # Calculate distances for each ally champion
        distances = {}
        for ally_lane, ally_champion in self.ally_lanes_to_champion.items():
            # Get enemy champions from different lanes, unless it is the jungler where we will check all enemies
            cross_lane_enemies = [
                enemy for lane, enemy in self.enemy_lanes_to_champion.items()
                if lane != ally_lane
            ]
            if ally_lane == "JUNGLE":
                cross_lane_enemies = self.enemy_lanes_to_champion.values()
            
            # Calculate distances to cross-lane enemies
            if cross_lane_enemies:
                champ_distances = calculate_champion_distances(
                    positions_xy,
                    ally_champion,
                    cross_lane_enemies
                )
                distances[ally_champion] = champ_distances
        
        return distances

    def format_ally_is_close(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]]) -> str:
        #check if the active player is close to any ally from another lane in the early game (before first 15 minutes)
        game_time = game_state.timestamp
        if game_time < 900:
            return ""
        if not self.ally_lanes_to_champion:
            self.ally_lanes_to_champion = {self.lane_mapping.get(lane, lane): c.name for lane, c in game_state.player_team.champions.items()}
        lines = []
        for ally_lane, ally_champion in self.ally_lanes_to_champion.items():
            if distances[ally_champion] and ally_champion != game_state.player_champion and distances[ally_champion][game_state.player_champion] < self.ally_close_threshold:
                #if it's the jungler say 'Gank incoming'
                if ally_lane == "JUNGLE":
                    lines.append(f"{ally_champion} is on the way to gank the enemy")
                else:
                    lines.append(f"{ally_champion} is close to you")
        return "\n".join(lines) if lines else ""
        
    def format_threats(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]], positions_str: Dict[str, str]) -> str:
        """
        Format the distances and positions into a readable string, checking against thresholds.
        
        Args:
            game_state: Current game state
            distances: Dictionary of champion distances from get_cross_lane_distances
            positions_str: Dictionary mapping champion names to their position descriptions
            
        Returns:
            Formatted string describing threats to each ally champion
        """
        lines = []
        # Add game time

        
        for ally, enemy_distances in distances.items():
            # Get ally's lane to determine threshold
            ally_lane = next((lane for lane, c in game_state.player_team.champions.items() if c.name == ally), None)
            threshold = self.threshold_jungler if self.lane_mapping.get(ally_lane) == "JUNGLE" else self.threshold
            
            # Filter enemies within threshold
            threats = {
                enemy: dist for enemy, dist in enemy_distances.items()
                if dist is not None and dist <= threshold
            }
            
            if threats:
                # Use "You" if this is the active player
                display_name = "Be careful, You are" if ally == game_state.player_champion else ally + " is"
                lines.append(f"\n{display_name} threatened by:")
                for enemy, distance in sorted(threats.items(), key=lambda x: x[1]):
                    position = positions_str.get(enemy, "Unknown position")
                    lines.append(f"- {enemy} ({distance:.0f} units away) at {position}")
        
        return "\n".join(lines) if lines else ""
    
    def format_my_threats(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]], positions_str: Dict[str, str]) -> str:
        lines = []
        threats = {
            enemy: dist for enemy, dist in distances[game_state.player_champion].items()
            if dist is not None and dist <= self.threshold
        }
        if threats:
            lines.append(f"\nBe careful, you are threatened by:")
            for enemy, distance in sorted(threats.items(), key=lambda x: x[1]):
                position = positions_str.get(enemy, "Unknown position")
                lines.append(f"- {enemy} ({distance:.0f} units away) at {position}")
        return "\n".join(lines) if lines else ""
    

    def run(self, game_state: Optional[GameStateContext] = None, user_message: str = None, image_path: str = None) -> Tuple[str, str]:
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
            return user_message, "Please update the game state first to analyze threats."

        if not image_path:
            return "No minimap available", "Please take a screenshot first to analyze threats."
        
        minutes = int(game_state.timestamp) // 60
        seconds = int(game_state.timestamp) % 60
        time_str = f"Game Time: {minutes}:{seconds:02d}"

        # Get champion lists
        if not self.ally_lanes_to_champion:
            self.ally_lanes_to_champion = {self.lane_mapping.get(lane, lane): c.name for lane, c in game_state.player_team.champions.items()}
        if not self.enemy_lanes_to_champion:
            self.enemy_lanes_to_champion = {self.lane_mapping.get(lane, lane): c.name for lane, c in game_state.enemy_team.champions.items()}
        
        # Get champion positions from minimap
        positions_str, positions_xy = detect_champion_positions(
            image_path, 
            self.ally_lanes_to_champion.values(), 
            self.enemy_lanes_to_champion.values(), 
            debug=False
        )
        
        # Calculate distances
        distances = self.get_cross_lane_distances(game_state, positions_xy)
        distances_allies = calculate_champion_distances(positions_xy, game_state.player_champion, self.ally_lanes_to_champion.values())

        # Format threats
        threats_str = self.format_threats(game_state, distances, positions_str)
        ally_close_str = self.format_ally_is_close(game_state, distances_allies)
        # Create prompt and response
        prompt = user_message + "\n" + "What are the threats?"
        if threats_str or ally_close_str:
            response = time_str + "\n" + threats_str + "\n" + ally_close_str
        else:
            response = ""
        
        return prompt, response 