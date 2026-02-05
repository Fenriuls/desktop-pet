import random
import math
from typing import List, Optional

from deskpet.entities.pet import Pet
from deskpet.entities.enemy import Enemy
from deskpet.entities.food import Food
from deskpet.entities.toy import ToyBall

from deskpet.personality import ensure_personality, record_feed, record_play_ball, record_poke

from deskpet.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TICK_MS,
    SPAWN_INTERVAL_TICKS, MAX_ENEMIES,
    GRAVITY, MAX_FALL_SPEED, GROUND_MARGIN,
    AIR_DRAG, GROUND_MODE, GROUND_FRICTION_SKID, GROUND_FRICTION_STICKY,
    STOP_EPS_SKID, STOP_EPS_STICKY,
    PET_MAX_SPEED, PET_ACCEL,
    ENEMY_MAX_SPEED, ENEMY_ACCEL,
    ENEMY_DETECT_RADIUS,
    ENEMY_ORBIT_CHANCE, ENEMY_ORBIT_RADIUS,
    ENEMY_STYLE_MIN_SECS_DIRECT, ENEMY_STYLE_MAX_SECS_DIRECT,
    ENEMY_STYLE_MIN_SECS_ORBIT, ENEMY_STYLE_MAX_SECS_ORBIT,
    ENEMY_SKITTER_ON, ENEMY_SKITTER_AMP_MIN, ENEMY_SKITTER_AMP_MAX,
    ENEMY_SKITTER_FREQ_MIN, ENEMY_SKITTER_FREQ_MAX,
    ENEMY_JUMP_STRENGTH, ENEMY_JUMP_COOLDOWN, ENEMY_WANDER_HOP_RATE, ENEMY_CHASE_HOP_RATE,
    AI_STEP_SECS,
    ATTACK_RANGE, FOOD_EAT_RANGE, HUNGER_START_SEEK_FOOD,
    PET_ATTACK_COOLDOWN, ENEMY_ATTACK_COOLDOWN, PET_DAMAGE, ENEMY_DAMAGE,
    MOOD_START, MOOD_DECAY_PER_SEC, MOOD_HAPPY_THRESHOLD, MOOD_ANNOYED_THRESHOLD, MOOD_SCARED_THRESHOLD,
    CURSOR_INTERACT_RADIUS, CURSOR_POKE_RADIUS, CURSOR_STILL_SPEED, CURSOR_FAST_SPEED,
    CURSOR_REACT_COOLDOWN, CURSOR_POKE_IRRITATION, CURSOR_POKE_FOR_FRUSTRATION_JUMP,
    BUBBLE_TTL_SECS,
    DOCK_MIN_SECS, TASKBAR_DOCK_BAND, DOCK_UNDOCK_HUNGER, DOCK_ENEMY_ALERT_RADIUS,
    LANDING_SMALL, LANDING_BIG, RECOVERY_HOP_STRENGTH, STAGGER_BIG_SECS,
    BUG_BITS_DROP_MIN, BUG_BITS_DROP_MAX,
    FOOD_TYPES, DEFAULT_FOOD_KIND,
    BOREDOM_START, BOREDOM_MAX, BOREDOM_GAIN_PER_SEC, BOREDOM_REDUCE_PER_SEC_PLAY, BOREDOM_SEEK_THRESHOLD,
    TOY_BALL_RADIUS, TOY_BALL_BOUNCE, TOY_BALL_GROUND_FRICTION, TOY_BALL_STOP_EPS, TOY_CHASE_RADIUS,
)
from deskpet.util.mathutil import clamp, dist, sign


