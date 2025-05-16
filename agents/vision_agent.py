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
        self.conversation_history = []

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
        ally_lanes = {c.name: self.lane_mapping.get(c.lane, c.lane) for c in game_state.player_team.champions}
        enemy_lanes = {c.name: self.lane_mapping.get(c.lane, c.lane) for c in game_state.enemy_team.champions}
        
        # Calculate distances for each ally champion
        distances = {}
        for ally in ally_champions:
            # Get enemy champions from different lanes, unless it is the jungler where we will check all enemies
            cross_lane_enemies = [
                enemy for enemy in enemy_champions
                if enemy_lanes[enemy] != ally_lanes[ally]
            ]
            if ally_lanes[ally] == "JUNGLE":
                cross_lane_enemies = enemy_champions
            
            # Calculate distances to cross-lane enemies
            if cross_lane_enemies:
                champ_distances = calculate_champion_distances(
                    positions_xy,
                    ally,
                    cross_lane_enemies
                )
                distances[ally] = champ_distances
        
        return distances

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
        threats_found = False
        # Add game time
        minutes = int(game_state.timestamp) // 60
        seconds = int(game_state.timestamp) % 60
        
        for ally, enemy_distances in distances.items():
            # Get ally's lane to determine threshold
            ally_lane = next((c.lane for c in game_state.player_team.champions if c.name == ally), None)
            threshold = self.threshold_jungler if self.lane_mapping.get(ally_lane) == "JUNGLE" else self.threshold
            
            # Filter enemies within threshold
            threats = {
                enemy: dist for enemy, dist in enemy_distances.items()
                if dist is not None and dist <= threshold
            }
            
            if threats:
                threats_found = True
                # Use "You" if this is the active player
                display_name = "You" if ally == game_state.player_champion else ally
                lines.append(f"\n{display_name} is threatened by:")
                for enemy, distance in sorted(threats.items(), key=lambda x: x[1]):
                    position = positions_str.get(enemy, "Unknown position")
                    lines.append(f"- {enemy} ({distance:.0f} units away) at {position}")
        
        if threats_found:
            lines[0] = f"Game Time: {minutes}:{seconds:02d}"

        return "\n".join(lines) if lines else "No immediate threats detected."

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

        # Get champion lists
        ally_champions = [c.name for c in game_state.player_team.champions]
        enemy_champions = [c.name for c in game_state.enemy_team.champions]
        
        # Get champion positions from minimap
        positions_str, positions_xy = detect_champion_positions(
            image_path, 
            ally_champions, 
            enemy_champions, 
            debug=False
        )
        
        # Calculate distances
        distances = self.get_cross_lane_distances(game_state, ally_champions, enemy_champions, positions_xy)
        
        # Format threats
        threats_str = self.format_threats(game_state, distances, positions_str)
        
        # Create prompt and response
        prompt = "What are the threats?"
        response = threats_str
        
        return prompt, response 