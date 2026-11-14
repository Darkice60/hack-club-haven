import asyncio
import math
import random
from dataclasses import dataclass
from typing import List, Tuple
import pygame

from ball import Ghost, MiniGhost, Soul
from upgrades import UpgradeManager, format_number

# 1000 x 700 window and layout dimensions
WINDOW_WIDTH: int = 1000
WINDOW_HEIGHT: int = 700
PANEL_WIDTH: int = 300
PLAY_WIDTH: int = WINDOW_WIDTH - PANEL_WIDTH  # 700 px
PLAY_HEIGHT: int = WINDOW_HEIGHT              # 700 px
TARGET_FPS: int = 60

# Combo streak settings (capped at 20x)
COMBO_WINDOW: float = 2.4
MAX_COMBO: int = 20


@dataclass
class Particle:
    """Small spectral or autumn spark emitted when eating Souls, boosting, or rebirthing."""

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: Tuple[int, int, int]
    life: float
    max_life: float


@dataclass
class Shockwave:
    """Expanding spirit ring when the Ghost eats a Soul or performs a Rebirth."""

    x: float
    y: float
    start_radius: float
    radius: float
    max_radius: float
    color: Tuple[int, int, int]
    life: float = 0.28
    max_life: float = 0.28


@dataclass
class FloatingText:
    """Rising '+X' or 'REBIRTH!' popup in the autumn woods."""

    x: float
    y: float
    text: str
    color: Tuple[int, int, int]
    life: float = 0.85


@dataclass
class ClickRipple:
    """Expanding warm amber or wind-green ring showing where the player clicked."""

    x: float
    y: float
    color: Tuple[int, int, int]
    radius: float = 6.0
    max_radius: float = 42.0
    life: float = 0.35


@dataclass
class FallingLeaf:
    """Decorative autumn leaf drifting gently in the forest background."""

    x: float
    y: float
    vy: float
    sway_phase: float
    sway_speed: float
    size: int
    color: Tuple[int, int, int]


def create_autumn_leaves(count: int = 22) -> List[FallingLeaf]:
    """Generate ambient falling autumn leaves for the 700x700 forest backdrop."""
    palette = [
        (168, 58, 22),
        (198, 86, 26),
        (216, 128, 34),
        (142, 46, 20),
    ]
    leaves: List[FallingLeaf] = []
    for _ in range(count):
        leaves.append(
            FallingLeaf(
                x=random.uniform(14.0, PLAY_WIDTH - 14.0),
                y=random.uniform(0.0, PLAY_HEIGHT),
                vy=random.uniform(18.0, 38.0),
                sway_phase=random.uniform(0.0, math.tau),
                sway_speed=random.uniform(1.5, 3.0),
                size=random.randint(4, 6),
                color=random.choice(palette),
            )
        )
    return leaves


def spawn_soul(
    arena_width: int,
    arena_height: int,
    ghost: Ghost,
    existing_souls: List[Soul],
    upgrade_manager: UpgradeManager,
) -> Soul:
    """
    Spawn a Normal, Golden (5x), or Devil (15x) Soul inside the autumn woods
    while avoiding overlapping the Ghost or existing Souls.
    """
    size = upgrade_manager.soul_size
    margin = size + 10.0
    min_x = margin
    max_x = max(margin, arena_width - margin)
    min_y = margin
    max_y = max(margin, arena_height - margin)

    best_x = random.uniform(min_x, max_x)
    best_y = random.uniform(min_y, max_y)
    best_clearance = -1.0

    for _ in range(60):
        cx = random.uniform(min_x, max_x)
        cy = random.uniform(min_y, max_y)

        ghost_dist = math.hypot(cx - ghost.x, cy - ghost.y)
        ghost_clearance = ghost_dist - (ghost.size + size + 32.0)

        if ghost_clearance < 0.0:
            if ghost_clearance > best_clearance:
                best_clearance = ghost_clearance
                best_x, best_y = cx, cy
            continue

        overlaps_other = False
        for other in existing_souls:
            if math.hypot(cx - other.x, cy - other.y) < (other.size + size + 8.0):
                overlaps_other = True
                break

        if not overlaps_other:
            best_x, best_y = cx, cy
            break

        if ghost_clearance > best_clearance:
            best_clearance = ghost_clearance
            best_x, best_y = cx, cy

    variant = upgrade_manager.roll_soul_variant()
    return Soul(
        x=best_x,
        y=best_y,
        speed=upgrade_manager.soul_speed,
        size=size,
        base_point_value=upgrade_manager.soul_points,
        arena_width=arena_width,
        arena_height=arena_height,
        soul_type=variant,
    )


