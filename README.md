# lol_coach

## Overview
lol_coach is a League of Legends coaching application designed to assist players in improving their gameplay. It provides real-time insights and recommendations using two intelligent agents:

- **MacroAgent**: Offers strategic advice based on the current game state.
- **BuildAgent**: Provides item build recommendations tailored to the player's champion, role, and game context.

The application features a graphical user interface (GUI) for interacting with these agents and supports both live and mock game states for testing and development purposes.

---


## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/HatimFertat/lol_coach.git
   cd lol_coach
   ```

2. Create and activate a virtual environment (choose one):

   - Using **venv** (Python 3.9+):
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate  # On Windows: .venv\Scripts\activate
     ```

   - Using **virtualenv**:
     ```bash
     pip install virtualenv
     virtualenv venv --python=python3.9
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     ```

   - Using **conda**:
     ```bash
     conda create -n lol_coach python=3.9
     conda activate lol_coach
     ```

3. Install the package:
   ```bash
   pip install .
   ```
   


3. Set up environment variables:
   - Create a `.env` file in the root directory.
   - Add the following variable:
     ```
     GEMINI_API_KEY=<your-api-key>
     ```

4. Run the application:
   ```bash
   python main.py
   ```

---

## Usage

1. Launch the application by running `main.py`.
2. Start a League of Legends game (Summoner's rift only for now).
3. Use the GUI to interact with the MacroAgent and BuildAgent:
   - Update button: gets the current game state and runs the agent.
   - Send button: write in chat for additional info.
   - Reset button: Clears chat and history

   - **Macro Agent Tab**: Get strategic advice.
   - **Build Agent Tab**: Receive item build recommendations.
4. (Bonus) Use the "Auto-Reset after Update" option to clear conversation history automatically.

---

## Features
- **MacroAgent**:
  - Summarizes the game state.
  - Provides strategic insights, such as turret status, jungle objectives, and team performance.

- **BuildAgent**:
  - Recommends optimal item builds based on the player's champion, role, and game progress.
  - Fetches builds from lolalytics for accurate and up-to-date recommendations.

- **GUI**:
  - User-friendly interface with tabs for interacting with each agent.
  - Supports mock game states for testing.
  - Auto-reset option for clearing conversation history after updates.

---

## File Structure

```
main.py
pyproject.toml
README.md
agents/
  base_agent.py
  build_agent.py
  macro_agent.py
cache_builds/
examples/
  example_game_state.json
  ...
game_context/
  game_state.py
  game_state_fetcher.py
GUI/
  gui.py
patch_item_data/
  items_15.9.1.json
utils/
  get_item_recipes.py
  lolalytics_client.py
```

- **main.py**: Entry point for the application.
- **agents/**: Contains the MacroAgent and BuildAgent implementations.
- **examples/**: Example game state files for testing.
- **game_context/**: Handles game state parsing and fetching.
- **GUI/**: Implements the graphical user interface.
- **patch_item_data/**: Stores item data for different patches.
- **utils/**: Utility scripts for fetching and processing data.

---

## Development

### Running Tests
1. Use mock game states in the `examples/` directory for testing.
2. Modify the `MOCK` variable in `gui.py` to toggle between live and mock states.
