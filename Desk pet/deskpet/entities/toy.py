from dataclasses import dataclass

@dataclass
class ToyBall:
    x: float
    y: float
    r: float = 10.0

    vx: float = 0.0
    vy: float = 0.0
    vx_desired: float = 0.0  # unused, but keeps shape consistent

    w: float = 20.0
    h: float = 20.0

    held: bool = False
    on_ground: bool = False
    last_impact: float = 0.0