def spawn_burst(
    particles: List[Particle],
    x: float,
    y: float,
    color: Tuple[int, int, int],
    count: int = 10,
    speed_range: Tuple[float, float] = (50.0, 175.0),
) -> None:
    """Create a radial burst of small particles."""
    for _ in range(count):
        angle = random.uniform(0.0, math.tau)
        spd = random.uniform(*speed_range)
        life = random.uniform(0.25, 0.50)
        particles.append(
            Particle(
                x=x,
                y=y,
                vx=math.cos(angle) * spd,
                vy=math.sin(angle) * spd,
                radius=random.uniform(2.0, 4.2),
                color=color,
                life=life,
                max_life=life,
            )
        )


def _draw_wooden_bridge(
    surface: pygame.Surface,
    x: int,
    y: int,
    width: int,
    trunk_centers: List[int],
) -> None:
    """Draw a classic 16-bit wooden boardwalk ledge with diagonal support struts."""
    plank_h = 11
    rect = pygame.Rect(x, y, width, plank_h)

    # Support braces & pegs anchored under the walkway at each tree trunk
    for tx in trunk_centers:
        if x + 28 <= tx <= x + width - 28:
            # Diagonal left and right support struts
            pygame.draw.line(surface, (42, 20, 10), (tx - 38, y + plank_h), (tx - 10, y + 36), 6)
            pygame.draw.line(surface, (148, 82, 36), (tx - 38, y + plank_h), (tx - 10, y + 36), 3)

            pygame.draw.line(surface, (42, 20, 10), (tx + 38, y + plank_h), (tx + 10, y + 36), 6)
            pygame.draw.line(surface, (148, 82, 36), (tx + 38, y + plank_h), (tx + 10, y + 36), 3)

            # Small pointed wooden peg directly below the plank
            peg = [(tx - 6, y + plank_h), (tx + 6, y + plank_h), (tx, y + plank_h + 15)]
            pygame.draw.polygon(surface, (156, 86, 38), peg)
            pygame.draw.polygon(surface, (36, 18, 10), peg, width=1)

    # Main horizontal plank beam
    pygame.draw.rect(surface, (158, 86, 38), rect, border_radius=2)
    pygame.draw.line(surface, (206, 128, 62), (x + 2, y + 2), (x + width - 3, y + 2), 2)
    pygame.draw.line(surface, (96, 48, 20), (x + 2, y + plank_h - 3), (x + width - 3, y + plank_h - 3), 2)
    pygame.draw.rect(surface, (36, 18, 10), rect, width=2, border_radius=2)

    # Individual vertical plank dividers
    for px in range(x + 18, x + width - 8, 20):
        pygame.draw.line(surface, (52, 26, 13), (px, y + 1), (px, y + plank_h - 2), 2)


