import tkinter as tk
from deskpet.config import (
    PET_SPRITES,
    FOOD_TYPES,
    HOTBAR_HEIGHT, HOTBAR_PAD, HOTBAR_SLOT_W, HOTBAR_SLOT_H, HOTBAR_SLOT_GAP,
)

class Renderer:
    def __init__(self, root: tk.Tk):
        self.pet_img = tk.PhotoImage(file=str(PET_SPRITES["idle"]))

    def _draw_bubble(self, canvas, x, y, text: str):
        pad_x = 10
        pad_y = 6
        text_id = canvas.create_text(x, y, text=text, anchor="s", fill="black")
        bbox = canvas.bbox(text_id)
        if not bbox:
            return
        x1, y1, x2, y2 = bbox
        x1 -= pad_x; x2 += pad_x; y1 -= pad_y; y2 += pad_y
        rect = canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black")
        tail = canvas.create_polygon(
            x, y2,
            x - 8, y2 + 10,
            x + 8, y2 + 10,
            fill="white", outline="black",
        )
        canvas.tag_raise(text_id, rect)
        canvas.tag_raise(text_id, tail)

    def hotbar_layout(self, world):
        w = int(world.width)
        h = int(world.height)
        bar_y0 = h - HOTBAR_HEIGHT
        kinds = list(FOOD_TYPES.keys())[:3]
        total_w = (len(kinds) * HOTBAR_SLOT_W) + ((len(kinds) - 1) * HOTBAR_SLOT_GAP)
        start_x = (w - total_w) / 2
        y = bar_y0 + HOTBAR_PAD

        slots = []
        for i, kind in enumerate(kinds):
            x = start_x + i * (HOTBAR_SLOT_W + HOTBAR_SLOT_GAP)
            slots.append({"kind": kind, "i": i, "x1": x, "y1": y, "x2": x + HOTBAR_SLOT_W, "y2": y + HOTBAR_SLOT_H})
        return slots

    def _draw_hotbar(self, canvas, world, focused):
        w = int(world.width)
        h = int(world.height)
        bar_y0 = h - HOTBAR_HEIGHT
        canvas.create_rectangle(0, bar_y0, w, h, fill="", outline="")

        slots = self.hotbar_layout(world)
        for s in slots:
            kind = s["kind"]
            i = s["i"]
            x1, y1, x2, y2 = s["x1"], s["y1"], s["x2"], s["y2"]

            selected = (kind == focused.selected_food_kind)
            outline = "white" if selected else "gray"
            width = 3 if selected else 1

            canvas.create_rectangle(x1, y1, x2, y2, fill="#111111", outline=outline, width=width)
            canvas.create_text((x1+x2)/2, y1+12, text=f"{i+1}", fill="white")
            canvas.create_text((x1+x2)/2, y1+30, text=kind, fill="white")

            cost = int(FOOD_TYPES[kind].get("cost_bug_bits", 0))
            if cost > 0:
                canvas.create_text(x2-8, y2-8, text=f"{cost}🪲", fill="white", anchor="se")

    def _draw_craft_menu(self, canvas, world, ui_state):
        if not ui_state.get("craft_menu_open", False):
            return

        w = int(world.width)
        h = int(world.height)
        mw, mh = 320, 190
        x1 = (w - mw) / 2
        y1 = (h - mh) / 2
        x2 = x1 + mw
        y2 = y1 + mh

        focused = world.get_focused()
        bits = focused.inventory.get("bug_bits", 0)

        canvas.create_rectangle(x1, y1, x2, y2, fill="#1b1b1b", outline="white", width=2)
        canvas.create_text((x1+x2)/2, y1+18, text="Crafting", fill="white", font=("TkDefaultFont", 12, "bold"))
        canvas.create_text((x1+x2)/2, y1+42, text=f"{focused.name} Bug Bits: {bits}", fill="white")

        btns = []
        kinds = list(FOOD_TYPES.keys())[:3]
        by = y1 + 65
        for i, kind in enumerate(kinds):
            cost = int(FOOD_TYPES[kind].get("cost_bug_bits", 0))
            label = f"{kind}  (cost {cost})"
            bx1 = x1 + 24
            bx2 = x2 - 24
            b_y1 = by + i * 36
            b_y2 = b_y1 + 30
            canvas.create_rectangle(bx1, b_y1, bx2, b_y2, fill="#2a2a2a", outline="gray")
            canvas.create_text((bx1+bx2)/2, (b_y1+b_y2)/2, text=label, fill="white")
            btns.append({"kind": kind, "x1": bx1, "y1": b_y1, "x2": bx2, "y2": b_y2})

        canvas.create_text((x1+x2)/2, y2-18, text="Click outside to close", fill="white")

        ui_state["craft_buttons"] = btns
        ui_state["craft_bounds"] = (x1, y1, x2, y2)

    def draw(self, canvas, world, ui_state=None):
        if ui_state is None:
            ui_state = {}

        canvas.delete("all")

        # toys (ball)
        for b in getattr(world, "toys", []):
            canvas.create_oval(b.x - b.r, b.y - b.r, b.x + b.r, b.y + b.r, fill="white", outline="")

        # fenlings
        for p in world.fenlings:
            canvas.create_image(p.x, p.y, image=self.pet_img, anchor="center")

        # food
        for f in world.food:
            fill = "green" if f.kind == "kibble" else ("orange" if f.kind == "meat" else "pink")
            canvas.create_oval(f.x - 6, f.y - 6, f.x + 6, f.y + 6, fill=fill, outline="")

        # enemies
        for e in world.enemies:
            canvas.create_oval(e.x - e.w/2, e.y - e.h/2, e.x + e.w/2, e.y + e.h/2, fill="red", outline="")

        focused = world.get_focused()

        # focused bubble
        if focused.bubbles:
            b = focused.bubbles[0]
            self._draw_bubble(canvas, focused.x, focused.y - (focused.h * 0.65), b["text"])

        # hotbar + craft menu
        self._draw_hotbar(canvas, world, focused)
        self._draw_craft_menu(canvas, world, ui_state)

        bits = focused.inventory.get("bug_bits", 0)
        boredom = getattr(focused, "boredom", 0.0)
        canvas.create_text(
            10, 10,
            text=f"focused={focused.name} | mood={focused.mood_state} ({focused.mood:+.2f}) | boredom={boredom:.0f} | bits={bits} | selected={focused.selected_food_kind} | balls={len(getattr(world,'toys',[]))}",
            anchor="nw",
            fill="white"
        )
        canvas.create_text(
            10, 30,
            text="Wave 6: Press B to spawn a ball",
            anchor="nw",
            fill="white"
        )