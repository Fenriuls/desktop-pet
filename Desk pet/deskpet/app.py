import time
import tkinter as tk
import ctypes

from deskpet.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TICK_MS,
    THROW_MODE, THROW_SMOOTHING,
    THROW_SCALE_GENTLE, MAX_THROW_SPEED_GENTLE,
    THROW_SCALE_YEET, MAX_THROW_SPEED_YEET,
    FOOD_TYPES,
)
from deskpet.world import World
from deskpet.renderer import Renderer
from deskpet.util.mathutil import clamp, dist

from deskpet.intro import IntroModal
from deskpet.dialogue import generate_reply
from deskpet.personality import record_throw

user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_LAYERED = 0x80000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SPI_GETWORKAREA = 0x0030


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)]


class DesktopPetApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Fenlings")

        try:
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if vw <= 0 or vh <= 0:
                raise RuntimeError("Invalid virtual screen metrics")
        except Exception:
            vx, vy = 0, 0
            vw, vh = WINDOW_WIDTH, WINDOW_HEIGHT

        work_area = None
        try:
            r = RECT()
            ok = user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
            if ok:
                work_area = (int(r.left), int(r.top), int(r.right), int(r.bottom))
        except Exception:
            work_area = None

        self.overlay_color = "#ff00ff"
        self.root.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.root.configure(bg=self.overlay_color)

        self.canvas = tk.Canvas(
            self.root,
            width=vw,
            height=vh,
            bg=self.overlay_color,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.world = World(width=vw, height=vh, offset_x=vx, offset_y=vy, work_area=work_area)
        self.renderer = Renderer(self.root)

        self.overlay_on = False
        self.clickthrough_on = False

        self.ui_state = {"craft_menu_open": False, "craft_bounds": None, "craft_buttons": []}

        self._last_hotkey = {}
        self._hotkey_debounce_s = 0.20

        self.dragging = False
        self.drag_ent = None
        self.drag_off_x = 0.0
        self.drag_off_y = 0.0

        self.last_mouse_x = None
        self.last_mouse_y = None
        self.last_mouse_t = None
        self.smoothed_vx = 0.0
        self.smoothed_vy = 0.0

        self._last_cursor_x = None
        self._last_cursor_y = None
        self._last_cursor_t = None

        # Keybinds
        self.root.bind("<F3>", lambda e: self.on_hotkey("f3", self.toggle_overlay))
        self.root.bind("<F2>", lambda e: self.on_hotkey("f2", self.toggle_clickthrough))
        self.root.bind("<Escape>", lambda e: self.on_hotkey("esc", self.quit))

        self.root.bind("1", lambda e: self.on_hotkey("1", lambda: self.select_food_by_index(0)))
        self.root.bind("2", lambda e: self.on_hotkey("2", lambda: self.select_food_by_index(1)))
        self.root.bind("3", lambda e: self.on_hotkey("3", lambda: self.select_food_by_index(2)))

        self.root.bind("c", lambda e: self.on_hotkey("c", self.toggle_craft_menu))
        self.root.bind("C", lambda e: self.on_hotkey("c", self.toggle_craft_menu))

        self.root.bind("b", lambda e: self.on_hotkey("b", self.world.spawn_ball))
        self.root.bind("B", lambda e: self.on_hotkey("b", self.world.spawn_ball))

        # Wave 7
        self.root.bind("i", lambda e: self.on_hotkey("i", self.show_intro))
        self.root.bind("I", lambda e: self.on_hotkey("i", self.show_intro))
        self.root.bind("t", lambda e: self.on_hotkey("t", self.show_chat))
        self.root.bind("T", lambda e: self.on_hotkey("t", self.show_chat))

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)

        self._kb_listener = None
        self._start_global_hotkeys()

        # Start loop
        self.tick()

        # Auto-run intro every launch for now (no save/load)
        self.root.after(150, self.show_intro)

    # -----------------------
    # Hotkeys
    # -----------------------

    def _debounce(self, name: str) -> bool:
        now = time.perf_counter()
        last = self._last_hotkey.get(name, 0.0)
        if (now - last) < self._hotkey_debounce_s:
            return False
        self._last_hotkey[name] = now
        return True

    def on_hotkey(self, name: str, fn):
        if self._debounce(name):
            fn()

    def _start_global_hotkeys(self):
        try:
            from pynput import keyboard
        except Exception:
            print("[hotkeys] pynput not available; global hotkeys disabled.")
            return

        def on_press(key):
            try:
                if key == keyboard.Key.f3:
                    self.root.after(0, lambda: self.on_hotkey("f3", self.toggle_overlay))
                elif key == keyboard.Key.f2:
                    self.root.after(0, lambda: self.on_hotkey("f2", self.toggle_clickthrough))
                elif key == keyboard.Key.esc:
                    self.root.after(0, lambda: self.on_hotkey("esc", self.quit))
            except Exception:
                pass

        self._kb_listener = keyboard.Listener(on_press=on_press)
        self._kb_listener.daemon = True
        self._kb_listener.start()
        print("[hotkeys] Global hotkeys enabled (F2/F3/Esc).")

    # -----------------------
    # Modal utilities (freeze world + ensure typing works)
    # -----------------------

    def _run_modal(self, build_modal_fn):
        prev_paused = self.world.paused
        self.world.paused = True

        prev_clickthrough = self.clickthrough_on
        if prev_clickthrough:
            self._set_clickthrough(False)

        try:
            modal = build_modal_fn()
            # blocks until destroyed
            self.root.wait_window(modal.win if hasattr(modal, "win") else modal)
        finally:
            self.world.paused = prev_paused
            if prev_clickthrough:
                self._set_clickthrough(True)

    def show_intro(self):
        self._run_modal(lambda: IntroModal(self.root, self.world))
        p = self.world.get_focused()
        p.push_bubble("hi.", self.world.time_s, ttl=1.4, priority=60)

    def show_chat(self):
        def build():
            win = tk.Toplevel(self.root)
            win.title("Talk to your Fenling")
            win.configure(bg="#111111")
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()
            win.focus_force()

            lbl = tk.Label(win, text="Say something:", fg="white", bg="#111111")
            lbl.pack(padx=14, pady=(12, 6))

            entry = tk.Entry(win, width=42)
            entry.pack(padx=14, pady=(0, 10))
            entry.focus_set()

            btn_row = tk.Frame(win, bg="#111111")
            btn_row.pack(padx=14, pady=(0, 12), fill="x")

            def send():
                text = entry.get().strip()
                if not text:
                    win.destroy()
                    return
                p = self.world.get_focused()
                reply = generate_reply(self.world, p, text)
                if reply:
                    p.push_bubble(reply, self.world.time_s, ttl=2.4, priority=80)
                win.destroy()

            send_btn = tk.Button(btn_row, text="Send", command=send)
            send_btn.pack(side="right")
            cancel_btn = tk.Button(btn_row, text="Cancel", command=win.destroy)
            cancel_btn.pack(side="left")

            win.bind("<Return>", lambda e: send())

            # center
            win.update_idletasks()
            w = win.winfo_width()
            h = win.winfo_height()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = int((sw - w) / 2)
            y = int((sh - h) / 2)
            win.geometry(f"{w}x{h}+{x}+{y}")

            return win

        self._run_modal(build)

    # -----------------------
    # UI helpers (unchanged)
    # -----------------------

    def toggle_craft_menu(self):
        self.ui_state["craft_menu_open"] = not self.ui_state["craft_menu_open"]
        if self.ui_state["craft_menu_open"]:
            self.world.get_focused().push_bubble("crafting…", self.world.time_s, ttl=1.0, priority=70)

    def _point_in_rect(self, x, y, r):
        x1, y1, x2, y2 = r
        return (x1 <= x <= x2) and (y1 <= y <= y2)

    def _hotbar_hit(self, x, y):
        slots = self.renderer.hotbar_layout(self.world)
        for s in slots:
            if (s["x1"] <= x <= s["x2"]) and (s["y1"] <= y <= s["y2"]):
                return s
        return None

    def _craft_menu_hit(self, x, y):
        if not self.ui_state.get("craft_menu_open", False):
            return None
        btns = self.ui_state.get("craft_buttons", [])
        for b in btns:
            if (b["x1"] <= x <= b["x2"]) and (b["y1"] <= y <= b["y2"]):
                return b
        return None

    def select_food_by_index(self, idx: int):
        kinds = list(FOOD_TYPES.keys())[:3]
        if 0 <= idx < len(kinds):
            self.world.set_selected_food(kinds[idx])

    # -----------------------
    # Picking / focus / dragging
    # -----------------------

    def _hit_entity(self, ent, x, y) -> bool:
        half_w = max(18.0, float(ent.w) * 0.5)
        half_h = max(18.0, float(ent.h) * 0.5)
        return (abs(x - ent.x) <= half_w) and (abs(y - ent.y) <= half_h)

    def _pick_entity_under_cursor(self, x, y):
        for e in reversed(self.world.enemies):
            if self._hit_entity(e, x, y):
                return e
        for b in reversed(getattr(self.world, "toys", [])):
            if dist(x, y, b.x, b.y) <= (b.r + 8):
                return b
        for p in reversed(self.world.fenlings):
            if self._hit_entity(p, x, y):
                return p
        return None

    def on_left_click(self, e):
        x, y = float(e.x), float(e.y)

        if self.ui_state.get("craft_menu_open", False):
            hit = self._craft_menu_hit(x, y)
            if hit:
                kind = hit["kind"]
                ok = self.world.try_craft_food(kind)
                if ok:
                    self.world.set_selected_food(kind)
                return
            bounds = self.ui_state.get("craft_bounds")
            if bounds and (not self._point_in_rect(x, y, bounds)):
                self.ui_state["craft_menu_open"] = False
                return

        slot = self._hotbar_hit(x, y)
        if slot:
            self.world.set_selected_food(slot["kind"])
            return

        self.on_mouse_down(e)

    def on_right_click(self, e):
        x, y = float(e.x), float(e.y)
        slot = self._hotbar_hit(x, y)
        if slot:
            self.world.try_craft_food(slot["kind"])
            return
        self.toggle_craft_menu()

    def on_mouse_down(self, e):
        x, y = float(e.x), float(e.y)
        now = time.perf_counter()

        self.last_mouse_x = x
        self.last_mouse_y = y
        self.last_mouse_t = now
        self.smoothed_vx = 0.0
        self.smoothed_vy = 0.0

        ent = self._pick_entity_under_cursor(x, y)
        if ent is not None:
            if hasattr(ent, "inventory") and hasattr(ent, "selected_food_kind"):
                self.world.set_focus(ent)

            self.dragging = True
            self.drag_ent = ent

            ent.held = True
            ent.vx = 0.0
            ent.vy = 0.0
            ent.vx_desired = 0.0

            self.drag_off_x = ent.x - x
            self.drag_off_y = ent.y - y
            return

        self.world.drop_food(x, y)

    def on_mouse_drag(self, e):
        if not self.dragging or self.drag_ent is None:
            return

        x, y = float(e.x), float(e.y)
        now = time.perf_counter()

        if self.last_mouse_t is not None:
            dtm = max(0.001, now - self.last_mouse_t)
            dx = x - float(self.last_mouse_x)
            dy = y - float(self.last_mouse_y)
            raw_vx = dx / dtm
            raw_vy = dy / dtm

            a = THROW_SMOOTHING
            self.smoothed_vx = (1.0 - a) * self.smoothed_vx + a * raw_vx
            self.smoothed_vy = (1.0 - a) * self.smoothed_vy + a * raw_vy

        self.last_mouse_x = x
        self.last_mouse_y = y
        self.last_mouse_t = now

        ent = self.drag_ent
        ent.x = x + self.drag_off_x
        ent.y = y + self.drag_off_y
        ent.x = clamp(ent.x, 0.0, float(self.world.width))
        ent.y = clamp(ent.y, -2000.0, float(self.world.height))

    def on_mouse_up(self, e):
        if not self.dragging or self.drag_ent is None:
            return

        ent = self.drag_ent
        self.dragging = False
        self.drag_ent = None

        ent.held = False

        if THROW_MODE == "yeet":
            scale = THROW_SCALE_YEET
            vmax = MAX_THROW_SPEED_YEET
        else:
            scale = THROW_SCALE_GENTLE
            vmax = MAX_THROW_SPEED_GENTLE

        vx = clamp(self.smoothed_vx * scale, -vmax, vmax)
        vy = clamp(self.smoothed_vy * scale, -vmax, vmax)

        speed = (vx * vx + vy * vy) ** 0.5
        if speed > vmax and speed > 0:
            k = vmax / speed
            vx *= k
            vy *= k

        ent.vx = vx
        ent.vy = vy

        # Wave 7: record throw intensity (Fenling only)
        if hasattr(ent, "traits"):
            intensity = "gentle" if speed < 900 else "hard"
            record_throw(ent, intensity)

    # -----------------------
    # Overlay / click-through
    # -----------------------

    def _set_clickthrough(self, enabled: bool):
        hwnd = self.root.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self.clickthrough_on = enabled
        print("Click-through:", self.clickthrough_on)

    def _force_transparency_key(self):
        try:
            self.root.configure(bg=self.overlay_color)
            self.canvas.configure(bg=self.overlay_color)
            if self.overlay_on:
                self.root.wm_attributes("-transparentcolor", self.overlay_color)
        except Exception:
            pass
        try:
            self.root.update_idletasks()
            self.root.update_idletasks()
        except Exception:
            pass

    def toggle_clickthrough(self):
        if not self.overlay_on:
            self._set_clickthrough(False)
            return
        self._force_transparency_key()
        self._set_clickthrough(not self.clickthrough_on)
        self._force_transparency_key()

    def _apply_overlay_state(self):
        on = self.overlay_on
        self.root.overrideredirect(on)
        self.root.attributes("-topmost", on)
        try:
            if on:
                self.root.wm_attributes("-transparentcolor", self.overlay_color)
            else:
                self.root.wm_attributes("-transparentcolor", "")
        except Exception:
            pass
        if (not on) and self.clickthrough_on:
            self._set_clickthrough(False)
        self._force_transparency_key()

    def toggle_overlay(self):
        self.overlay_on = not self.overlay_on
        self._apply_overlay_state()
        print("Overlay:", self.overlay_on)

    # -----------------------
    # Cursor stimulus
    # -----------------------

    def _update_cursor_stimulus(self):
        sx = float(self.root.winfo_pointerx())
        sy = float(self.root.winfo_pointery())
        wx = float(self.root.winfo_rootx())
        wy = float(self.root.winfo_rooty())
        lx = sx - wx
        ly = sy - wy

        now = time.perf_counter()
        speed = 0.0
        if self._last_cursor_t is not None:
            dt = max(0.001, now - self._last_cursor_t)
            dx = lx - float(self._last_cursor_x)
            dy = ly - float(self._last_cursor_y)
            speed = (dx * dx + dy * dy) ** 0.5 / dt

        self._last_cursor_x = lx
        self._last_cursor_y = ly
        self._last_cursor_t = now

        self.world.set_cursor(lx, ly, speed)

    # -----------------------
    # Loop / quit
    # -----------------------

    def tick(self):
        self._update_cursor_stimulus()
        self.world.tick()
        self.renderer.draw(self.canvas, self.world, self.ui_state)
        self.root.after(TICK_MS, self.tick)

    def quit(self):
        try:
            if self._kb_listener is not None:
                self._kb_listener.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()