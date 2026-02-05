from dataclasses import dataclass, field
from typing import Optional, List, Dict
from deskpet.util.mathutil import clamp


@dataclass
class Pet:
    # Fenling identity
    name: str = "Fenling"

    x: float = 200.0
    y: float = 200.0
    w: float = 64.0
    h: float = 64.0

    # Physics
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = False
    held: bool = False

    # AI steering
    vx_desired: float = 0.0

    # Wander
    wander_tx: float = 200.0
    wander_until: float = 0.0
    wander_pause_until: float = 0.0

    # Combat timing
    attack_cd: float = 0.0
    target_eid: Optional[int] = None

    # Debug/physics
    last_impact: float = 0.0

    # Stats
    level: int = 1
    xp: int = 0
    hp: int = 10
    max_hp: int = 10

    hunger: float = 0.0
    hunger_rate: float = 0.6

    # Mood + bubbles + docking + cursor
    mood: float = 0.15
    mood_state: str = "content"

    docked: bool = False
    dock_zone: str = "none"
    dock_progress: float = 0.0
    stagger_until: float = 0.0

    cursor_react_cd: float = 0.0
    poke_count: int = 0
    last_poke_time: float = -999.0

    bubbles: List[Dict] = field(default_factory=list)
    bubble_cd: float = 0.0

    # Per-Fenling inventory + per-Fenling food selection
    inventory: Dict = field(default_factory=lambda: {"bug_bits": 0})
    selected_food_kind: str = "kibble"

    # Wave 6 boredom
    boredom: float = 15.0
    _is_playing: bool = False

    # Wave 7 personality scaffold (local, no save yet)
    traits: Dict = field(default_factory=lambda: {
        "trust": 0.50, "bold": 0.50, "clingy": 0.50, "playful": 0.50
    })
    origin_memory: Dict = field(default_factory=lambda: {
        "named": False, "fed_first": False, "played_first": False,
        "petted_first": False, "thrown_first": False, "poked_first": False
    })
    event_log: List[str] = field(default_factory=list)

    def heal(self, amount: int):
        self.hp = int(clamp(self.hp + amount, 0, self.max_hp))

    def take_damage(self, amount: int):
        self.hp = int(clamp(self.hp - amount, 0, self.max_hp))

    def add_xp(self, amount: int):
        self.xp += amount
        need = 25 + (self.level - 1) * 8
        while self.xp >= need:
            self.xp -= need
            self.level += 1
            self.max_hp += 2
            self.hp = self.max_hp
            need = 25 + (self.level - 1) * 8

    def tick_needs(self):
        self.hunger = clamp(self.hunger + self.hunger_rate, 0, 100)

    def push_bubble(self, text: str, now_s: float, ttl: float = 2.2, priority: int = 50):
        if self.bubble_cd > 0:
            return
        self.bubbles.append({"text": text, "until": now_s + ttl, "prio": priority})
        self.bubbles = sorted(self.bubbles, key=lambda b: b["prio"], reverse=True)[:3]
        self.bubble_cd = 0.7