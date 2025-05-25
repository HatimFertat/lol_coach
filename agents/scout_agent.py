from agents.base_agent import Agent
from game_context.game_state import GameStateContext
from typing import Tuple, Optional, List, Dict, Any
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import logging
from agents.modelnames import get_model_config
from openai import OpenAI

load_dotenv()

class ScoutAgent(Agent):
    def __init__(self):
        self.conversation_history = []
        self.model_name = "gemini"  # Default model
        self.riot_client = RiotAPIClient()
        self.riot_mcp = RiotMCP()
        self.logger = logging.getLogger(__name__)

    def set_model(self, model_name: str):
        """Set the model to use for this agent."""
        self.model_name = model_name

    def _get_client(self):
        """Get the OpenAI client configured for the selected model."""
        config = get_model_config(self.model_name)
        if not config:
            raise ValueError(f"Model {self.model_name} is not available")
            
        return OpenAI(
            api_key=os.getenv(config.api_key_env),
            base_url=config.base_url
        )

    def _get_model_name(self):
        """Get the model name to use for the selected model."""
        config = get_model_config(self.model_name)
        if not config:
            raise ValueError(f"Model {self.model_name} is not available")
        return config.model_name

    def find_similar_matches(self, game_state: GameStateContext, time_window: int = 120) -> List[Dict]:
        """
        Find matches with similar champion configurations around the current game time.
        
        Args:
            game_state: Current game state
            time_window: Time window in seconds to look around the current timestamp
            
        Returns:
            List of similar matches with their relevant data
        """
        # Get champion configurations from current game
        our_champions = {lane: champ.name for lane, champ in game_state.player_team.champions.items()}
        enemy_champions = {lane: champ.name for lane, champ in game_state.enemy_team.champions.items()}
        
        # Get match IDs from a high-elo player
        puuid = os.getenv("RIOT_PUUID")  # You'll need to set this in your .env file
        if not puuid:
            return []
            
        match_ids = self.riot_client.get_match_ids_by_puuid(puuid, count=100)
        similar_matches = []
        
        for match_id in match_ids:
            match_details = self.riot_client.get_match_details(match_id)
            match_timeline = self.riot_client.get_match_timeline(match_id)
            
            if not match_details or not match_timeline:
                continue
            
            # Extract champion configurations from the match
            match_champions = {}
            for participant in match_details.get("info", {}).get("participants", []):
                lane = participant.get("individualPosition", "").upper()
                if lane in ["UTILITY"]:
                    lane = "SUPPORT"
                match_champions[lane] = participant.get("championName")
            
            # Calculate match similarity score
            our_match_score = sum(1 for lane, champ in our_champions.items() 
                                if lane in match_champions and match_champions[lane] == champ)
            enemy_match_score = sum(1 for lane, champ in enemy_champions.items() 
                                  if lane in match_champions and match_champions[lane] == champ)
            
            # Check if this match meets our criteria
            if our_match_score == 5 and enemy_match_score >= 1:  # All our team + at least enemy laner
                # Extract relevant data from the time window
                current_time = game_state.timestamp
                time_window_data = self._extract_time_window_data(match_timeline, current_time, time_window)
                
                if time_window_data:
                    similar_matches.append({
                        "match_id": match_id,
                        "our_champions": our_champions,
                        "enemy_champions": enemy_champions,
                        "match_champions": match_champions,
                        "time_window_data": time_window_data,
                        "similarity_score": our_match_score + enemy_match_score
                    })
            
            # If we have enough matches, stop searching
            if len(similar_matches) >= 20:
                break
        
        return similar_matches

    def _extract_time_window_data(self, match_timeline: Dict, current_time: float, time_window: int) -> Optional[Dict]:
        """
        Extract relevant data from the match timeline within the specified time window.
        
        Args:
            match_timeline: Match timeline data
            current_time: Current game time
            time_window: Time window in seconds
            
        Returns:
            Dictionary containing relevant events and data from the time window
        """
        try:
            frames = match_timeline.get("info", {}).get("frames", [])
            relevant_frames = []
            
            for frame in frames:
                frame_time = frame.get("timestamp", 0) / 1000  # Convert to seconds
                if abs(frame_time - current_time) <= time_window:
                    relevant_frames.append(frame)
            
            if not relevant_frames:
                return None
            
            # Extract events and data from relevant frames
            events = []
            objectives = {
                "dragon": [],
                "baron": [],
                "herald": [],
                "turrets": [],
                "inhibitors": []
            }
            
            for frame in relevant_frames:
                for event in frame.get("events", []):
                    event_type = event.get("type")
                    
                    if event_type == "CHAMPION_KILL":
                        events.append({
                            "type": "kill",
                            "time": frame.get("timestamp", 0) / 1000,
                            "killer": event.get("killerId"),
                            "victim": event.get("victimId"),
                            "assists": event.get("assistingParticipantIds", [])
                        })
                    elif event_type == "ELITE_MONSTER_KILL":
                        monster_type = event.get("monsterType", "").lower()
                        if monster_type in objectives:
                            objectives[monster_type].append({
                                "time": frame.get("timestamp", 0) / 1000,
                                "team": event.get("killerTeamId")
                            })
                    elif event_type == "BUILDING_KILL":
                        building_type = event.get("buildingType", "").lower()
                        if building_type in objectives:
                            objectives[building_type].append({
                                "time": frame.get("timestamp", 0) / 1000,
                                "team": event.get("killerTeamId"),
                                "lane": event.get("laneType", "").upper()
                            })
            
            return {
                "events": events,
                "objectives": objectives
            }
            
        except Exception as e:
            logging.error(f"Error extracting time window data: {str(e)}")
            return None

    def analyze_similar_matches(self, similar_matches: List[Dict], game_state: GameStateContext) -> str:
        """
        Analyze similar matches and extract relevant insights.
        
        Args:
            similar_matches: List of similar matches
            game_state: Current game state
            
        Returns:
            Formatted string with insights
        """
        if not similar_matches:
            return "No similar matches found to analyze."

        # Initialize statistics
        stats = {
            "kills": {"our_team": 0, "enemy_team": 0},
            "objectives": {
                "dragon": {"our_team": 0, "enemy_team": 0},
                "baron": {"our_team": 0, "enemy_team": 0},
                "herald": {"our_team": 0, "enemy_team": 0},
                "turrets": {"our_team": 0, "enemy_team": 0},
                "inhibitors": {"our_team": 0, "enemy_team": 0}
            },
            "common_events": []
        }

        # Process each match
        for match in similar_matches:
            time_window_data = match["time_window_data"]
            
            # Process kills
            for event in time_window_data["events"]:
                if event["type"] == "kill":
                    # Determine which team got the kill
                    # This is a simplification - you'll need to map participant IDs to teams
                    team = "our_team" if event["killer"] in [1, 2, 3, 4, 5] else "enemy_team"
                    stats["kills"][team] += 1

            # Process objectives
            for obj_type, events in time_window_data["objectives"].items():
                for event in events:
                    team = "our_team" if event["team"] == 100 else "enemy_team"
                    stats["objectives"][obj_type][team] += 1

        # Calculate averages
        num_matches = len(similar_matches)
        averages = {
            "kills": {
                "our_team": stats["kills"]["our_team"] / num_matches,
                "enemy_team": stats["kills"]["enemy_team"] / num_matches
            },
            "objectives": {
                obj_type: {
                    "our_team": stats["objectives"][obj_type]["our_team"] / num_matches,
                    "enemy_team": stats["objectives"][obj_type]["enemy_team"] / num_matches
                }
                for obj_type in stats["objectives"]
            }
        }

        # Format the analysis
        analysis_lines = [
            f"Analysis of {num_matches} similar matches:",
            "\nKill Statistics:",
            f"Average kills for our team: {averages['kills']['our_team']:.1f}",
            f"Average kills for enemy team: {averages['kills']['enemy_team']:.1f}",
            "\nObjective Control:"
        ]

        for obj_type in stats["objectives"]:
            our_avg = averages["objectives"][obj_type]["our_team"]
            enemy_avg = averages["objectives"][obj_type]["enemy_team"]
            analysis_lines.append(
                f"{obj_type.capitalize()}: Our team {our_avg:.1f} vs Enemy team {enemy_avg:.1f}"
            )

        # Add common patterns or notable events
        if stats["common_events"]:
            analysis_lines.append("\nCommon Patterns:")
            for event in stats["common_events"]:
                analysis_lines.append(f"- {event}")

        return "\n".join(analysis_lines)

    def analyze_game_state(self, game_state: GameStateContext) -> Dict:
        """
        Analyze the current game state and provide insights based on similar matches.
        """
        try:
            # Get similar matches
            similar_matches = self.riot_mcp.get_similar_matches(game_state)
            if not similar_matches:
                return {
                    "status": "error",
                    "message": "No similar matches found"
                }

            # Analyze match data
            analysis = self.riot_mcp.analyze_match_data(similar_matches, game_state)
            if not analysis:
                return {
                    "status": "error",
                    "message": "Failed to analyze match data"
                }

            # Format insights
            insights = self._format_insights(analysis, game_state)
            return {
                "status": "success",
                "data": insights
            }

        except Exception as e:
            self.logger.error(f"Error in analyze_game_state: {str(e)}")
            return {
                "status": "error",
                "message": f"Analysis failed: {str(e)}"
            }

    def _format_insights(self, analysis: Dict, game_state: GameStateContext) -> Dict:
        """
        Format the analysis data into readable insights.
        """
        raw_stats = analysis["raw_stats"]
        averages = analysis["averages"]
        num_matches = analysis["num_matches"]

        # Get current game state
        current_time = game_state.timestamp
        current_kills = {
            "our_team": sum(1 for champ in game_state.player_team.champions.values() if champ.kills > 0),
            "enemy_team": sum(1 for champ in game_state.enemy_team.champions.values() if champ.kills > 0)
        }

        # Format insights
        insights = {
            "match_count": num_matches,
            "kill_comparison": {
                "current": current_kills,
                "average": averages["kills"],
                "difference": {
                    "our_team": current_kills["our_team"] - averages["kills"]["our_team"],
                    "enemy_team": current_kills["enemy_team"] - averages["kills"]["enemy_team"]
                }
            },
            "objectives": {
                obj_type: {
                    "current": raw_stats["objectives"][obj_type],
                    "average": averages["objectives"][obj_type]
                }
                for obj_type in raw_stats["objectives"]
            },
            "common_items": sorted(
                [(item_id, count) for item_id, count in raw_stats["items"].items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]  # Top 5 most common items
        }

        return insights

    def run(self, game_state: Optional[GameStateContext] = None, user_message: str = None, image_path: str = None) -> Tuple[str, str, str]:
        """
        Run the scout agent to analyze similar matches and provide insights.
        
        Args:
            game_state: Current game state
            user_message: Optional user message
            image_path: Optional path to an image
            
        Returns:
            Tuple of (prompt, full_response, curated_response)
        """
        if not game_state:
            return "No game state provided", "Please provide a game state to analyze.", ""

        # Find similar matches
        similar_matches = self.find_similar_matches(game_state)
        
        # Analyze matches
        analysis = self.analyze_similar_matches(similar_matches, game_state)
        
        # Format prompt
        prompt = f"Based on the analysis of similar matches:\n{analysis}"
        if user_message:
            prompt = f"{user_message}\n{prompt}"

        # Get model response
        try:
            client = self._get_client()
            messages = [
                {"role": "system", "content": "You are a League of Legends match analysis expert."},
                {"role": "user", "content": prompt}
            ]
            response = client.chat.completions.create(
                model=self._get_model_name(),
                messages=messages,
                max_tokens=1024
            )
            advice = response.choices[0].message.content
            
            return prompt, advice, advice
        except Exception as e:
            error_msg = f"ScoutAgent Error: {str(e)}"
            return prompt, error_msg, error_msg

if __name__ == "__main__":
    # Test the scout agent
    from game_context.game_state import parse_game_state
    
    with open("data/examples/example_game_state.json", "r") as file:
        game_state_json = json.load(file)
    game_state = parse_game_state(game_state_json)
    
    agent = ScoutAgent()
    prompt, response, curated = agent.run(game_state)
    print(f"Prompt: {prompt}\n\nResponse: {response}") 