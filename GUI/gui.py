import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
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
    def __init__(self, parent, agent, agent_name, get_game_state_func, auto_clear_var):
        self.agent = agent
        self.agent_name = agent_name
        self.get_game_state_func = get_game_state_func
        self.auto_clear = auto_clear_var
        self.frame = ttk.Frame(parent)
        self.text_area = scrolledtext.ScrolledText(
            self.frame, wrap=tk.WORD, height=20, width=80, state='disabled',
            font=("Courier New", 14), spacing1=4, spacing3=4
        )
        # Improved appearance for in-game readability
        self.text_area.configure(bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        self.text_area.tag_configure("user", foreground="#a6e22e", font=("Courier New", 14, "bold"))
        self.text_area.tag_configure("agent", foreground="#4fc1ff", font=("Courier New", 14, "bold"))

        control_frame = ttk.Frame(self.frame)

        self.entry = tk.Entry(control_frame, width=60)
        self.entry.grid(row=0, column=0, padx=(0, 5), pady=2, sticky='ew')
        control_frame.columnconfigure(0, weight=1)

        self.send_button = tk.Button(control_frame, text="Send", command=self.send_message)
        self.send_button.grid(row=0, column=1, padx=2)

        self.update_button = tk.Button(control_frame, text="Update", command=self.update_with_game_state)
        self.update_button.grid(row=0, column=2, padx=2)

        self.reset_button = tk.Button(control_frame, text="Clear", command=self.clear_conversation)
        self.reset_button.grid(row=0, column=3, padx=2)

        # Layout using grid to ensure controls are always visible
        self.text_area.pack_forget()
        self.text_area.grid(row=0, column=0, sticky="nsew", padx=5, pady=(5, 0))
        control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.status_label = ttk.Label(self.frame, text="", foreground="orange")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=0)
        self.frame.grid_rowconfigure(2, weight=0)
        self.frame.grid_columnconfigure(0, weight=1)


    def display_message(self, sender, message):
        self.text_area['state'] = 'normal'
        tag = "user" if sender == "You" else "agent"
        self.text_area.insert(tk.END, f"{sender}: {message}\n", tag)
        self.text_area['state'] = 'disabled'
        self.text_area.see(tk.END)

    def send_message(self):
        try:
            logging.debug(f"send_message called for {self.agent_name}")
            user_message = self.entry.get().strip()
            if not user_message:
                return
            self.status_label.config(text="Processing...")
            self.frame.update_idletasks()
            self.display_message("You", user_message)
            self.entry.delete(0, tk.END)
            response = self.agent.run(None, user_message)
            self.display_message(self.agent_name, response)
            self.status_label.config(text="")
        except Exception as e:
            logging.exception("Exception in send_message")
            self.status_label.config(text="Error during processing")

    def update_with_game_state(self):
        try:
            self.status_label.config(text="Fetching and processing game state...")
            self.frame.update_idletasks()
            if self.auto_clear and self.auto_clear.get():
                self.agent.conversation_history = []
            logging.debug(f"update_with_game_state called for {self.agent_name}")
            user_message = self.entry.get().strip()
            self.entry.delete(0, tk.END)
            game_state = self.get_game_state_func()
            prompt, response = self.agent.run(game_state, user_message)
            self.display_message("You", prompt)
            self.display_message(self.agent_name, response)
            self.status_label.config(text="")
        except Exception as e:
            logging.exception("Exception in update_with_game_state")
            self.status_label.config(text="Error during processing")

    def clear_conversation(self):
        try:
            logging.debug(f"clear_conversation called for {self.agent_name}")
            self.agent.conversation_history = []
            self.text_area['state'] = 'normal'
            self.text_area.delete(1.0, tk.END)
            self.text_area['state'] = 'disabled'
        except Exception as e:
            logging.exception("Exception in clear_conversation")

class LoLCoachGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LoL Coach Agents")
        self.geometry("800x500")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill=tk.X, padx=5, pady=2)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.pack_configure(expand=True, fill='both')
        self.build_agent = BuildAgent()
        self.macro_agent = MacroAgent()

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
        self.macro_tab = AgentChatTab(self.notebook, self.macro_agent, "MacroAgent", get_game_state, self.auto_clear)
        self.build_tab = AgentChatTab(self.notebook, self.build_agent, "BuildAgent", get_game_state, self.auto_clear)
        self.notebook.add(self.macro_tab.frame, text="Macro Agent")
        self.notebook.add(self.build_tab.frame, text="Build Agent")

if __name__ == "__main__":
    app = LoLCoachGUI()
    app.mainloop()
