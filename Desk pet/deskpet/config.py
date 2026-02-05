from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"

PET_SPRITES = {
    "idle": ASSETS_DIR / "fenrir1.png",
    "alt": ASSETS_DIR / "fenrir2.png",
}

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
TICK_MS = 50

SPAWN_INTERVAL_TICKS = 200
MAX_ENEMIES = 3

ATTACK_RANGE = 26
FOOD_EAT_RANGE = 22
HUNGER_START_SEEK_FOOD = 25.0

# ----------------------------
# Physics / ground
# ----------------------------
GRAVITY = 2400.0
MAX_FALL_SPEED = 2400.0
GROUND_MARGIN = 10
AIR_DRAG = 0.01

GROUND_MODE = "skid"  # "skid" or "sticky"
GROUND_FRICTION_STICKY = 0.28
GROUND_FRICTION_SKID = 0.10
STOP_EPS_STICKY = 22.0
STOP_EPS_SKID = 12.0

# ----------------------------
# Drag / throw
# ----------------------------
THROW_MODE = "gentle"  # "gentle" or "yeet"
THROW_SMOOTHING = 0.35

THROW_SCALE_GENTLE = 0.70
MAX_THROW_SPEED_GENTLE = 1400.0

THROW_SCALE_YEET = 1.25
MAX_THROW_SPEED_YEET = 2400.0

# ----------------------------
# Movement + AI
# ----------------------------
PET_MAX_SPEED = 520.0
PET_ACCEL = 2400.0

ENEMY_MAX_SPEED = 420.0
ENEMY_ACCEL = 2100.0

ENEMY_DETECT_RADIUS = 240.0
ENEMY_ORBIT_CHANCE = 0.30
ENEMY_ORBIT_RADIUS = 90.0
ENEMY_STYLE_MIN_SECS_DIRECT = 1.2
ENEMY_STYLE_MAX_SECS_DIRECT = 2.4
ENEMY_STYLE_MIN_SECS_ORBIT = 0.8
ENEMY_STYLE_MAX_SECS_ORBIT = 1.6

ENEMY_SKITTER_ON = True
ENEMY_SKITTER_AMP_MIN = 35.0
ENEMY_SKITTER_AMP_MAX = 85.0
ENEMY_SKITTER_FREQ_MIN = 7.0
ENEMY_SKITTER_FREQ_MAX = 12.0

ENEMY_JUMP_STRENGTH = 950.0
ENEMY_JUMP_COOLDOWN = 1.5
ENEMY_WANDER_HOP_RATE = 0.20
ENEMY_CHASE_HOP_RATE = 0.25

PET_ATTACK_COOLDOWN = 0.45
ENEMY_ATTACK_COOLDOWN = 0.65
PET_DAMAGE = 2
ENEMY_DAMAGE = 1

AI_STEP_SECS = 0.35

# ----------------------------
# Mood + bubbles + docking + landing reactions
# ----------------------------
MOOD_START = 0.15
MOOD_DECAY_PER_SEC = 0.010
MOOD_HAPPY_THRESHOLD = 0.45
MOOD_ANNOYED_THRESHOLD = -0.35
MOOD_SCARED_THRESHOLD = -0.70

CURSOR_INTERACT_RADIUS = 80
CURSOR_POKE_RADIUS = 40

CURSOR_STILL_SPEED = 40.0
CURSOR_FAST_SPEED = 250.0

CURSOR_REACT_COOLDOWN = 1.0
CURSOR_POKE_IRRITATION = 0.12
CURSOR_POKE_FOR_FRUSTRATION_JUMP = 5

BUBBLE_TTL_SECS = 2.2

DOCK_MIN_SECS = 6.0
TASKBAR_DOCK_BAND = 90
DOCK_UNDOCK_HUNGER = 30.0
DOCK_ENEMY_ALERT_RADIUS = 240.0

LANDING_SMALL = 700.0
LANDING_BIG = 1300.0
RECOVERY_HOP_STRENGTH = 420.0
STAGGER_BIG_SECS = 0.45

# ----------------------------
# Inventory + Food Types + Crafting + Hotbar
# ----------------------------

BUG_BITS_DROP_MIN = 1
BUG_BITS_DROP_MAX = 3

FOOD_TYPES = {
    "kibble": {"hunger_reduce": 25.0, "heal": 1, "cost_bug_bits": 0},
    "meat":   {"hunger_reduce": 40.0, "heal": 3, "cost_bug_bits": 2},
    "treat":  {"hunger_reduce": 15.0, "heal": 0, "mood_boost": 0.22, "cost_bug_bits": 1},
}

DEFAULT_FOOD_KIND = "kibble"

HOTBAR_HEIGHT = 64
HOTBAR_PAD = 10
HOTBAR_SLOT_W = 120
HOTBAR_SLOT_H = 44
HOTBAR_SLOT_GAP = 10

# ----------------------------
# Wave 6: Toys + Boredom
# ----------------------------
BOREDOM_START = 15.0
BOREDOM_MAX = 100.0
BOREDOM_GAIN_PER_SEC = 1.6      # grows while idle-ish
BOREDOM_REDUCE_PER_SEC_PLAY = 8.0  # reduces while chasing toy
BOREDOM_SEEK_THRESHOLD = 45.0

TOY_BALL_RADIUS = 10.0
TOY_BALL_BOUNCE = 0.35
TOY_BALL_GROUND_FRICTION = 0.08
TOY_BALL_STOP_EPS = 10.0
TOY_SPAWN_BUBBLE_TTL = 1.2
TOY_CHASE_RADIUS = 520.0