from dataclasses import dataclass

@dataclass
class Food:
    x: float
    y: float
    kind: str = "kibble"