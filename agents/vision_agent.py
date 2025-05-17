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
        self.ally_lanes = None
        self.enemy_lanes = None

    def get_cross_lane_distances(self, game_state: GameStateContext, ally_champions: List[str], enemy_champions: List[str], positions_xy: Dict[str, Tuple[float, float]]) -> Dict[str, Dict[str, float]]:
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
        if not self.ally_lanes:
            self.ally_lanes = {c.name: self.lane_mapping.get(lane, lane) for lane, c in game_state.player_team.champions.items()}
        if not self.enemy_lanes:
            self.enemy_lanes = {c.name: self.lane_mapping.get(lane, lane) for lane, c in game_state.enemy_team.champions.items()}
        
        # Calculate distances for each ally champion
        distances = {}
        for ally in ally_champions:
            # Get enemy champions from different lanes, unless it is the jungler where we will check all enemies
            cross_lane_enemies = [
                enemy for enemy in self.enemy_champions
                if self.enemy_lanes[enemy] != self.ally_lanes[ally]
            ]
            if self.ally_lanes[ally] == "JUNGLE":
                cross_lane_enemies = self.enemy_champions
            
            # Calculate distances to cross-lane enemies
            if cross_lane_enemies:
                champ_distances = calculate_champion_distances(
                    positions_xy,
                    ally,
                    cross_lane_enemies
                )
                distances[ally] = champ_distances
        
        return distances

    def format_ally_is_close(self, game_state: GameStateContext, distances: Dict[str, Dict[str, float]]) -> str:
        #check if the active player is close to any ally from another lane in the early game (before first 15 minutes)
        game_time = game_state.timestamp
        if game_time < 900:
            return ""
        
        if not self.ally_lanes:
            self.ally_lanes = {c.name: self.lane_mapping.get(lane, lane) for lane, c in game_state.player_team.champions.items()}
        lines = []
        for ally in self.ally_champions:
            if distances[ally] and ally != game_state.player_champion and distances[ally][game_state.player_champion] < self.ally_close_threshold:
                #if it's the jungler say 'Gank incoming'
                if self.ally_lanes[ally] == "JUNGLE":
                    lines.append(f"{ally} is on the way to gank the enemy")
                else:
                    lines.append(f"{ally} is close to you")
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
        response = f"Game Time: {minutes}:{seconds:02d}"

        # Get champion lists
        if not self.ally_champions:
            self.ally_champions = [c.name for c in game_state.player_team.champions]
        if not self.enemy_champions:
            self.enemy_champions = [c.name for c in game_state.enemy_team.champions]
        
        # Get champion positions from minimap
        positions_str, positions_xy = detect_champion_positions(
            image_path, 
            self.ally_champions, 
            self.enemy_champions, 
            debug=False
        )
        
        # Calculate distances
        distances = self.get_cross_lane_distances(game_state, self.ally_champions, self.enemy_champions, positions_xy)
        distances_allies = calculate_champion_distances(positions_xy, game_state.player_champion, self.ally_champions)

        # Format threats
        threats_str = self.format_threats(game_state, distances, positions_str)
        ally_close_str = self.format_ally_is_close(game_state, distances_allies)
        # Create prompt and response
        prompt = user_message + "\n" + "What are the threats?"
        response += threats_str + "\n" + ally_close_str
        
        return prompt, response 