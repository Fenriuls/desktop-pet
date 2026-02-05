from __future__ import annotations
import tkinter as tk
from deskpet.personality import ensure_personality, apply_intro_name, apply_intro_choice


class IntroModal:
    """
    Centered modal, reliable. Freezes the world while open.
    """
    def __init__(self, root: tk.Tk, world):
        self.root = root
        self.world = world
        self.result = None

        self.win = tk.Toplevel(root)
        self.win.title("Welcome to Fenlings")
        self.win.configure(bg="#111111")
        self.win.resizable(False, False)

        # Modal behaviors
        self.win.transient(root)
        self.win.grab_set()
        self.win.focus_force()

        # Layout
        self.stage = 0

        self.title_lbl = tk.Label(self.win, text="A Fenling has appeared.", fg="white", bg="#111111", font=("TkDefaultFont", 12, "bold"))
        self.title_lbl.pack(padx=16, pady=(14, 6))

        self.body_lbl = tk.Label(self.win, text="It looks at you like you owe it rent.", fg="white", bg="#111111", wraplength=360, justify="center")
        self.body_lbl.pack(padx=16, pady=(0, 10))

        self.name_var = tk.StringVar(value=self.world.get_focused().name)
        self.name_entry = tk.Entry(self.win, textvariable=self.name_var, width=28)
        self.name_entry.pack(padx=16, pady=(0, 10))

        self.choice_frame = tk.Frame(self.win, bg="#111111")
        self.choice_frame.pack(padx=16, pady=(0, 10), fill="x")

        self.btn_frame = tk.Frame(self.win, bg="#111111")
        self.btn_frame.pack(padx=16, pady=(0, 14), fill="x")

        self.next_btn = tk.Button(self.btn_frame, text="Next", command=self._next)
        self.next_btn.pack(side="right")

        self.skip_btn = tk.Button(self.btn_frame, text="Skip", command=self._finish)
        self.skip_btn.pack(side="left")

        self._render_stage()

        # Center
        self._center()

    def _center(self):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    def _clear_choices(self):
        for child in list(self.choice_frame.winfo_children()):
            child.destroy()

    def _render_stage(self):
        self._clear_choices()
        self.name_entry.pack_forget()

        if self.stage == 0:
            self.title_lbl.config(text="A Fenling has appeared.")
            self.body_lbl.config(text="It blinks twice. That’s basically a handshake.\n\nWhat will you name it?")
            self.name_entry.pack(padx=16, pady=(0, 10))
            self.name_entry.focus_set()

        elif self.stage == 1:
            self.title_lbl.config(text="First impression")
            self.body_lbl.config(text="Your first move sticks.\n\nHow do you greet your new roommate?")

            # choices
            choices = [
                ("Feed it first (trust +)", "feed"),
                ("Play ball (playful +)", "play"),
                ("Gentle pat (clingy +)", "pet"),
                ("Gentle toss (bold +)", "throw_gentle"),
                ("Ignore it (clingy ++, trust -)", "ignore"),
            ]
            for text, cid in choices:
                b = tk.Button(self.choice_frame, text=text, anchor="w", command=lambda c=cid: self._choose(c))
                b.pack(fill="x", pady=3)

        else:
            self._finish()

    def _choose(self, cid: str):
        self.result = cid
        self._finish()

    def _next(self):
        if self.stage == 0:
            # apply name
            p = self.world.get_focused()
            ensure_personality(p)
            apply_intro_name(p, self.name_var.get())
            self.stage = 1
            self._render_stage()
            self._center()
            return

        self._finish()

    def _finish(self):
        # Apply default if no choice made
        p = self.world.get_focused()
        ensure_personality(p)
        if self.result:
            apply_intro_choice(p, self.result)
        self.win.grab_release()
        self.win.destroy()