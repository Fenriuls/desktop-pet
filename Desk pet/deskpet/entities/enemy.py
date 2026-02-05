from dataclasses import dataclass


@dataclass
class Enemy:
    eid: int
    x: float
    y: float
    hp: int = 12

    # Size (needed for feet-based ground)
    w: float = 28.0
    h: float = 28.0

    # Physics
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = False
    held: bool = False

    # AI steering
    vx_desired: float = 0.0

    # Skitter identity
    skitter_phase: float = 0.0
    skitter_freq: float = 9.0
    skitter_amp: float = 55.0

    # Chase micro-style
    chase_style: str = "direct"   # "direct" or "orbit"
    orbit_dir: int = 1            # -1 or +1
    style_until: float = 0.0

    # Combat timing
    attack_cd: float = 0.0

    # Debug
    last_impact: float = 0.0