from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import time
import random
import re


DEFAULT_TRAITS: Dict[str, float] = {
    "trust": 50.0,
    "affection": 50.0,
    "bravery": 50.0,
    "curiosity": 50.0,
    "playfulness": 50.0,
    "patience": 50.0,
    "human_kindness": 50.0,
    "human_consistency": 50.0,
}

TRAIT_MIN = 0.0
TRAIT_MAX = 100.0


def _clamp(v: float, lo: float = TRAIT_MIN, hi: float = TRAIT_MAX) -> float:
    return lo if v < lo else hi if v > hi else v


def _now() -> float:
    return time.time()


def _day_id(ts: float) -> int:
    return int(ts // 86400)


@dataclass
class InteractionEvent:
    ts: float
    kind: str
    value: float = 0.0
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class CareStats:
    # “How you treat it” memory
    feed_count_total: int = 0
    praise_count_total: int = 0
    scold_count_total: int = 0
    talk_count_total: int = 0

    # last times
    last_fed_ts: float = 0.0
    last_talk_ts: float = 0.0
    last_positive_ts: float = 0.0
    last_negative_ts: float = 0.0

    # consistency/neglect tracking
    neglect_strikes: int = 0
    last_neglect_check_day: int = 0

    # “daily care” record (day_id -> count)
    fed_by_day: Dict[str, int] = field(default_factory=dict)
    talked_by_day: Dict[str, int] = field(default_factory=dict)
    praised_by_day: Dict[str, int] = field(default_factory=dict)


@dataclass
class BrainState:
    pet_name: str = "FenPet"
    first_run_done: bool = False

    first_contact_style: str = "unknown"  # gentle|rough|curious|silent|mixed|unknown
    first_contact_score: float = 0.0

    traits: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_TRAITS))

    interaction_log: List[InteractionEvent] = field(default_factory=list)

    # lightweight convo memory
    last_user_utterances: List[str] = field(default_factory=list)
    last_pet_replies: List[str] = field(default_factory=list)

    # mechanical learning: phrase triggers -> replies
    phrase_memory: Dict[str, str] = field(default_factory=dict)

    # word + habit memory (your earlier “word_memory/habit_memory” direction)
    word_memory: Dict[str, str] = field(default_factory=dict)        # key -> value
    habit_memory: Dict[str, float] = field(default_factory=dict)     # metric -> score

    care: CareStats = field(default_factory=CareStats)

    mood: str = "neutral"
    last_chat_ts: float = 0.0

    # drift bookkeeping
    last_drift_day: int = 0
    last_weekly_day: int = 0


