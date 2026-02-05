from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from deskpet.util.mathutil import clamp


DEFAULT_TRAITS = {
    "trust": 0.50,    # more willing to approach / accept interactions
    "bold": 0.50,     # less scared, more “let’s go”
    "clingy": 0.50,   # seeks player/cursor, hates being ignored
    "playful": 0.50,  # likes toys, hops, goofy reactions
}


DEFAULT_ORIGIN = {
    "named": False,
    "fed_first": False,
    "played_first": False,
    "petted_first": False,
    "thrown_first": False,
    "poked_first": False,
}


def ensure_personality(pet) -> None:
    """Attach personality fields if missing (safe for older saves / dev runs)."""
    if not hasattr(pet, "traits") or pet.traits is None:
        pet.traits = dict(DEFAULT_TRAITS)
    else:
        for k, v in DEFAULT_TRAITS.items():
            pet.traits.setdefault(k, v)

    if not hasattr(pet, "origin_memory") or pet.origin_memory is None:
        pet.origin_memory = dict(DEFAULT_ORIGIN)
    else:
        for k, v in DEFAULT_ORIGIN.items():
            pet.origin_memory.setdefault(k, v)

    if not hasattr(pet, "event_log") or pet.event_log is None:
        pet.event_log = []  # list[str]


def _bump_trait(pet, key: str, delta: float) -> None:
    ensure_personality(pet)
    pet.traits[key] = clamp(float(pet.traits.get(key, 0.5)) + float(delta), 0.0, 1.0)


def record_event(pet, event: str) -> None:
    """Lightweight, always-on behavior memory for this run."""
    ensure_personality(pet)
    pet.event_log.append(event)
    pet.event_log = pet.event_log[-25:]


def apply_intro_name(pet, name: str) -> None:
    ensure_personality(pet)
    name = (name or "").strip()
    if name:
        pet.name = name
        pet.origin_memory["named"] = True
        record_event(pet, f"named:{name}")


def apply_intro_choice(pet, choice: str) -> None:
    """
    Sets first-impression flags and nudges traits.
    Choices are short IDs, not UI text.
    """
    ensure_personality(pet)

    if choice == "feed":
        pet.origin_memory["fed_first"] = True
        _bump_trait(pet, "trust", +0.10)
        _bump_trait(pet, "clingy", +0.03)
        record_event(pet, "intro:fed_first")

    elif choice == "play":
        pet.origin_memory["played_first"] = True
        _bump_trait(pet, "playful", +0.12)
        _bump_trait(pet, "bold", +0.05)
        record_event(pet, "intro:played_first")

    elif choice == "pet":
        pet.origin_memory["petted_first"] = True
        _bump_trait(pet, "trust", +0.08)
        _bump_trait(pet, "clingy", +0.08)
        record_event(pet, "intro:petted_first")

    elif choice == "throw_gentle":
        pet.origin_memory["thrown_first"] = True
        _bump_trait(pet, "bold", +0.10)
        _bump_trait(pet, "playful", +0.06)
        _bump_trait(pet, "trust", -0.03)  # some fenlings remember…
        record_event(pet, "intro:thrown_first")

    elif choice == "ignore":
        _bump_trait(pet, "clingy", +0.10)
        _bump_trait(pet, "trust", -0.05)
        record_event(pet, "intro:ignored")

    # fallback
    else:
        record_event(pet, f"intro:{choice}")


def record_feed(pet) -> None:
    ensure_personality(pet)
    _bump_trait(pet, "trust", +0.01)
    record_event(pet, "event:fed")


def record_play_ball(pet) -> None:
    ensure_personality(pet)
    _bump_trait(pet, "playful", +0.01)
    record_event(pet, "event:ball")


def record_poke(pet) -> None:
    ensure_personality(pet)
    pet.origin_memory["poked_first"] = pet.origin_memory.get("poked_first", False) or ("event:poked" not in pet.event_log)
    _bump_trait(pet, "trust", -0.01)
    _bump_trait(pet, "clingy", +0.01)
    record_event(pet, "event:poked")


def record_throw(pet, intensity: str) -> None:
    ensure_personality(pet)
    if intensity == "gentle":
        _bump_trait(pet, "bold", +0.01)
        _bump_trait(pet, "playful", +0.01)
        record_event(pet, "event:thrown_gentle")
    else:
        _bump_trait(pet, "trust", -0.02)
        _bump_trait(pet, "clingy", +0.02)
        record_event(pet, "event:thrown_hard")