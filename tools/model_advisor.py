"""
Claude Code Model Advisor
Pops up a dialog, you describe your task, it tells you which model to use.
Run via: python tools/model_advisor.py
Or via the desktop shortcut "Which Claude Model?"
"""
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.claude_token_tracker import _classify
from tools.claude_model_router import ModelRouter

MODEL_INFO = {
    "claude-haiku-4-5": {
        "label":   "Haiku 4.5  (fastest, cheapest)",
        "command": "/model haiku",
        "color":   "#10b981",
        "bg":      "#d1fae5",
        "use_for": "Quick searches, validation, simple lookups, small edits",
    },
    "claude-sonnet-4-6": {
        "label":   "Sonnet 4.6  (balanced)",
        "command": "/model sonnet",
        "color":   "#d97706",
        "bg":      "#fef3c7",
        "use_for": "Explanations, code edits, refactoring, medium features",
    },
    "claude-opus-4-7": {
        "label":   "Opus 4.7   (most powerful)",
        "command": "/model opus",
        "color":   "#3b82f6",
        "bg":      "#dbeafe",
        "use_for": "Complex debugging, full features, architecture, review",
    },
}

EXAMPLES = [
    "Fix the bug in inventory.py where qty_after is null",
    "Explain how RLS works in Supabase",
    "Find all files that reference hive_id",
    "Build the shift handover report PDF feature",
    "Validate the schema coverage",
    "Review the XSS hardening for the community page",
]


class AdvisorApp:
    def __init__(self, root):
        self.root = root
        self.router = ModelRouter()
        root.title("Which Claude Model?")
        root.resizable(False, False)
        root.configure(bg="#f8fafc")
        self._build_ui()
        root.update_idletasks()
        # Centre on screen
        w, h = 520, 460
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        pad = {"padx": 20, "pady": 8}

        # Header
        tk.Label(
            self.root, text="Claude Code Model Advisor",
            font=("Segoe UI", 14, "bold"), bg="#f8fafc", fg="#1e293b"
        ).pack(pady=(20, 2))
        tk.Label(
            self.root, text="Describe your task and get the right model instantly.",
            font=("Segoe UI", 10), bg="#f8fafc", fg="#64748b"
        ).pack()

        # Task input
        tk.Label(
            self.root, text="What are you about to do?",
            font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#1e293b", anchor="w"
        ).pack(fill="x", **pad)

        self.task_var = tk.StringVar()
        entry = ttk.Entry(self.root, textvariable=self.task_var, font=("Segoe UI", 11), width=50)
        entry.pack(padx=20, pady=(0, 4), fill="x")
        entry.focus()
        entry.bind("<Return>", lambda e: self._advise())

        # Example chips
        chips_frame = tk.Frame(self.root, bg="#f8fafc")
        chips_frame.pack(padx=20, pady=(0, 8), fill="x")
        tk.Label(chips_frame, text="Examples:", font=("Segoe UI", 9),
                 bg="#f8fafc", fg="#94a3b8").pack(side="left")
        for ex in EXAMPLES[:3]:
            short = ex[:28] + "..." if len(ex) > 28 else ex
            btn = tk.Button(
                chips_frame, text=short, font=("Segoe UI", 8),
                bg="#e2e8f0", fg="#475569", relief="flat", cursor="hand2",
                command=lambda t=ex: self._set_example(t)
            )
            btn.pack(side="left", padx=(4, 0))

        # Advise button
        tk.Button(
            self.root, text="Get Recommendation  →",
            font=("Segoe UI", 11, "bold"),
            bg="#3b82f6", fg="white", relief="flat",
            padx=16, pady=8, cursor="hand2",
            command=self._advise
        ).pack(pady=4)

        # Result panel
        self.result_frame = tk.Frame(self.root, bg="#f8fafc")
        self.result_frame.pack(padx=20, pady=8, fill="x")

        # Detected action label
        self.action_label = tk.Label(
            self.root, text="", font=("Segoe UI", 9),
            bg="#f8fafc", fg="#64748b"
        )
        self.action_label.pack()

    def _set_example(self, text):
        self.task_var.set(text)
        self._advise()

    def _advise(self):
        task = self.task_var.get().strip()
        if not task:
            return

        action = _classify(task)
        model  = self.router.suggest(action)
        info   = MODEL_INFO[model]

        # Clear old result
        for w in self.result_frame.winfo_children():
            w.destroy()

        # Result card
        card = tk.Frame(self.result_frame, bg=info["bg"], bd=0, relief="flat")
        card.pack(fill="x", pady=4)

        tk.Label(
            card, text="Recommended Model",
            font=("Segoe UI", 9), bg=info["bg"], fg="#64748b"
        ).pack(anchor="w", padx=16, pady=(12, 2))

        tk.Label(
            card, text=info["label"],
            font=("Segoe UI", 14, "bold"), bg=info["bg"], fg=info["color"]
        ).pack(anchor="w", padx=16)

        tk.Label(
            card, text=f"Best for: {info['use_for']}",
            font=("Segoe UI", 9), bg=info["bg"], fg="#475569", wraplength=440
        ).pack(anchor="w", padx=16, pady=(2, 4))

        # Command to type
        cmd_frame = tk.Frame(card, bg=info["bg"])
        cmd_frame.pack(fill="x", padx=16, pady=(4, 12))

        tk.Label(
            cmd_frame, text="Type in Claude Code:",
            font=("Segoe UI", 9), bg=info["bg"], fg="#64748b"
        ).pack(side="left")

        cmd_label = tk.Label(
            cmd_frame, text=f"  {info['command']}  ",
            font=("Consolas", 12, "bold"),
            bg="#1e293b", fg="#f0fdf4",
            padx=8, pady=4, cursor="hand2"
        )
        cmd_label.pack(side="left", padx=(8, 0))
        cmd_label.bind("<Button-1>", lambda e: self._copy(info["command"]))

        tk.Label(
            cmd_frame, text="(click to copy)",
            font=("Segoe UI", 8), bg=info["bg"], fg="#94a3b8"
        ).pack(side="left", padx=4)

        self.action_label.config(text=f"Detected action type: {action}")

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)


def main():
    root = tk.Tk()
    AdvisorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
