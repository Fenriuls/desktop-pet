from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class Pet:
    x: float = 200.0
    y: float = 200.0
    hp: int = 10
    max_hp: int = 10
    hunger: float = 0.0
    alive: bool = True

@dataclass
class Enemy:
    eid: int
    x: float
    y: float
    hp: int = 6
    speed: float = 1.2

@dataclass
class WorldState:
    pet: Pet = field(default_factory=Pet)
    enemies: Dict[int, Enemy] = field(default_factory=dict)
    next_eid: int = 1
    t: int = 0