class World:
    def __init__(self, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, offset_x=0, offset_y=0, work_area=None):
        self.width = width
        self.height = height
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.work_area = work_area

        self.fenlings: List[Pet] = []
        self.focus_idx: int = 0
        self.spawn_fenling(x=200.0, y=200.0, name="Fenling-1")

        self.enemies: List[Enemy] = []
        self.food: List[Food] = []

        self.toys: List[ToyBall] = []

        self.t = 0
        self.next_eid = 1

        self.time_s = 0.0
        self._ai_accum = 0.0

        self.cursor_x = None
        self.cursor_y = None
        self.cursor_speed = 0.0

        # Wave 7: freeze simulation while modals are open
        self.paused: bool = False

    # ----------------------------
    # Fenling helpers
    # ----------------------------

    def spawn_fenling(self, x: float, y: float, name: str = "Fenling"):
        p = Pet(name=name)
        p.x = float(x)
        p.y = float(y)
        p.mood = MOOD_START
        p.selected_food_kind = DEFAULT_FOOD_KIND
        p.inventory = {"bug_bits": 0}
        p.boredom = float(BOREDOM_START)
        p.wander_tx = float(random.randint(40, max(41, int(self.width) - 40)))

        ensure_personality(p)

        self.fenlings.append(p)
        return p

    def get_focused(self) -> Pet:
        if not self.fenlings:
            self.spawn_fenling(200.0, 200.0, "Fenling-1")
            self.focus_idx = 0
        self.focus_idx = int(clamp(self.focus_idx, 0, len(self.fenlings) - 1))
        return self.fenlings[self.focus_idx]

    def set_focus(self, pet: Pet):
        try:
            self.focus_idx = self.fenlings.index(pet)
        except ValueError:
            pass

    def nearest_fenling_to(self, x: float, y: float) -> Optional[Pet]:
        if not self.fenlings:
            return None
        best, best_d = None, 1e18
        for p in self.fenlings:
            d = dist(x, y, p.x, p.y)
            if d < best_d:
                best, best_d = p, d
        return best

    # ----------------------------
    # Inputs
    # ----------------------------

    def set_cursor(self, x: float, y: float, speed: float):
        self.cursor_x = float(x)
        self.cursor_y = float(y)
        self.cursor_speed = float(speed)

    def set_selected_food(self, kind: str):
        if kind not in FOOD_TYPES:
            return
        p = self.get_focused()
        p.selected_food_kind = kind
        p.push_bubble(f"{kind}", self.time_s, ttl=1.1, priority=60)

    def try_craft_food(self, kind: str) -> bool:
        if kind not in FOOD_TYPES:
            return False
        p = self.get_focused()
        cost = int(FOOD_TYPES[kind].get("cost_bug_bits", 0))
        if p.inventory.get("bug_bits", 0) < cost:
            p.push_bubble("need bug bits", self.time_s, ttl=1.4, priority=85)
            return False
        p.inventory["bug_bits"] -= cost
        p.selected_food_kind = kind
        p.push_bubble(f"crafted {kind}", self.time_s, ttl=1.4, priority=85)
        return True

    def drop_food(self, x, y):
        p = self.get_focused()
        self.food.append(Food(x=float(x), y=float(y), kind=p.selected_food_kind))
        print(f"[t={self.t}] Food dropped: {p.selected_food_kind} at ({x},{y})")

    def spawn_ball(self, x: Optional[float] = None, y: Optional[float] = None):
        if x is None or y is None:
            p = self.get_focused()
            x = float(p.x + random.choice([-80, 80]))
            y = float(p.y - 120)

        ball = ToyBall(x=float(x), y=float(y), r=float(TOY_BALL_RADIUS))
        ball.w = ball.r * 2
        ball.h = ball.r * 2
        ball.vx = random.uniform(-250, 250)
        ball.vy = random.uniform(-100, 0)
        self.toys.append(ball)

        self.get_focused().push_bubble("ball!", self.time_s, ttl=1.2, priority=80)

    # ----------------------------
    # Desktop ground helpers
    # ----------------------------

    def ground_y(self) -> float:
        if self.work_area:
            l, t, r, b = self.work_area
            gy = float(b - self.offset_y)
            return clamp(gy, 0.0, float(self.height))
        return float(self.height - GROUND_MARGIN)

    def _taskbar_band_y(self) -> float:
        gy = self.ground_y()
        return max(0.0, gy - float(TASKBAR_DOCK_BAND))

    # ----------------------------
    # Enemy spawning
    # ----------------------------

    def spawn_enemy(self):
        if len(self.enemies) >= MAX_ENEMIES:
            return

        x = random.randint(50, max(51, self.width - 50))
        y = random.randint(50, max(51, self.height - 50))
        e = Enemy(eid=self.next_eid, x=float(x), y=float(y))

        e.skitter_phase = random.random() * math.tau
        e.skitter_freq = random.uniform(ENEMY_SKITTER_FREQ_MIN, ENEMY_SKITTER_FREQ_MAX)
        e.skitter_amp = random.uniform(ENEMY_SKITTER_AMP_MIN, ENEMY_SKITTER_AMP_MAX)

        e.chase_style = "direct"
        e.orbit_dir = random.choice([-1, 1])
        e.style_until = 0.0

        e.attack_cd = 0.0
        e.vx = 0.0
        e.vy = 0.0
        e.vx_desired = 0.0
        e.w = 24.0
        e.h = 24.0
        e.held = False
        e.on_ground = False
        e.last_impact = 0.0

        self.next_eid += 1
        self.enemies.append(e)
        print(f"[t={self.t}] Spawned Bug#{e.eid} at ({x},{y})")

    # ----------------------------
    # Physics
    # ----------------------------

    def _apply_steering(self, ent, max_speed: float, accel: float, dt: float):
        dv = float(ent.vx_desired) - float(ent.vx)
        step = accel * dt
        ent.vx = float(ent.vx) + clamp(dv, -step, step)
        ent.vx = clamp(ent.vx, -max_speed, max_speed)

    def _apply_physics_to_entity(self, ent, dt: float, max_speed: float, accel: float) -> None:
        gy = self.ground_y()
        feet_y = float(gy - (ent.h * 0.5))
        prev_vy = float(ent.vy)

        if getattr(ent, "held", False):
            ent.vx = 0.0
            ent.vy = 0.0
            ent.on_ground = False
            return

        self._apply_steering(ent, max_speed=max_speed, accel=accel, dt=dt)

        ent.vy = float(ent.vy) + GRAVITY * dt
        ent.vy = clamp(ent.vy, -MAX_FALL_SPEED, MAX_FALL_SPEED)

        ent.x = float(ent.x) + float(ent.vx) * dt
        ent.y = float(ent.y) + float(ent.vy) * dt

        ent.x = clamp(ent.x, 0.0, float(self.width))

        if ent.y >= feet_y:
            ent.y = feet_y
            if ent.vy > 0:
                ent.vy = 0.0
            ent.on_ground = True
            if prev_vy > 0:
                ent.last_impact = abs(prev_vy)
        else:
            ent.on_ground = False

        if not ent.on_ground:
            ent.vx = float(ent.vx) * (1.0 - AIR_DRAG)

        if ent.on_ground:
            if GROUND_MODE == "sticky":
                fr = GROUND_FRICTION_STICKY
                stop_eps = STOP_EPS_STICKY
            else:
                fr = GROUND_FRICTION_SKID
                stop_eps = STOP_EPS_SKID

            ent.vx = float(ent.vx) * (1.0 - fr)
            if abs(ent.vx) < stop_eps:
                ent.vx = 0.0

        ent.y = clamp(ent.y, 0.0, feet_y)

    def _apply_physics_to_ball(self, ball: ToyBall, dt: float):
        gy = self.ground_y()
        feet_y = float(gy - ball.r)
        prev_vy = float(ball.vy)

        if ball.held:
            ball.vx = 0.0
            ball.vy = 0.0
            ball.on_ground = False
            return

        ball.vy = float(ball.vy) + GRAVITY * dt
        ball.vy = clamp(ball.vy, -MAX_FALL_SPEED, MAX_FALL_SPEED)

        ball.x = float(ball.x) + float(ball.vx) * dt
        ball.y = float(ball.y) + float(ball.vy) * dt

        ball.x = clamp(ball.x, ball.r, float(self.width) - ball.r)

        if ball.y >= feet_y:
            ball.y = feet_y
            if ball.vy > 0:
                ball.vy = -prev_vy * TOY_BALL_BOUNCE
                if abs(ball.vy) < 40:
                    ball.vy = 0.0
            ball.on_ground = True
        else:
            ball.on_ground = False

        if ball.on_ground:
            ball.vx = float(ball.vx) * (1.0 - TOY_BALL_GROUND_FRICTION)
            if abs(ball.vx) < TOY_BALL_STOP_EPS:
                ball.vx = 0.0

    # ----------------------------
    # Helpers
    # ----------------------------

    def _nearest_food_to(self, p: Pet) -> Optional[Food]:
        if not self.food:
            return None
        best, best_d = None, 1e18
        for f in self.food:
            d = dist(p.x, p.y, f.x, f.y)
            if d < best_d:
                best, best_d = f, d
        return best

    def _nearest_enemy_to(self, p: Pet) -> Optional[Enemy]:
        if not self.enemies:
            return None
        best, best_d = None, 1e18
        for e in self.enemies:
            d = dist(p.x, p.y, e.x, e.y)
            if d < best_d:
                best, best_d = e, d
        return best

    def _nearest_ball_to(self, p: Pet) -> Optional[ToyBall]:
        if not self.toys:
            return None
        best, best_d = None, 1e18
        for b in self.toys:
            d = dist(p.x, p.y, b.x, b.y)
            if d < best_d:
                best, best_d = b, d
        return best

    def _enemy_near_pet(self, p: Pet, radius: float) -> bool:
        for e in self.enemies:
            if dist(p.x, p.y, e.x, e.y) <= radius:
                return True
        return False

    # ----------------------------
    # Mood/cursor/docking/landing
    # ----------------------------

    def _update_mood(self, p: Pet, dt: float):
        if p.mood > 0:
            p.mood = max(0.0, p.mood - MOOD_DECAY_PER_SEC * dt)
        elif p.mood < 0:
            p.mood = min(0.0, p.mood + MOOD_DECAY_PER_SEC * dt)

        if p.mood >= MOOD_HAPPY_THRESHOLD:
            p.mood_state = "happy"
        elif p.mood <= MOOD_SCARED_THRESHOLD:
            p.mood_state = "scared"
        elif p.mood <= MOOD_ANNOYED_THRESHOLD:
            p.mood_state = "annoyed"
        else:
            p.mood_state = "content"

    def _landing_reactions(self, p: Pet):
        if p.last_impact <= 0:
            return
        impact = p.last_impact
        p.last_impact = 0.0

        if impact >= LANDING_BIG:
            p.stagger_until = max(p.stagger_until, self.time_s + STAGGER_BIG_SECS)
            p.mood = clamp(p.mood - 0.20, -1.0, 1.0)
            p.push_bubble("oof", self.time_s, ttl=BUBBLE_TTL_SECS, priority=85)
            if p.on_ground and p.mood_state != "scared":
                p.vy = -RECOVERY_HOP_STRENGTH
        elif impact >= LANDING_SMALL:
            p.mood = clamp(p.mood - 0.07, -1.0, 1.0)
            p.push_bubble("!", self.time_s, ttl=1.4, priority=65)

    def _cursor_step(self, p: Pet):
        if self.cursor_x is None or self.cursor_y is None:
            return

        if p.cursor_react_cd > 0:
            p.cursor_react_cd = max(0.0, p.cursor_react_cd - (TICK_MS / 1000.0))

        d = dist(p.x, p.y, self.cursor_x, self.cursor_y)

        if d <= CURSOR_POKE_RADIUS and self.cursor_speed >= CURSOR_STILL_SPEED:
            if self.time_s - p.last_poke_time > 0.20:
                p.poke_count += 1
                p.last_poke_time = self.time_s
                p.mood = clamp(p.mood - CURSOR_POKE_IRRITATION, -1.0, 1.0)
                record_poke(p)

                if p.poke_count >= CURSOR_POKE_FOR_FRUSTRATION_JUMP and p.on_ground and not p.held:
                    p.push_bubble("NO.", self.time_s, ttl=BUBBLE_TTL_SECS, priority=90)
                    p.vy = -RECOVERY_HOP_STRENGTH * 1.15
                    p.poke_count = 0

        if self.time_s - p.last_poke_time > 5.0:
            p.poke_count = 0

        if p.cursor_react_cd > 0:
            return

        if d <= CURSOR_INTERACT_RADIUS:
            if self.cursor_speed >= CURSOR_FAST_SPEED:
                p.push_bubble("!!", self.time_s, ttl=1.2, priority=70)
                p.cursor_react_cd = CURSOR_REACT_COOLDOWN
            else:
                if p.mood_state == "happy":
                    p.push_bubble("♪", self.time_s, ttl=1.4, priority=55)
                    p.cursor_react_cd = CURSOR_REACT_COOLDOWN

    def _dock_step(self, p: Pet, dt: float):
        if p.held:
            p.docked = False
            p.dock_zone = "none"
            p.dock_progress = 0.0
            return

        if p.docked:
            if p.hunger >= DOCK_UNDOCK_HUNGER or self._enemy_near_pet(p, DOCK_ENEMY_ALERT_RADIUS):
                p.docked = False
                p.dock_zone = "none"
                p.dock_progress = 0.0
            return

        band_y = self._taskbar_band_y()
        near_taskbar = p.y >= band_y
        calm = p.mood_state in ("content", "happy")
        not_hungry = p.hunger < DOCK_UNDOCK_HUNGER
        safe = not self._enemy_near_pet(p, DOCK_ENEMY_ALERT_RADIUS)

        if near_taskbar and calm and not_hungry and safe:
            p.dock_progress += dt
            if p.dock_progress >= DOCK_MIN_SECS:
                p.docked = True
                p.dock_zone = "taskbar"
                p.push_bubble("comfy.", self.time_s, ttl=2.0, priority=75)
        else:
            p.dock_progress = max(0.0, p.dock_progress - dt * 2.0)

    # ----------------------------
    # Boredom
    # ----------------------------

    def _boredom_step(self, p: Pet, dt: float):
        if p._is_playing:
            p.boredom = clamp(p.boredom - BOREDOM_REDUCE_PER_SEC_PLAY * dt, 0.0, BOREDOM_MAX)
        else:
            p.boredom = clamp(p.boredom + BOREDOM_GAIN_PER_SEC * dt, 0.0, BOREDOM_MAX)

    # ----------------------------
    # AI
    # ----------------------------

    def _pet_idle_wander(self, p: Pet):
        if self.time_s < p.wander_pause_until:
            p.vx_desired = 0.0
            return

        if self.time_s >= p.wander_until or abs(p.wander_tx - p.x) < 20.0:
            p.wander_tx = float(random.randint(40, max(41, int(self.width) - 40)))
            move_secs = random.uniform(1.5, 3.2)
            pause_secs = random.uniform(0.3, 0.8)
            p.wander_until = self.time_s + move_secs
            p.wander_pause_until = p.wander_until + pause_secs

        dx = p.wander_tx - p.x
        p.vx_desired = sign(dx) * (PET_MAX_SPEED * 0.35)

    def _pet_ai_step(self, p: Pet):
        p._is_playing = False

        if p.held or self.time_s < p.stagger_until or p.docked:
            p.vx_desired = 0.0
            return

        # hungry -> food
        if p.hunger >= HUNGER_START_SEEK_FOOD and self.food:
            f = self._nearest_food_to(p)
            if f:
                dx = f.x - p.x
                p.vx_desired = sign(dx) * PET_MAX_SPEED
                if dist(p.x, p.y, f.x, f.y) <= FOOD_EAT_RANGE:
                    try:
                        self.food.remove(f)
                    except ValueError:
                        pass

                    spec = FOOD_TYPES.get(f.kind, FOOD_TYPES[DEFAULT_FOOD_KIND])
                    hunger_reduce = float(spec.get("hunger_reduce", 25.0))
                    heal = int(spec.get("heal", 1))
                    mood_boost = float(spec.get("mood_boost", 0.12))

                    p.hunger = clamp(p.hunger - hunger_reduce, 0.0, 100.0)
                    if heal > 0:
                        p.heal(heal)
                    p.mood = clamp(p.mood + mood_boost, -1.0, 1.0)

                    record_feed(p)
                    p.push_bubble(f"nom {f.kind}", self.time_s, ttl=1.4, priority=75)
                return

        # bored -> ball
        if p.boredom >= BOREDOM_SEEK_THRESHOLD and self.toys:
            b = self._nearest_ball_to(p)
            if b:
                d = dist(p.x, p.y, b.x, b.y)
                if d <= TOY_CHASE_RADIUS:
                    dx = b.x - p.x
                    p.vx_desired = sign(dx) * PET_MAX_SPEED
                    p._is_playing = True
                    if d <= 24.0 and p.on_ground:
                        b.vx += sign(b.x - p.x) * 220.0
                        b.vy -= 180.0
                        record_play_ball(p)
                        p.push_bubble("boop!", self.time_s, ttl=1.0, priority=60)
                    return

        # chase enemy
        e = self._nearest_enemy_to(p)
        if e:
            dx = e.x - p.x
            p.vx_desired = 0.0 if abs(dx) <= ATTACK_RANGE else sign(dx) * PET_MAX_SPEED
            p.target_eid = e.eid
            return

        p.target_eid = None
        self._pet_idle_wander(p)

    def _enemy_choose_style(self, e: Enemy):
        if self.time_s < e.style_until:
            return
        if random.random() < ENEMY_ORBIT_CHANCE:
            e.chase_style = "orbit"
            e.orbit_dir = random.choice([-1, 1])
            e.style_until = self.time_s + random.uniform(ENEMY_STYLE_MIN_SECS_ORBIT, ENEMY_STYLE_MAX_SECS_ORBIT)
        else:
            e.chase_style = "direct"
            e.style_until = self.time_s + random.uniform(ENEMY_STYLE_MIN_SECS_DIRECT, ENEMY_STYLE_MAX_SECS_DIRECT)

    def _enemy_ai_step(self):
        for e in self.enemies:
            if e.held:
                e.vx_desired = 0.0
                continue

            target = self.nearest_fenling_to(e.x, e.y)
            if not target:
                e.vx_desired = 0.0
                continue

            d = dist(e.x, e.y, target.x, target.y)
            chasing = d <= ENEMY_DETECT_RADIUS

            if chasing:
                self._enemy_choose_style(e)
                if e.chase_style == "orbit":
                    orbit_tx = target.x + e.orbit_dir * ENEMY_ORBIT_RADIUS
                    dx = orbit_tx - e.x
                else:
                    dx = target.x - e.x
                base = 0.0 if abs(target.x - e.x) <= ATTACK_RANGE * 1.2 else sign(dx) * ENEMY_MAX_SPEED
            else:
                base = (random.choice([-1, 1]) * 0.55 * ENEMY_MAX_SPEED)
                if random.random() < 0.25:
                    base = 0.0

            if ENEMY_SKITTER_ON and abs(base) > 40 and abs(target.x - e.x) > ATTACK_RANGE * 1.2:
                osc = math.sin(e.skitter_phase + self.time_s * e.skitter_freq)
                base = base + osc * e.skitter_amp

            e.vx_desired = base

            if e.on_ground and (self.time_s - getattr(e, "last_jump_time", 0.0)) >= ENEMY_JUMP_COOLDOWN:
                rate = ENEMY_CHASE_HOP_RATE if chasing else ENEMY_WANDER_HOP_RATE
                if random.random() < rate * AI_STEP_SECS:
                    e.vy = -ENEMY_JUMP_STRENGTH
                    e.last_jump_time = self.time_s

    # ----------------------------
    # Combat + loot
    # ----------------------------

    def _combat_step(self, dt: float):
        for p in self.fenlings:
            if p.attack_cd > 0:
                p.attack_cd = max(0.0, p.attack_cd - dt)

        for e in list(self.enemies):
            if e.attack_cd > 0:
                e.attack_cd = max(0.0, e.attack_cd - dt)

            target = self.nearest_fenling_to(e.x, e.y)
            if target and dist(target.x, target.y, e.x, e.y) <= ATTACK_RANGE:
                if (not e.held) and e.attack_cd <= 0.0 and (not target.held):
                    target.take_damage(ENEMY_DAMAGE)
                    e.attack_cd = ENEMY_ATTACK_COOLDOWN
                    target.vx += sign(target.x - e.x) * 100.0
                    target.mood = clamp(target.mood - 0.08, -1.0, 1.0)

            for p in self.fenlings:
                if p.held:
                    continue
                if dist(p.x, p.y, e.x, e.y) <= ATTACK_RANGE and p.attack_cd <= 0.0:
                    e.hp -= PET_DAMAGE
                    p.attack_cd = PET_ATTACK_COOLDOWN
                    e.vx += sign(e.x - p.x) * 120.0

                    if e.hp <= 0:
                        self.enemies.remove(e)
                        bits = random.randint(BUG_BITS_DROP_MIN, BUG_BITS_DROP_MAX)
                        p.inventory["bug_bits"] = p.inventory.get("bug_bits", 0) + bits
                        p.add_xp(5)
                        p.mood = clamp(p.mood + 0.12, -1.0, 1.0)
                        p.push_bubble(f"+{bits} bits", self.time_s, ttl=1.4, priority=85)
                        break

    # ----------------------------
    # Main tick
    # ----------------------------

    def tick(self):
        if self.paused:
            return

        self.t += 1
        dt = TICK_MS / 1000.0
        self.time_s += dt

        if self.t % SPAWN_INTERVAL_TICKS == 0:
            self.spawn_enemy()

        for p in self.fenlings:
            p.tick_needs()
            if p.bubble_cd > 0:
                p.bubble_cd = max(0.0, p.bubble_cd - dt)

            self._update_mood(p, dt)
            self._cursor_step(p)
            self._dock_step(p, dt)
            self._boredom_step(p, dt)

        self._ai_accum += dt
        if self._ai_accum >= AI_STEP_SECS:
            self._ai_accum = 0.0
            for p in self.fenlings:
                self._pet_ai_step(p)
            self._enemy_ai_step()

        for p in self.fenlings:
            self._apply_physics_to_entity(p, dt=dt, max_speed=PET_MAX_SPEED, accel=PET_ACCEL)
        for e in self.enemies:
            self._apply_physics_to_entity(e, dt=dt, max_speed=ENEMY_MAX_SPEED, accel=ENEMY_ACCEL)
        for b in self.toys:
            self._apply_physics_to_ball(b, dt=dt)

        for p in self.fenlings:
            self._landing_reactions(p)

        self._combat_step(dt)

        for p in self.fenlings:
            if p.bubbles:
                p.bubbles = [bb for bb in p.bubbles if bb["until"] > self.time_s]