class PetBrain:
    """
    Lifelong brain:
      - remembers first contact
      - remembers care patterns (fed/praised/scolded/talked + neglect)
      - word_memory + habit_memory
      - daily/weekly trait drift
      - mechanical learning chat
    """

    def __init__(self, state: Optional[BrainState] = None, rng_seed: Optional[int] = None):
        self.state = state or BrainState()
        self.rng = random.Random(rng_seed if rng_seed is not None else int(_now() * 1000) % 2**32)

        self._pos_words = {
            "good", "nice", "great", "love", "cute", "sweet", "thanks", "thank you",
            "awesome", "well done", "proud", "yay", "brave", "strong"
        }
        self._neg_words = {
            "bad", "stupid", "hate", "annoying", "shut up", "idiot", "dumb", "stop"
        }

        self._greet = {"hi", "hello", "hey", "yo", "sup"}
        self._bye = {"bye", "goodbye", "cya", "see you", "later", "gn", "goodnight"}

        self._ask_name = {"your name", "who are you", "what are you"}
        self._help = {"help", "how", "what can you do", "commands"}

    # ---------------------------
    # Persistence
    # ---------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self.state)
        d["interaction_log"] = [asdict(ev) for ev in self.state.interaction_log]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any], rng_seed: Optional[int] = None) -> "PetBrain":
        # reconstruct CareStats safely
        care_d = d.get("care", {}) or {}
        care = CareStats(
            feed_count_total=int(care_d.get("feed_count_total", 0)),
            praise_count_total=int(care_d.get("praise_count_total", 0)),
            scold_count_total=int(care_d.get("scold_count_total", 0)),
            talk_count_total=int(care_d.get("talk_count_total", 0)),
            last_fed_ts=float(care_d.get("last_fed_ts", 0.0)),
            last_talk_ts=float(care_d.get("last_talk_ts", 0.0)),
            last_positive_ts=float(care_d.get("last_positive_ts", 0.0)),
            last_negative_ts=float(care_d.get("last_negative_ts", 0.0)),
            neglect_strikes=int(care_d.get("neglect_strikes", 0)),
            last_neglect_check_day=int(care_d.get("last_neglect_check_day", 0)),
            fed_by_day=dict(care_d.get("fed_by_day", {}) or {}),
            talked_by_day=dict(care_d.get("talked_by_day", {}) or {}),
            praised_by_day=dict(care_d.get("praised_by_day", {}) or {}),
        )

        st = BrainState(
            pet_name=d.get("pet_name", "FenPet"),
            first_run_done=bool(d.get("first_run_done", False)),
            first_contact_style=d.get("first_contact_style", "unknown"),
            first_contact_score=float(d.get("first_contact_score", 0.0)),
            traits=dict(DEFAULT_TRAITS) | dict(d.get("traits", {})),
            interaction_log=[],
            last_user_utterances=list(d.get("last_user_utterances", [])),
            last_pet_replies=list(d.get("last_pet_replies", [])),
            phrase_memory=dict(d.get("phrase_memory", {})),
            word_memory=dict(d.get("word_memory", {})),
            habit_memory={k: float(v) for k, v in (d.get("habit_memory", {}) or {}).items()},
            care=care,
            mood=d.get("mood", "neutral"),
            last_chat_ts=float(d.get("last_chat_ts", 0.0)),
            last_drift_day=int(d.get("last_drift_day", 0)),
            last_weekly_day=int(d.get("last_weekly_day", 0)),
        )

        for evd in d.get("interaction_log", []) or []:
            try:
                st.interaction_log.append(
                    InteractionEvent(
                        ts=float(evd.get("ts", _now())),
                        kind=str(evd.get("kind", "unknown")),
                        value=float(evd.get("value", 0.0)),
                        meta=dict(evd.get("meta", {}) or {}),
                    )
                )
            except Exception:
                continue

        for k in list(st.traits.keys()):
            st.traits[k] = _clamp(float(st.traits[k]))

        # ensure drift day fields are initialized
        now = _now()
        if st.last_drift_day == 0:
            st.last_drift_day = _day_id(now)
        if st.last_weekly_day == 0:
            st.last_weekly_day = _day_id(now)

        return cls(st, rng_seed=rng_seed)

    # ---------------------------
    # Tick drift + neglect checks
    # ---------------------------

    def tick(self, now_ts: Optional[float] = None, *, neglect_hours: float = 24.0) -> None:
        """
        Call this regularly (world.tick) to:
          - apply daily drift
          - apply weekly consolidation
          - apply neglect strike if no feeding/talking beyond threshold
        """
        now_ts = _now() if now_ts is None else float(now_ts)
        today = _day_id(now_ts)

        # daily drift once per day
        if today != self.state.last_drift_day:
            self._daily_drift(today)
            self.state.last_drift_day = today

        # weekly consolidation every 7 days
        if (today - self.state.last_weekly_day) >= 7:
            self._weekly_consolidation(today)
            self.state.last_weekly_day = today

        # neglect check (at most once per day)
        if today != self.state.care.last_neglect_check_day:
            self.state.care.last_neglect_check_day = today
            self._neglect_check(now_ts, neglect_hours=neglect_hours)

        self._refresh_mood_from_recent()

    def _daily_drift(self, today: int) -> None:
        """
        Gentle “living creature” drift.
        Consistency and kindness keep trust/affection stable.
        Neglect + harshness erode patience/trust.
        """
        t = self.state.traits
        care = self.state.care

        yday = str(today - 1)
        fed_yday = int(care.fed_by_day.get(yday, 0))
        talked_yday = int(care.talked_by_day.get(yday, 0))
        praised_yday = int(care.praised_by_day.get(yday, 0))

        # baseline drift toward 50
        for k in ("bravery", "curiosity", "playfulness", "patience"):
            self._nudge_toward(k, 50.0, rate=0.35)

        # consistency boosts if repeated daily care exists
        if fed_yday > 0 and talked_yday > 0:
            self._add_trait("human_consistency", +0.8)
            self._add_trait("trust", +0.4)
        elif fed_yday > 0 or talked_yday > 0:
            self._add_trait("human_consistency", +0.3)
        else:
            self._add_trait("human_consistency", -0.6)

        # praise makes affection stickier
        if praised_yday > 0:
            self._add_trait("affection", +0.4)
            self._add_trait("trust", +0.2)

        # neglect strikes slightly erode trust/patience (handled in neglect check too)
        if care.neglect_strikes > 0:
            self._add_trait("patience", -0.2 * care.neglect_strikes)

        # tiny mood seasoning via kindness
        kindness = t.get("human_kindness", 50.0)
        if kindness >= 60:
            self._add_trait("trust", +0.2)
        elif kindness <= 40:
            self._add_trait("trust", -0.2)

    def _weekly_consolidation(self, today: int) -> None:
        """
        Weekly “this becomes who I am” consolidation.
        Makes extremes a bit more stable based on overall care pattern.
        """
        t = self.state.traits
        care = self.state.care

        # compute last 7 days feeding/talking streak
        fed_days = 0
        talk_days = 0
        for d in range(today - 7, today):
            key = str(d)
            if int(care.fed_by_day.get(key, 0)) > 0:
                fed_days += 1
            if int(care.talked_by_day.get(key, 0)) > 0:
                talk_days += 1

        # reward consistency
        if fed_days >= 5 and talk_days >= 5:
            self._add_trait("human_consistency", +2.5)
            self._add_trait("trust", +1.5)
            self._add_trait("affection", +1.0)
        elif fed_days <= 1 and talk_days <= 1:
            self._add_trait("human_consistency", -2.5)
            self._add_trait("trust", -1.5)
            self._add_trait("patience", -1.0)

        # habit memory “scores”
        self.state.habit_memory["weekly_fed_days"] = float(fed_days)
        self.state.habit_memory["weekly_talk_days"] = float(talk_days)

        # stabilize first-contact influence slightly (it stays, but fades a bit)
        style = self.state.first_contact_style
        if style == "rough":
            self._nudge_toward("trust", 48.0, rate=0.2)
        elif style == "gentle":
            self._nudge_toward("trust", 52.0, rate=0.2)

    def _neglect_check(self, now_ts: float, *, neglect_hours: float) -> None:
        care = self.state.care

        # neglect means: too long since fed AND too long since talked
        sec = neglect_hours * 3600.0
        fed_gap = now_ts - float(care.last_fed_ts or 0.0)
        talk_gap = now_ts - float(care.last_talk_ts or 0.0)

        if care.last_fed_ts == 0.0 and care.last_talk_ts == 0.0:
            # brand new; don’t punish
            return

        if fed_gap > sec and talk_gap > sec:
            care.neglect_strikes += 1
            self.record_event("ignored", meta={"neglect_hours": f"{neglect_hours:.1f}"})

            # apply a sting
            self._add_trait("trust", -1.5)
            self._add_trait("patience", -1.0)
            self._add_trait("human_kindness", -0.8)
        else:
            # recovery: gentle decay of strikes
            if care.neglect_strikes > 0:
                care.neglect_strikes -= 1
            self.record_event("consistent_care")

    # ---------------------------
    # Onboarding / naming
    # ---------------------------

    def onboarding_active(self) -> bool:
        return not self.state.first_run_done

    def set_pet_name(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        self.state.pet_name = name[:24]

    def record_first_contact_delta(self, delta: float) -> None:
        if self.state.first_run_done:
            return
        self.state.first_contact_score += float(delta)

    def mark_first_run_done(self) -> None:
        self.state.first_run_done = True
        self._finalize_first_contact_style()

    def _finalize_first_contact_style(self) -> None:
        s = self.state.first_contact_score
        if s >= 6:
            style = "gentle"
        elif s <= -6:
            style = "rough"
        elif abs(s) <= 1:
            style = "silent"
        else:
            style = "mixed"
        self.state.first_contact_style = style

        if style == "gentle":
            self._add_trait("trust", +8)
            self._add_trait("affection", +6)
            self._add_trait("patience", +4)
            self._add_trait("human_kindness", +8)
        elif style == "rough":
            self._add_trait("trust", -10)
            self._add_trait("patience", -6)
            self._add_trait("bravery", +4)
            self._add_trait("human_kindness", -10)
        elif style == "silent":
            self._add_trait("curiosity", +6)
            self._add_trait("human_consistency", -2)
        else:
            self._add_trait("curiosity", +3)
            self._add_trait("human_consistency", +1)

    # ---------------------------
    # Interaction learning
    # ---------------------------

    def record_event(self, kind: str, value: float = 0.0, meta: Optional[Dict[str, str]] = None) -> None:
        now_ts = _now()
        ev = InteractionEvent(ts=now_ts, kind=kind, value=float(value), meta=meta or {})
        self.state.interaction_log.append(ev)

        if len(self.state.interaction_log) > 220:
            self.state.interaction_log = self.state.interaction_log[-220:]

        # care stats updates
        care = self.state.care
        today = str(_day_id(now_ts))

        if kind == "fed":
            care.feed_count_total += 1
            care.last_fed_ts = now_ts
            care.last_positive_ts = now_ts
            care.fed_by_day[today] = int(care.fed_by_day.get(today, 0)) + 1
        elif kind == "praised":
            care.praise_count_total += 1
            care.last_positive_ts = now_ts
            care.praised_by_day[today] = int(care.praised_by_day.get(today, 0)) + 1
        elif kind == "scolded":
            care.scold_count_total += 1
            care.last_negative_ts = now_ts
        elif kind == "talked":
            care.talk_count_total += 1
            care.last_talk_ts = now_ts
            care.talked_by_day[today] = int(care.talked_by_day.get(today, 0)) + 1

        self._apply_event_to_traits(ev)
        self._refresh_mood_from_recent()

    def _apply_event_to_traits(self, ev: InteractionEvent) -> None:
        k = ev.kind

        # onboarding scoring
        if not self.state.first_run_done:
            if k in ("fed", "praised"):
                self.record_first_contact_delta(+1.5)
            elif k in ("scolded", "hit"):
                self.record_first_contact_delta(-2.0)
            elif k in ("talked",):
                self.record_first_contact_delta(+0.5)

        if k == "fed":
            self._add_trait("trust", +1.2)
            self._add_trait("affection", +1.0)
            self._add_trait("human_kindness", +1.0)
        elif k == "praised":
            self._add_trait("trust", +1.0)
            self._add_trait("playfulness", +0.8)
            self._add_trait("human_kindness", +0.4)
        elif k == "scolded":
            self._add_trait("patience", -0.8)
            self._add_trait("trust", -0.6)
        elif k == "hit":
            self._add_trait("trust", -3.0)
            self._add_trait("human_kindness", -2.5)
            self._add_trait("bravery", +1.0)
        elif k == "ignored":
            self._add_trait("human_consistency", -0.6)
        elif k == "played":
            self._add_trait("playfulness", +1.2)
            self._add_trait("trust", +0.5)
            self._add_trait("curiosity", +0.5)
        elif k == "talked":
            self._add_trait("curiosity", +0.6)
            self._add_trait("trust", +0.2)
        elif k == "consistent_care":
            self._add_trait("human_consistency", +0.7)
            self._add_trait("human_kindness", +0.3)

    def _add_trait(self, name: str, delta: float) -> None:
        self.state.traits[name] = _clamp(float(self.state.traits.get(name, 50.0)) + float(delta))

    def _nudge_toward(self, name: str, target: float, rate: float) -> None:
        v = float(self.state.traits.get(name, 50.0))
        v = v + (target - v) * float(rate)
        self.state.traits[name] = _clamp(v)

    def _refresh_mood_from_recent(self) -> None:
        recent = self.state.interaction_log[-12:]
        score = 0.0
        for ev in recent:
            if ev.kind in ("fed", "praised", "played"):
                score += 1.0
            elif ev.kind in ("hit",):
                score -= 2.0
            elif ev.kind in ("scolded", "ignored"):
                score -= 0.8

        t = self.state.traits
        trust = t.get("trust", 50.0)
        if score >= 4 and trust >= 55:
            self.state.mood = "happy"
        elif score <= -3 or trust <= 35:
            self.state.mood = "wary"
        elif t.get("curiosity", 50.0) >= 60:
            self.state.mood = "curious"
        elif t.get("patience", 50.0) <= 35:
            self.state.mood = "grumpy"
        else:
            self.state.mood = "neutral"

    # ---------------------------
    # Word memory helpers
    # ---------------------------

    def remember(self, key: str, value: str) -> None:
        k = (key or "").strip().lower()
        v = (value or "").strip()
        if not k or not v:
            return
        self.state.word_memory[k[:40]] = v[:120]

    def forget(self, key: str) -> bool:
        k = (key or "").strip().lower()
        if not k:
            return False
        return self.state.word_memory.pop(k, None) is not None

    # ---------------------------
    # Chat (mechanical learning)
    # ---------------------------

    def chat(self, user_text: str) -> str:
        txt = (user_text or "").strip()
        if not txt:
            return self._reply("...?", kind="talked")

        self.record_event("talked", meta={"text": txt})
        self._remember_utterance(txt)

        low = txt.lower()

        # Teaching phrases: "when I say X, say Y"
        taught = self._parse_teaching(txt)
        if taught:
            key, val = taught
            self.state.phrase_memory[key] = val
            return self._reply(f"Okay. When you say “{key}”, I’ll say “{val}”.", kind="talked")

        # Word memory: "remember that X is Y" or "remember X = Y"
        mem = self._parse_word_memory(txt)
        if mem:
            k, v = mem
            self.remember(k, v)
            return self._reply(f"Stored. {k} = {v}", kind="talked")

        # Recall: "what do you remember" or "remember X?"
        if "what do you remember" in low or low.strip() == "memories":
            return self._reply(self._memory_summary(), kind="talked")

        ask_mem = self._parse_memory_query(txt)
        if ask_mem:
            k = ask_mem
            v = self.state.word_memory.get(k)
            if v is None:
                return self._reply(f"I don’t have anything for “{k}” yet.", kind="talked")
            return self._reply(f"{k} = {v}", kind="talked")

        # Forget: "forget X"
        forget_key = self._parse_forget(txt)
        if forget_key:
            ok = self.forget(forget_key)
            return self._reply("Forgot it." if ok else "I didn’t have that stored.", kind="talked")

        # Phrase memory matches
        for key, val in self.state.phrase_memory.items():
            if key and key in low:
                return self._reply(val, kind="talked")

        intent = self._detect_intent(txt)
        sentiment = self._sentiment(txt)

        t = self.state.traits
        trust = t.get("trust", 50.0)
        play = t.get("playfulness", 50.0)
        brave = t.get("bravery", 50.0)
        curious = t.get("curiosity", 50.0)
        patience = t.get("patience", 50.0)

        name = self.state.pet_name

        if intent == "greet":
            if trust < 40:
                return self._reply(f"...hi. I’m {name}.", kind="talked")
            if play >= 60:
                return self._reply(f"Hey! I’m {name}. Got any quests for me? 🐾", kind="talked")
            return self._reply(f"Hi. I’m {name}.", kind="talked")

        if intent == "bye":
            if trust >= 60:
                return self._reply("Okay. I’ll keep watch. Come back soon.", kind="talked")
            return self._reply("Bye.", kind="talked")

        if intent == "ask_name":
            return self._reply(f"I’m {name}.", kind="talked")

        if intent == "help":
            return self._reply(
                "Talk to me anytime. Teach phrases: “when I say X, say Y”. "
                "Memory: “remember that X is Y”, “remember X?”, “forget X”. "
                "Commands: sit, come, guard.",
                kind="talked",
            )

        # sentiment affects traits
        if sentiment > 0:
            self.record_event("praised", value=1.0)
            if play >= 65:
                return self._reply("YES. I am unstoppable. Also snack-motivated.", kind="talked")
            return self._reply("I’ll... try to be even better.", kind="talked")

        if sentiment < 0:
            self.record_event("scolded", value=1.0)
            if patience < 40:
                return self._reply("I heard you. I’m not thrilled about it.", kind="talked")
            if trust < 40:
                return self._reply("...okay.", kind="talked")
            return self._reply("Sorry. I’ll calm down.", kind="talked")

        if "how are you" in low or "hru" in low:
            return self._reply(self._status_line(), kind="talked")

        if "fight" in low or "combat" in low:
            if brave >= 60:
                return self._reply("Point me at a monster. I’ll handle the negotiations.", kind="talked")
            return self._reply("I can fight... but I like having a plan.", kind="talked")

        if "hungry" in low or "food" in low:
            if trust >= 55:
                return self._reply("Food would improve my mood by a scientifically alarming amount.", kind="talked")
            return self._reply("Food would help.", kind="talked")

        if curious >= 65 and self.rng.random() < 0.35:
            return self._reply(self._curious_prompt(), kind="talked")

        options = []
        if trust >= 60:
            options += ["I’m listening.", "Tell me more.", "Okay. What next?"]
        else:
            options += ["...hm.", "I heard you.", "Okay."]
        if play >= 60:
            options += ["Can we do something fun?", "I vote snacks and adventure."]
        if patience <= 35:
            options += ["Can we keep it short?", "My attention span is squirrel-shaped."]
        return self._reply(self.rng.choice(options), kind="talked")

    def _reply(self, text: str, kind: str = "talked") -> str:
        self.state.last_pet_replies.append(text)
        if len(self.state.last_pet_replies) > 25:
            self.state.last_pet_replies = self.state.last_pet_replies[-25:]
        self.state.last_chat_ts = _now()
        return text

    def _remember_utterance(self, txt: str) -> None:
        self.state.last_user_utterances.append(txt)
        if len(self.state.last_user_utterances) > 25:
            self.state.last_user_utterances = self.state.last_user_utterances[-25:]

    def _parse_teaching(self, txt: str) -> Optional[Tuple[str, str]]:
        t = txt.strip()
        m = re.search(r"when i say (.+?),\s*say (.+)$", t, flags=re.IGNORECASE)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            if 1 <= len(key) <= 40 and 1 <= len(val) <= 80:
                return key, val

        m = re.search(r"if i say (.+?)\s+then\s+say (.+)$", t, flags=re.IGNORECASE)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            if 1 <= len(key) <= 40 and 1 <= len(val) <= 80:
                return key, val
        return None

    def _parse_word_memory(self, txt: str) -> Optional[Tuple[str, str]]:
        # "remember that X is Y"
        m = re.search(r"^\s*remember that (.+?)\s+is\s+(.+)\s*$", txt, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip().lower(), m.group(2).strip()

        # "remember X = Y"
        m = re.search(r"^\s*remember\s+(.+?)\s*=\s*(.+)\s*$", txt, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip().lower(), m.group(2).strip()

        return None

    def _parse_memory_query(self, txt: str) -> Optional[str]:
        # "remember X?"
        m = re.search(r"^\s*remember\s+(.+?)\s*\?\s*$", txt, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip().lower()
        return None

    def _parse_forget(self, txt: str) -> Optional[str]:
        m = re.search(r"^\s*forget\s+(.+)\s*$", txt, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip().lower()
        return None

    def _detect_intent(self, txt: str) -> str:
        low = txt.lower()
        if any(w in low for w in self._greet):
            return "greet"
        if any(w in low for w in self._bye):
            return "bye"
        if any(w in low for w in self._ask_name):
            return "ask_name"
        if any(w in low for w in self._help):
            return "help"
        return "chat"

    def _sentiment(self, txt: str) -> int:
        low = txt.lower()
        s = 0
        for w in self._pos_words:
            if w in low:
                s += 1
        for w in self._neg_words:
            if w in low:
                s -= 1
        return s

    def _curious_prompt(self) -> str:
        prompts = [
            "What should we hunt today?",
            "Do you think monsters dream?",
            "Name a snack and I’ll consider it a quest.",
            "Tell me a secret. I’ll pretend I’m responsible with it.",
        ]
        return self.rng.choice(prompts)

    def _status_line(self) -> str:
        t = self.state.traits
        mood = self.state.mood
        trust = t.get("trust", 50.0)
        affection = t.get("affection", 50.0)
        strikes = self.state.care.neglect_strikes
        return f"I feel {mood}. Trust {trust:.0f}/100. Affection {affection:.0f}/100. Neglect strikes {strikes}."

    def _memory_summary(self) -> str:
        wm = self.state.word_memory
        if not wm:
            return "I don’t have any word-memories yet. Teach me: “remember that X is Y”."
        # show up to 5
        items = list(wm.items())[:5]
        lines = [f"{k} = {v}" for k, v in items]
        if len(wm) > 5:
            lines.append(f"(+{len(wm) - 5} more)")
        return "I remember:\n" + "\n".join(lines)