def _draw_pumpkin(
    surface: pygame.Surface,
    cx: int,
    bottom_y: int,
    radius_x: int = 18,
    radius_y: int = 14,
    is_jack_o_lantern: bool = False,
    time_sec: float = 0.0,
) -> None:
    """Draw a ribbed autumn pumpkin or flickering Jack-o'-Lantern sitting on a ledge."""
    cy = bottom_y - radius_y

    # Curved green-brown pumpkin stem
    stem_pts = [(cx - 3, cy - radius_y + 2), (cx + 2, cy - radius_y - 6), (cx + 6, cy - radius_y - 4), (cx + 2, cy - radius_y + 2)]
    pygame.draw.polygon(surface, (76, 94, 34), stem_pts)

    # Outer dark outline & plump orange body
    body_rect = pygame.Rect(cx - radius_x, cy - radius_y, radius_x * 2, radius_y * 2)
    pygame.draw.ellipse(surface, (182, 74, 20), body_rect)
    pygame.draw.ellipse(surface, (214, 96, 28), pygame.Rect(cx - radius_x + 4, cy - radius_y + 2, (radius_x - 4) * 2, (radius_y - 3) * 2))
    pygame.draw.ellipse(surface, (42, 18, 8), body_rect, width=2)

    # Vertical pumpkin rib curves
    pygame.draw.ellipse(surface, (124, 44, 14), pygame.Rect(cx - radius_x // 2, cy - radius_y + 1, radius_x, radius_y * 2 - 2), width=1)

    if is_jack_o_lantern:
        flicker = math.sin(time_sec * 14.0)
        glow_col = (255, 224, 88) if flicker > -0.2 else (255, 168, 44)

        # Flickering flame wisps above the Jack-o'-Lantern
        for idx, (ox, h_scale) in enumerate([(-6, 16), (0, 24), (6, 15)]):
            wave = math.sin(time_sec * 11.0 + idx * 1.7) * 3.0
            flame_pts = [
                (cx + ox - 4, cy - radius_y + 2),
                (int(cx + ox + wave), int(cy - radius_y - h_scale - flicker * 2)),
                (cx + ox + 4, cy - radius_y + 2),
            ]
            pygame.draw.polygon(surface, (238, 88, 24), flame_pts)
            inner_pts = [
                (cx + ox - 2, cy - radius_y + 2),
                (int(cx + ox + wave * 0.7), int(cy - radius_y - h_scale * 0.65)),
                (cx + ox + 2, cy - radius_y + 2),
            ]
            pygame.draw.polygon(surface, glow_col, inner_pts)

        # Glowing triangular eyes & jagged smile
        left_eye = [(cx - 9, cy - 2), (cx - 5, cy - 8), (cx - 2, cy - 2)]
        right_eye = [(cx + 2, cy - 2), (cx + 5, cy - 8), (cx + 9, cy - 2)]
        pygame.draw.polygon(surface, glow_col, left_eye)
        pygame.draw.polygon(surface, glow_col, right_eye)

        mouth_pts = [
            (cx - 10, cy + 4),
            (cx - 5, cy + 8),
            (cx, cy + 5),
            (cx + 5, cy + 8),
            (cx + 10, cy + 4),
            (cx + 6, cy + 10),
            (cx - 6, cy + 10),
        ]
        pygame.draw.polygon(surface, glow_col, mouth_pts)


def draw_autumn_background(
    surface: pygame.Surface,
    leaves: List[FallingLeaf],
    time_sec: float = 0.0,
) -> None:
    """
    Render a rich 16-bit autumn forest backdrop inspired by classic woodland stages:
    dappled burnt-orange forest shafts, ridged tree trunks with angled branches,
    red-orange foliage canopies, wooden walkways, and autumn pumpkins.
    """
    arena_rect = pygame.Rect(0, 0, PLAY_WIDTH, PLAY_HEIGHT)
    pygame.draw.rect(surface, (44, 19, 11), arena_rect)

    # 1. Distant dappled burnt-orange & sienna woodland backdrop columns
    distant_shafts = [
        (0, 88, (76, 33, 16)),
        (88, 62, (56, 24, 12)),
        (150, 120, (96, 42, 19)),
        (270, 74, (64, 28, 14)),
        (344, 130, (108, 48, 21)),
        (474, 68, (60, 26, 13)),
        (542, 110, (92, 40, 18)),
        (652, 48, (54, 23, 12)),
    ]
    for sx, sw, scol in distant_shafts:
        pygame.draw.rect(surface, scol, pygame.Rect(sx, 0, sw, PLAY_HEIGHT))
        # Subtle vertical woodland bark/foliage grain streaks
        for gx in range(sx + 8, sx + sw - 4, 14):
            pygame.draw.line(surface, (42, 18, 10), (gx, 40), (gx, PLAY_HEIGHT - 30), 2)

    # Jagged distant tree canopy silhouettes in warm russet
    for bx in range(0, PLAY_WIDTH + 40, 48):
        peak_h = 135 + ((bx * 37) % 65)
        tri = [(bx - 32, 40), (bx + 32, 40), (bx, peak_h)]
        pygame.draw.polygon(surface, (118, 52, 22), tri)

    # 2. Prominent Hero Tree Trunks & Angled Limbs
    # Left-center main hero tree trunk + right secondary trunk
    trunks = [
        (158, 94),
        (524, 68),
    ]
    for tx, tw in trunks:
        # Dark outer outline + rich mahogany bark fill
        pygame.draw.rect(surface, (28, 14, 8), pygame.Rect(tx - 3, 0, tw + 6, PLAY_HEIGHT))
        pygame.draw.rect(surface, (58, 30, 17), pygame.Rect(tx, 0, tw, PLAY_HEIGHT))

        # Highlight strip on right side of trunk + vertical bark ridges
        pygame.draw.rect(surface, (78, 42, 23), pygame.Rect(tx + tw - 18, 0, 14, PLAY_HEIGHT))
        for rx in range(tx + 10, tx + tw - 6, 14):
            pygame.draw.line(surface, (34, 17, 10), (rx, 0), (rx, PLAY_HEIGHT), 3)
            pygame.draw.line(surface, (92, 50, 27), (rx + 4, 0), (rx + 4, PLAY_HEIGHT), 1)

    # Angled tree branches reaching out from the main hero trunk (x=158..252)
    left_branch = [(160, 185), (160, 148), (88, 86), (72, 104)]
    pygame.draw.polygon(surface, (58, 30, 17), left_branch)
    pygame.draw.polygon(surface, (28, 14, 8), left_branch, width=2)

    right_branch = [(250, 210), (250, 172), (324, 106), (340, 124)]
    pygame.draw.polygon(surface, (66, 35, 19), right_branch)
    pygame.draw.polygon(surface, (28, 14, 8), right_branch, width=2)

    # 3. Lush Red-Orange Autumn Leaf Clusters on Branches & Top Canopy
    branch_foliage = [
        (82, 82, 38, (148, 44, 18)),
        (104, 72, 32, (186, 68, 22)),
        (68, 92, 26, (206, 96, 28)),
        (332, 102, 40, (148, 44, 18)),
        (312, 92, 32, (188, 70, 22)),
        (348, 114, 28, (210, 102, 30)),
    ]
    for fx, fy, fr, fcol in branch_foliage:
        pygame.draw.circle(surface, (36, 16, 8), (fx, fy), fr + 2)
        pygame.draw.circle(surface, fcol, (fx, fy), fr)

    # Dense overhanging autumn canopy across the top edge
    pygame.draw.rect(surface, (64, 22, 11), pygame.Rect(0, 0, PLAY_WIDTH, 34))
    top_canopy = [
        (24, 16, 44, (138, 42, 16)),
        (84, 12, 48, (176, 62, 20)),
        (148, 18, 42, (152, 46, 18)),
        (218, 10, 50, (196, 82, 24)),
        (286, 16, 44, (164, 54, 19)),
        (356, 10, 52, (204, 92, 26)),
        (430, 16, 46, (146, 44, 17)),
        (502, 12, 50, (184, 68, 22)),
        (574, 18, 44, (158, 50, 18)),
        (648, 12, 48, (194, 80, 24)),
        (700, 18, 40, (148, 44, 17)),
    ]
    for cx, cy, cr, ccol in top_canopy:
        pygame.draw.circle(surface, (36, 16, 8), (cx, cy), cr + 2)
        pygame.draw.circle(surface, ccol, (cx, cy), cr)

    # 4. Rustic Wooden Boardwalk & Lower Ledge
    trunk_centers = [158 + 94 // 2, 524 + 68 // 2]
    _draw_wooden_bridge(surface, x=0, y=496, width=PLAY_WIDTH, trunk_centers=trunk_centers)
    _draw_wooden_bridge(surface, x=48, y=624, width=350, trunk_centers=trunk_centers)

    # 5. Pumpkins & Flickering Jack-o'-Lantern
    _draw_pumpkin(surface, cx=112, bottom_y=496, radius_x=18, radius_y=14, is_jack_o_lantern=False)
    _draw_pumpkin(
        surface,
        cx=336,
        bottom_y=496,
        radius_x=19,
        radius_y=15,
        is_jack_o_lantern=True,
        time_sec=time_sec,
    )
    _draw_pumpkin(surface, cx=96, bottom_y=624, radius_x=17, radius_y=13, is_jack_o_lantern=False)

    # 6. Leafy Autumn Forest Floor Undergrowth
    pygame.draw.rect(surface, (38, 18, 10), pygame.Rect(0, PLAY_HEIGHT - 26, PLAY_WIDTH, 26))
    for fx in range(0, PLAY_WIDTH + 30, 34):
        bush_col = (118, 46, 18) if (fx // 34) % 2 == 0 else (148, 62, 22)
        pygame.draw.circle(surface, bush_col, (fx, PLAY_HEIGHT - 22), 20)
    pygame.draw.line(surface, (176, 78, 26), (0, PLAY_HEIGHT - 26), (PLAY_WIDTH, PLAY_HEIGHT - 26), 2)

    # 7. Ambient Falling Autumn Leaves
    for leaf in leaves:
        lx = int(leaf.x + math.sin(leaf.sway_phase) * 9.0)
        ly = int(leaf.y)
        s = leaf.size
        pts = [(lx, ly - s), (lx + s + 1, ly), (lx, ly + s), (lx - s - 1, ly)]
        pygame.draw.polygon(surface, leaf.color, pts)


async def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("BOUNCE BACK - Autumn Spirit")
    clock = pygame.time.Clock()

    arena_surface = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT))

    font_hud = pygame.font.Font(None, 26)
    font_combo = pygame.font.Font(None, 22)
    font_hint = pygame.font.Font(None, 24)
    font_popup = pygame.font.Font(None, 25)

    upgrade_manager = UpgradeManager(
        panel_x=PLAY_WIDTH,
        panel_width=PANEL_WIDTH,
        panel_height=WINDOW_HEIGHT,
    )

    ghost = Ghost(
        x=PLAY_WIDTH / 2.0,
        y=PLAY_HEIGHT / 2.0,
        speed=upgrade_manager.INITIAL_GHOST_SPEED,
        size=upgrade_manager.INITIAL_GHOST_SIZE,
        arena_width=PLAY_WIDTH,
        arena_height=PLAY_HEIGHT,
    )

    mini_ghosts: List[MiniGhost] = []
    souls: List[Soul] = []
    while len(souls) < upgrade_manager.soul_target_count:
        souls.append(spawn_soul(PLAY_WIDTH, PLAY_HEIGHT, ghost, souls, upgrade_manager))

    particles: List[Particle] = []
    shockwaves: List[Shockwave] = []
    floating_texts: List[FloatingText] = []
    ripples: List[ClickRipple] = []
    leaves: List[FallingLeaf] = create_autumn_leaves(22)

    has_nudged_once = False
    combo_count: int = 0
    combo_timer: float = 0.0
    shake_timer: float = 0.0
    elapsed_time: float = 0.0

    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)
        elapsed_time += dt
        mouse_pos = pygame.mouse.get_pos()

        # 1. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx < PLAY_WIDTH:
                    accepted, gusted = ghost.nudge_toward(mx, my)
                    if accepted:
                        ripple_col = (120, 245, 200) if gusted else (235, 148, 56)
                        ripples.append(ClickRipple(x=float(mx), y=float(my), color=ripple_col))
                        if gusted:
                            spawn_burst(
                                particles,
                                ghost.x,
                                ghost.y,
                                color=(145, 248, 215),
                                count=8,
                                speed_range=(40.0, 120.0),
                            )
                        has_nudged_once = True
                    else:
                        # Subtle muted ripple if player clicks while 0.8s cooldown is active
                        ripples.append(
                            ClickRipple(
                                x=float(mx),
                                y=float(my),
                                color=(150, 95, 85),
                                radius=4.0,
                                max_radius=18.0,
                                life=0.20,
                            )
                        )
                else:
                    action = upgrade_manager.handle_click(
                        (mx, my), ghost, souls, mini_ghosts
                    )
                    if action == "soul_count":
                        while len(souls) < upgrade_manager.soul_target_count:
                            souls.append(
                                spawn_soul(
                                    PLAY_WIDTH, PLAY_HEIGHT, ghost, souls, upgrade_manager
                                )
                            )
                    elif action == "rebirth":
                        combo_count = 0
                        combo_timer = 0.0
                        souls.clear()
                        while len(souls) < upgrade_manager.soul_target_count:
                            souls.append(
                                spawn_soul(
                                    PLAY_WIDTH, PLAY_HEIGHT, ghost, souls, upgrade_manager
                                )
                            )

                        shake_timer = 0.22
                        spawn_burst(
                            particles,
                            ghost.x,
                            ghost.y,
                            color=(205, 135, 255),
                            count=28,
                            speed_range=(70.0, 260.0),
                        )
                        shockwaves.append(
                            Shockwave(
                                x=ghost.x,
                                y=ghost.y,
                                start_radius=ghost.size,
                                radius=ghost.size,
                                max_radius=ghost.size + 140.0,
                                color=(218, 155, 255),
                                life=0.55,
                                max_life=0.55,
                            )
                        )
                        floating_texts.append(
                            FloatingText(
                                x=ghost.x,
                                y=ghost.y - ghost.size - 10.0,
                                text=f"REBIRTH {upgrade_manager.rebirth_count}! BLACK HOLE!",
                                color=(235, 185, 255),
                                life=1.40,
                            )
                        )

        # 2. Physics & State Updates
        if combo_timer > 0.0:
            combo_timer = max(0.0, combo_timer - dt)
            if combo_timer == 0.0:
                combo_count = 0

        if shake_timer > 0.0:
            shake_timer = max(0.0, shake_timer - dt)

        ghost.update(dt)
        if ghost.just_triggered_boost:
            spawn_burst(
                particles,
                ghost.x,
                ghost.y,
                color=(245, 165, 55),
                count=14,
                speed_range=(70.0, 200.0),
            )

        for mg in mini_ghosts:
            mg.update(dt)

        soul_nearby = False
        eat_anticipation_dist = ghost.size + upgrade_manager.soul_size + 32.0
        bh_radius = ghost.black_hole_radius

        for soul in souls:
            soul.update(dt)
            if bh_radius > 0.0:
                soul.pull_toward(
                    ghost.x,
                    ghost.y,
                    bh_radius,
                    ghost.black_hole_strength,
                    dt,
                )
            if math.hypot(soul.x - ghost.x, soul.y - ghost.y) <= eat_anticipation_dist:
                soul_nearby = True

        # Check collisions between Ghost (or Mini Ghosts) and Souls
        for idx, soul in enumerate(souls):
            eaten_by_main = ghost.collides_with(soul)
            eaten_by_mini = (not eaten_by_main) and any(
                mg.collides_with(soul) for mg in mini_ghosts
            )

            if eaten_by_main or eaten_by_mini:
                if eaten_by_main:
                    combo_count = min(MAX_COMBO, combo_count + 1)
                    combo_timer = COMBO_WINDOW
                    ghost.trigger_chomp()

                streak_bonus = (
                    (combo_count // 4) * upgrade_manager.soul_points if eaten_by_main else 0
                )
                earned = (soul.point_value + streak_bonus) * upgrade_manager.rebirth_multiplier
                upgrade_manager.add_points(earned)

                if soul.soul_type == "devil":
                    burst_col = (255, 68, 98)
                    burst_count = 18
                    wave_max = soul.size + 52.0
                    popup_color = (255, 110, 132)
                    prefix = "DEVIL! "
                    shake_timer = max(shake_timer, 0.11)
                elif soul.soul_type == "golden":
                    burst_col = (255, 218, 72)
                    burst_count = 14
                    wave_max = soul.size + 42.0
                    popup_color = (255, 228, 95)
                    prefix = "GOLD! "
                    shake_timer = max(shake_timer, 0.08)
                else:
                    burst_col = (115, 245, 215)
                    burst_count = 10
                    wave_max = soul.size + 30.0
                    popup_color = (165, 255, 230)
                    prefix = ""
                    if eaten_by_main:
                        shake_timer = max(shake_timer, 0.05)

                spawn_burst(particles, soul.x, soul.y, color=burst_col, count=burst_count)
                shockwaves.append(
                    Shockwave(
                        x=soul.x,
                        y=soul.y,
                        start_radius=soul.size,
                        radius=soul.size,
                        max_radius=wave_max,
                        color=burst_col,
                    )
                )

                popup_label = f"{prefix}+{format_number(earned)}"
                if streak_bonus > 0:
                    popup_label += f" ({combo_count}x)"

                floating_texts.append(
                    FloatingText(
                        x=soul.x,
                        y=soul.y - soul.size,
                        text=popup_label,
                        color=popup_color,
                    )
                )

                others = [s for i, s in enumerate(souls) if i != idx]
                souls[idx] = spawn_soul(
                    PLAY_WIDTH, PLAY_HEIGHT, ghost, others, upgrade_manager
                )

        # Update ambient leaves, visual effects & UI timers
        upgrade_manager.update(dt)

        for leaf in leaves:
            leaf.y += leaf.vy * dt
            leaf.sway_phase = (leaf.sway_phase + leaf.sway_speed * dt) % math.tau
            if leaf.y > PLAY_HEIGHT + 10:
                leaf.y = -10.0
                leaf.x = random.uniform(14.0, PLAY_WIDTH - 14.0)

        for p in particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
        particles = [p for p in particles if p.life > 0.0]

        for sw in shockwaves:
            sw.life -= dt
            progress = 1.0 - max(0.0, sw.life / sw.max_life)
            sw.radius = sw.start_radius + (sw.max_radius - sw.start_radius) * progress
        shockwaves = [sw for sw in shockwaves if sw.life > 0.0]

        for ft in floating_texts:
            ft.y -= 38.0 * dt
            ft.life -= dt
        floating_texts = [ft for ft in floating_texts if ft.life > 0.0]

        for rp in ripples:
            rp.life -= dt
            progress = 1.0 - max(0.0, rp.life / 0.35)
            rp.radius = 6.0 + (rp.max_radius - 6.0) * progress
        ripples = [rp for rp in ripples if rp.life > 0.0]

        # 3. Rendering onto the arena surface
        draw_autumn_background(arena_surface, leaves, time_sec=elapsed_time)

        for rp in ripples:
            pygame.draw.circle(
                arena_surface,
                rp.color,
                (int(rp.x), int(rp.y)),
                int(rp.radius),
                width=2,
            )

        for sw in shockwaves:
            pygame.draw.circle(
                arena_surface,
                sw.color,
                (int(sw.x), int(sw.y)),
                int(sw.radius),
                width=2,
            )

        for soul in souls:
            if soul.being_pulled:
                pygame.draw.line(
                    arena_surface,
                    (138, 86, 195),
                    (int(ghost.x), int(ghost.y)),
                    (int(soul.x), int(soul.y)),
                    2,
                )

        for soul in souls:
            soul.draw(arena_surface)
        for mg in mini_ghosts:
            mg.draw(arena_surface)
        ghost.draw(arena_surface, soul_nearby=soul_nearby)

        for p in particles:
            scale = max(0.0, p.life / p.max_life)
            pygame.draw.circle(
                arena_surface,
                p.color,
                (int(p.x), int(p.y)),
                max(1, int(p.radius * scale)),
            )

        for ft in floating_texts:
            txt_surf = font_popup.render(ft.text, True, ft.color)
            arena_surface.blit(txt_surf, (int(ft.x - txt_surf.get_width() / 2), int(ft.y)))

        # Cursor-only cooldown circle meter inside the playable woods
        if mouse_pos[0] < PLAY_WIDTH and not ghost.can_nudge:
            cd_rect = pygame.Rect(mouse_pos[0] - 13, mouse_pos[1] - 13, 26, 26)
            ready_frac = 1.0 - ghost.cooldown_progress
            pygame.draw.circle(arena_surface, (42, 22, 12), mouse_pos, 13, width=3)
            pygame.draw.arc(
                arena_surface,
                (255, 206, 86),
                cd_rect,
                math.pi / 2,
                math.pi / 2 + (math.tau * ready_frac),
                width=3,
            )

        shake_x = random.randint(-2, 2) if shake_timer > 0.0 else 0
        shake_y = random.randint(-2, 2) if shake_timer > 0.0 else 0
        screen.blit(arena_surface, (shake_x, shake_y))

        # Top-Left Wooden HUD Badge
        actual_speed = int(round(ghost.get_speed()))
        if ghost.is_boosted:
            speed_str = f"SPEED: {actual_speed}  [BOOST {ghost.boost_bounces_remaining}x]"
            speed_color = (255, 204, 82)
        elif ghost.is_gusting:
            speed_str = f"SPEED: {actual_speed}  [GUST]"
            speed_color = (125, 245, 212)
        else:
            speed_str = f"SPEED: {actual_speed}"
            speed_color = (255, 244, 224)

        souls_str = f"SOULS: {len(souls)}"

        hud_w = 275 if (ghost.is_boosted or ghost.is_gusting) else 195
        hud_h = 80 if combo_count >= 2 else 58
        hud_bg = pygame.Rect(12, 12, hud_w, hud_h)
        pygame.draw.rect(surface=screen, color=(62, 34, 18), rect=hud_bg, border_radius=8)
        pygame.draw.rect(surface=screen, color=(196, 122, 46), rect=hud_bg, width=2, border_radius=8)

        screen.blit(font_hud.render(speed_str, True, speed_color), (22, 19))
        screen.blit(font_hud.render(souls_str, True, (125, 245, 212)), (22, 43))

        if combo_count >= 2:
            streak_label = (
                f"STREAK: {combo_count}x MAX"
                if combo_count >= MAX_COMBO
                else f"STREAK: {combo_count}x"
            )
            combo_txt = font_combo.render(streak_label, True, (255, 218, 95))
            screen.blit(combo_txt, (22, 66))
            bar_x = 22 + combo_txt.get_width() + 8
            bar_w = max(24, (12 + hud_w - 10) - bar_x)
            fill_w = int(bar_w * (combo_timer / COMBO_WINDOW))
            pygame.draw.rect(screen, (38, 20, 12), pygame.Rect(bar_x, 70, bar_w, 7), border_radius=4)
            if fill_w > 0:
                pygame.draw.rect(
                    screen,
                    (255, 204, 78),
                    pygame.Rect(bar_x, 70, fill_w, 7),
                    border_radius=4,
                )

        if not has_nudged_once:
            hint_surf = font_hint.render(
                "Click anywhere in the woods to guide the Ghost!",
                True,
                (255, 224, 178),
            )
            screen.blit(
                hint_surf,
                (PLAY_WIDTH // 2 - hint_surf.get_width() // 2, PLAY_HEIGHT - 38),
            )

        # Right-hand Autumn Tree Upgrade Panel
        upgrade_manager.draw(screen, mouse_pos, ghost, mini_ghosts)

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())