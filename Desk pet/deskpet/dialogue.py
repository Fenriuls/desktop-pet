from __future__ import annotations
import random
from deskpet.util.mathutil import clamp
from deskpet.personality import ensure_personality


def _pick(options, rng: random.Random) -> str:
    return rng.choice(options) if options else ""


def generate_reply(world, pet, user_text: str) -> str:
    """
    Local, rule-based “chat” that feels alive.
    No network. No ML libs. Just mood + traits + recent context.
    """
    ensure_personality(pet)

    txt = (user_text or "").strip().lower()
    rng = random.Random(hash((pet.name, world.t, txt)) & 0xFFFFFFFF)

    # quick state
    mood_state = getattr(pet, "mood_state", "content")
    hunger = getattr(pet, "hunger", 0.0)
    boredom = getattr(pet, "boredom", 0.0)

    trust = float(pet.traits.get("trust", 0.5))
    bold = float(pet.traits.get("bold", 0.5))
    clingy = float(pet.traits.get("clingy", 0.5))
    playful = float(pet.traits.get("playful", 0.5))

    last_events = list(getattr(pet, "event_log", []))[-6:]
    recently_thrown = any("thrown" in e for e in last_events)
    recently_ball = any("ball" in e for e in last_events)

    # intent-ish keyword buckets
    if any(k in txt for k in ["hi", "hello", "hey", "yo"]):
        if trust > 0.6:
            return _pick(["hi!", "hey!", "hello human."], rng)
        return _pick(["hm.", "…hi.", "hi."], rng)

    if any(k in txt for k in ["name", "who are you", "what are you"]):
        return _pick([f"i'm {pet.name}.", f"{pet.name}. that's me.", f"{pet.name}. don't forget it."], rng)

    if any(k in txt for k in ["hungry", "food", "eat"]):
        if hunger >= 30:
            return _pick(["yes. food. now.", "i would like… snacks.", "my tummy is yelling."], rng)
        return _pick(["i'm okay for now.", "later. maybe.", "not starving yet."], rng)

    if any(k in txt for k in ["play", "ball", "toy"]):
        if playful > 0.6 or boredom > 40:
            return _pick(["BALL!!", "yes yes yes.", "throw it. i dare you."], rng)
        return _pick(["maybe later.", "not feeling it.", "…fine. one ball."], rng)

    if any(k in txt for k in ["sorry", "apologize"]):
        if recently_thrown and trust < 0.55:
            return _pick(["hmpf.", "i will remember this… and also forgive. maybe.", "…okay. softer next time."], rng)
        return _pick(["okay.", "we're good.", "fine."], rng)

    if any(k in txt for k in ["love you", "good", "good job", "nice"]):
        if clingy > 0.65:
            return _pick(["again. say it again.", "stay here.", "i like that."], rng)
        return _pick([":)", "thanks.", "i'm trying."], rng)

    if any(k in txt for k in ["stop", "calm", "sit"]):
        if mood_state == "annoyed":
            return _pick(["finally.", "yes. silence.", "good."], rng)
        return _pick(["ok.", "sure.", "sitting-ish."], rng)

    # fallback based on current vibe
    if mood_state == "scared":
        return _pick(["…keep the bugs away.", "too many eyes.", "i don't like this."], rng)

    if mood_state == "annoyed":
        return _pick(["no.", "don't.", "…what."], rng)

    if mood_state == "happy":
        if recently_ball:
            return _pick(["again!!", "we are unstoppable.", "more chaos please."], rng)
        return _pick(["♪", "hi hi!", "this is nice."], rng)

    # content
    if boredom > 55:
        return _pick(["i'm bored.", "something happen.", "ball? bug? anything?"], rng)

    return _pick(["hm.", "okay.", "i'm listening.", "…"], rng)