"""
Wordle Solver GUI
Run with:
    python wordle_v2.py --gui
"""

import tkinter as tk
from tkinter import messagebox

from wordle import load_data, cached_feedback, best_guesses


BG = "#121212"
PANEL = "#1e1e1e"
TEXT = "#f5f5f5"
MUTED = "#a8a8a8"
BORDER = "#333333"
GRAY = "#3a3a3c"
YELLOW = "#b59f3b"
GREEN = "#538d4e"


class WordleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Wordle Solver")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.answers, self.guesses = load_data()
        self.candidates = list(self.answers)
        self.history = []
        self.current_guess = ""
        self.colors = [0] * 5

        self.build_ui()
        self.entry.focus_set()
        self.update_candidates()
        self.update_recommendations()

    def label(self, parent, text, size=10, bold=False, color=TEXT):
        return tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=color,
            font=("Segoe UI", size, "bold" if bold else "normal"),
        )

    def build_ui(self):
        outer = tk.Frame(self.root, bg=BG, padx=26, pady=22)
        outer.pack()

        self.label(outer, "WORDLE SOLVER", 22, True).pack()
        self.label(
            outer,
            "Enter your guess below, then click the tiles to match Wordle.",
            9,
            color=MUTED,
        ).pack(pady=(3, 18))

        # Guess input — no Set Guess button.
        input_frame = tk.Frame(outer, bg=BG)
        input_frame.pack()

        self.entry = tk.Entry(
            input_frame,
            width=10,
            justify="center",
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 20, "bold"),
        )
        self.entry.pack(ipady=6)
        self.entry.bind("<KeyRelease>", self.on_typing)
        self.entry.bind("<Return>", lambda e: self.submit_result())

        # Wordle tiles.
        self.tile_frame = tk.Frame(outer, bg=BG)
        self.tile_frame.pack(pady=16)

        self.tiles = []
        for i in range(5):
            button = tk.Button(
                self.tile_frame,
                text="",
                width=3,
                height=1,
                bg=GRAY,
                fg=TEXT,
                activebackground=GRAY,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 18, "bold"),
                command=lambda i=i: self.cycle_tile(i),
            )
            button.grid(row=0, column=i, padx=3)
            self.tiles.append(button)

        self.label(
            outer,
            "Click each tile:  GRAY  →  YELLOW  →  GREEN",
            8,
            color=MUTED,
        ).pack()

        submit = tk.Button(
            outer,
            text="SUBMIT RESULT",
            width=18,
            bg=PANEL,
            fg=TEXT,
            activebackground="#303030",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            command=self.submit_result,
        )
        submit.pack(pady=(14, 18), ipady=5)

        # Always-visible recommendations.
        self.make_section(outer, "🧠  BEST NEXT GUESSES")

        self.label(
            outer,
            "Optimized to minimize expected guesses.",
            8,
            color=MUTED,
        ).pack(anchor="w")

        self.recommendations = tk.Listbox(
            outer,
            width=66,
            height=8,
            bg=PANEL,
            fg=TEXT,
            selectbackground="#333333",
            selectforeground=TEXT,
            highlightthickness=0,
            relief="flat",
            font=("Consolas", 10),
        )
        self.recommendations.pack(pady=(6, 12))

        # Possible answers are hidden until <= 10.
        self.possible_title = self.make_section(
            outer, "🎯  POSSIBLE ANSWERS"
        )
        self.possible_label = self.label(
            outer, "", 9, color=MUTED
        )
        self.possible_label.pack(anchor="w", pady=(0, 4))

        self.possible_box = tk.Text(
            outer,
            width=66,
            height=4,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            highlightthickness=0,
            relief="flat",
            font=("Consolas", 11, "bold"),
        )
        self.possible_box.pack()

        self.bottom = tk.Frame(outer, bg=BG)
        self.bottom.pack(fill="x", pady=(12, 0))

        self.status = self.label(
            self.bottom, "Starting with no guesses entered.", 9, color=MUTED
        )
        self.status.pack(side="left")

        tk.Button(
            self.bottom,
            text="RESET",
            bg=PANEL,
            fg=TEXT,
            activebackground="#303030",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            command=self.reset,
        ).pack(side="right")

        self.possible_title.pack_forget()
        self.possible_label.pack_forget()
        self.possible_box.pack_forget()

    def make_section(self, parent, title):
        frame = tk.Frame(parent, bg=BG)
        # Return label; caller can place/forget it.
        label = self.label(frame, title, 12, True)
        label.pack(anchor="w")
        frame.pack(fill="x", pady=(2, 0))
        return frame

    def on_typing(self, _event=None):
        text = "".join(c for c in self.entry.get().lower() if c.isalpha())[:5]
        if text != self.entry.get():
            self.entry.delete(0, tk.END)
            self.entry.insert(0, text.upper())
        else:
            # Keep displayed input uppercase.
            pos = self.entry.index(tk.INSERT)
            self.entry.delete(0, tk.END)
            self.entry.insert(0, text.upper())
            try:
                self.entry.icursor(min(pos, 5))
            except tk.TclError:
                pass

        self.current_guess = text
        for i in range(5):
            self.tiles[i].config(text=text[i].upper() if i < len(text) else "")
        self.colors = [0] * 5
        self.refresh_tiles()

    def cycle_tile(self, i):
        if len(self.current_guess) != 5:
            return
        self.colors[i] = (self.colors[i] + 1) % 3
        self.refresh_tiles()

    def refresh_tiles(self):
        for i, tile in enumerate(self.tiles):
            state = self.colors[i]
            if state == 0:
                bg, fg = GRAY, TEXT
            elif state == 1:
                bg, fg = YELLOW, "#111111"
            else:
                bg, fg = GREEN, TEXT

            tile.config(
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
            )

    def submit_result(self):
        guess = self.current_guess.strip().lower()

        if len(guess) != 5:
            self.status.config(text="Enter exactly 5 letters.")
            return

        if guess not in self.guesses:
            messagebox.showwarning(
                "Invalid guess",
                f"{guess.upper()} is not in your allowed-guess list.",
            )
            return

        pattern = tuple(self.colors)

        if pattern == (2, 2, 2, 2, 2):
            self.status.config(
                text=f"Solved!  {guess.upper()}  🎉"
            )
            self.history.append((guess, pattern))
            self.candidates = [guess]
            self.update_candidates()
            self.update_recommendations()
            return

        before = len(self.candidates)
        new_candidates = [
            answer for answer in self.candidates
            if cached_feedback(guess, answer) == pattern
        ]

        if not new_candidates:
            messagebox.showwarning(
                "No candidates",
                "Those tile colors produce zero possible answers.\n"
                "Check the result and try again.",
            )
            return

        self.candidates = new_candidates
        self.history.append((guess, pattern))

        self.entry.delete(0, tk.END)
        self.current_guess = ""
        self.colors = [0] * 5
        for tile in self.tiles:
            tile.config(text="")
        self.refresh_tiles()

        self.update_candidates()
        self.update_recommendations()

        self.status.config(
            text=(
                f"{guess.upper()}   "
                f"{''.join(map(str, pattern))}   "
                f"Candidates: {before} → {len(self.candidates)}"
            )
        )

    def update_candidates(self):
        n = len(self.candidates)

        if n <= 10:
            self.possible_title.pack(fill="x", pady=(2, 0))
            self.possible_label.pack(anchor="w", pady=(0, 4))
            self.possible_box.pack(fill="x")

            self.possible_label.config(
                text=f"{n} possible answer{'s' if n != 1 else ''}"
            )
            self.possible_box.config(state="normal")
            self.possible_box.delete("1.0", tk.END)

            if n == 1:
                self.possible_box.insert(
                    "1.0", f"🎯  {self.candidates[0].upper()}"
                )
            else:
                self.possible_box.insert(
                    "1.0",
                    "    ".join(w.upper() for w in self.candidates),
                )
            self.possible_box.config(state="disabled")
        else:
            self.possible_title.pack_forget()
            self.possible_label.pack_forget()
            self.possible_box.pack_forget()

    def update_recommendations(self):
        self.recommendations.delete(0, tk.END)

        if len(self.candidates) == 1:
            guess = self.candidates[0]
            self.recommendations.insert(
                tk.END,
                f"  1. {guess.upper():<8} SOLUTION",
            )
            return

        # Use all legal guesses when the pool is large; once it is small,
        # prioritize actual answer candidates so the UI recommendation is
        # immediately actionable while retaining the information objective.
        restrict = len(self.candidates) <= 50

        scored = best_guesses(
            self.candidates,
            self.guesses,
            limit=8,
            restrict_to_candidates=restrict,
        )

        for rank, (guess, metrics) in enumerate(scored, 1):
            expected, worst, _, neg_entropy = metrics
            entropy = -neg_entropy
            tag = "  ← answer" if guess in self.candidates else ""
            self.recommendations.insert(
                tk.END,
                f"{rank:>2}. {guess.upper():<7}"
                f" expected={expected:>6.2f}"
                f"  worst={worst:>3}"
                f"  info={entropy:>5.2f}{tag}",
            )

    def reset(self):
        self.candidates = list(self.answers)
        self.history.clear()
        self.current_guess = ""
        self.colors = [0] * 5
        self.entry.delete(0, tk.END)

        for tile in self.tiles:
            tile.config(text="", bg=GRAY, fg=TEXT)

        self.update_candidates()
        self.update_recommendations()
        self.status.config(text="Reset. Enter your first guess.")


def launch_gui():
    root = tk.Tk()
    WordleGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
