import tkinter as tk
from tkinter import ttk, scrolledtext
from agents.build_agent import BuildAgent
from agents.macro_agent import MacroAgent
from game_context.game_state import parse_game_state
from game_context.game_state_fetcher import fetch_game_state
import json
import os

MOCK = True

class AgentChatTab:
    def __init__(self, parent, agent, agent_name, get_game_state_func):
        self.agent = agent
        self.agent_name = agent_name
        self.get_game_state_func = get_game_state_func
        self.frame = ttk.Frame(parent)
        self.text_area = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, height=20, width=80, state='disabled')
        self.text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.text_area.tag_configure("user", foreground="blue")
        self.text_area.tag_configure("agent", foreground="green")

        control_frame = ttk.Frame(self.frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.entry = tk.Entry(control_frame, width=60)
        self.entry.grid(row=0, column=0, padx=(0, 5), pady=2, sticky='ew')
        control_frame.columnconfigure(0, weight=1)

        self.send_button = tk.Button(control_frame, text="Send", command=self.send_message)
        self.send_button.grid(row=0, column=1, padx=2)

        self.update_button = tk.Button(control_frame, text="Update", command=self.update_with_game_state)
        self.update_button.grid(row=0, column=2, padx=2)

        self.reset_button = tk.Button(control_frame, text="Clear", command=self.reset_conversation)
        self.reset_button.grid(row=0, column=3, padx=2)

        self.frame.pack(fill=tk.BOTH, expand=True)


    def display_message(self, sender, message):
        self.text_area['state'] = 'normal'
        tag = "user" if sender == "You" else "agent"
        self.text_area.insert(tk.END, f"{sender}: {message}\n", tag)
        self.text_area['state'] = 'disabled'
        self.text_area.see(tk.END)

    def send_message(self):
        try:
            print(f"[DEBUG] send_message called for {self.agent_name}")
            user_message = self.entry.get().strip()
            if not user_message:
                return
            self.display_message("You", user_message)
            self.entry.delete(0, tk.END)
            response = self.agent.run(None, user_message)
            self.display_message(self.agent_name, response)
        except Exception as e:
            print(f"[ERROR] Exception in send_message: {e}")

    def update_with_game_state(self):
        try:
            if self.auto_clear.get():
                self.agent.conversation_history = []
            print(f"[DEBUG] update_with_game_state called for {self.agent_name}")
            user_message = self.entry.get().strip()
            self.entry.delete(0, tk.END)
            game_state = self.get_game_state_func()
            prompt, response = self.agent.run(game_state, user_message)
            self.display_message("You", prompt)
            self.display_message(self.agent_name, response)
        except Exception as e:
            print(f"[ERROR] Exception in update_with_game_state: {e}")

    def clear_conversation(self):
        try:
            print(f"[DEBUG] clear_conversation called for {self.agent_name}")
            self.agent.conversation_history = []
            self.text_area['state'] = 'normal'
            self.text_area.delete(1.0, tk.END)
            self.text_area['state'] = 'disabled'
        except Exception as e:
            print(f"[ERROR] Exception in clear_conversation: {e}")

class LoLCoachGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LoL Coach Agents")
        self.geometry("800x500")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.build_agent = BuildAgent()
        self.macro_agent = MacroAgent()

        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill=tk.X, padx=5, pady=2)

        # Add bottom frame for auto-clear checkbox
        self.auto_clear = tk.BooleanVar(value=False)
        self.auto_clear_checkbox = tk.Checkbutton(mode_frame, text="Auto-Reset after Update", variable=self.auto_clear)
        self.auto_clear_checkbox.pack(side="right", padx=8, pady=6)
        # --- BEGIN: TESTING ONLY ---
        self.use_mock = tk.BooleanVar(value=MOCK)

        ttk.Label(mode_frame, text="Use mock game state").pack(side=tk.LEFT)
        ttk.Checkbutton(mode_frame, variable=self.use_mock).pack(side=tk.LEFT)
        def get_game_state():
            if self.use_mock.get():
                with open(os.path.join(os.path.dirname(__file__), '../examples/example_game_state.json')) as f:
                    game_state_json = json.load(f)
                return parse_game_state(game_state_json)
            else:
                return fetch_game_state()
        # --- END: TESTING ONLY ---
        self.macro_tab = AgentChatTab(self.notebook, self.macro_agent, "MacroAgent", get_game_state)
        self.build_tab = AgentChatTab(self.notebook, self.build_agent, "BuildAgent", get_game_state)
        self.notebook.add(self.macro_tab.frame, text="Macro Agent")
        self.notebook.add(self.build_tab.frame, text="Build Agent")

if __name__ == "__main__":
    app = LoLCoachGUI()
    app.mainloop()
