import asyncio
import math
import random
from dataclasses import dataclass
from typing import List, Tuple
import pygame

from ball import MotherBall, PointBall
from upgrades import UpgradeManager

# Window and layout dimensions
WINDOW_WIDTH: int = 800
WINDOW_HEIGHT: int = 600
PANEL_WIDTH: int = 200
PLAY_WIDTH: int = WINDOW_WIDTH - PANEL_WIDTH  # 600 px
PLAY_HEIGHT: int = WINDOW_HEIGHT              # 600 px
TARGET_FPS: int = 60


@dataclass
class Particle:
    """Small arcade spark emitted on Point Ball collection or wall boost."""

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: Tuple[int, int, int]
    life: float
    max_life: float


@dataclass
class FloatingText:
    """Rising '+X' score popup when collecting a Point Ball."""

    x: float
    y: float
    text: str
    color: Tuple[int, int, int]
    life: float = 0.75


@dataclass
class ClickRipple:
    """Expanding ring showing where the player clicked to steer the Mother Ball."""

    x: float
    y: float
    radius: float = 4.0
    max_radius: float = 34.0
    life: float = 0.35


def spawn_point_ball(
    arena_width: int,
    arena_height: int,
    mother_ball: MotherBall,
    existing_balls: List[PointBall],
    speed: float,
    size: float,
    point_value: int,
) -> PointBall:
    """
    Spawn a Point Ball inside the arena while avoiding overlapping the Mother Ball
    or existing Point Balls.
    """
    margin = size + 6.0
    min_x = margin
    max_x = max(margin, arena_width - margin)
    min_y = margin
    max_y = max(margin, arena_height - margin)

    best_x = random.uniform(min_x, max_x)
    best_y = random.uniform(min_y, max_y)
    best_clearance = -1.0

    # Sample candidate coordinates and pick the first valid non-overlapping spot
    for _ in range(60):
        cx = random.uniform(min_x, max_x)
        cy = random.uniform(min_y, max_y)

        mother_dist = math.hypot(cx - mother_ball.x, cy - mother_ball.y)
        mother_clearance = mother_dist - (mother_ball.size + size + 24.0)

        if mother_clearance < 0.0:
            if mother_clearance > best_clearance:
                best_clearance = mother_clearance
                best_x, best_y = cx, cy
            continue

        overlaps_other = False
        for other in existing_balls:
            if math.hypot(cx - other.x, cy - other.y) < (other.size + size + 8.0):
                overlaps_other = True
                break

        if not overlaps_other:
            best_x, best_y = cx, cy
            break

        if mother_clearance > best_clearance:
            best_clearance = mother_clearance
            best_x, best_y = cx, cy

    return PointBall(
        x=best_x,
        y=best_y,
        speed=speed,
        size=size,
        point_value=point_value,
        arena_width=arena_width,
        arena_height=arena_height,
    )


def spawn_burst(
    particles: List[Particle],
    x: float,
    y: float,
    color: Tuple[int, int, int],
    count: int = 10,
    speed_range: Tuple[float, float] = (45.0, 155.0),
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
                radius=random.uniform(2.0, 4.0),
                color=color,
                life=life,
                max_life=life,
            )
        )


def draw_arena_background(surface: pygame.Surface) -> None:
    """Draw the dark navy playable background and subtle arcade grid."""
    arena_rect = pygame.Rect(0, 0, PLAY_WIDTH, PLAY_HEIGHT)
    pygame.draw.rect(surface, (11, 15, 25), arena_rect)

    grid_color = (19, 26, 43)
    step = 50
    for gx in range(step, PLAY_WIDTH, step):
        pygame.draw.line(surface, grid_color, (gx, 0), (gx, PLAY_HEIGHT), 1)
    for gy in range(step, PLAY_HEIGHT, step):
        pygame.draw.line(surface, grid_color, (0, gy), (PLAY_WIDTH, gy), 1)


async def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("BOUNCE BACK")
    clock = pygame.time.Clock()

    font_hud = pygame.font.Font(None, 22)
    font_hint = pygame.font.Font(None, 20)
    font_popup = pygame.font.Font(None, 22)

    # Core game entities
    mother_ball = MotherBall(
        x=PLAY_WIDTH / 2.0,
        y=PLAY_HEIGHT / 2.0,
        speed=85.0,
        size=12.0,
        arena_width=PLAY_WIDTH,
        arena_height=PLAY_HEIGHT,
    )

    upgrade_manager = UpgradeManager(
        panel_x=PLAY_WIDTH,
        panel_width=PANEL_WIDTH,
        panel_height=WINDOW_HEIGHT,
    )

    point_balls: List[PointBall] = []
    while len(point_balls) < upgrade_manager.pb_target_count:
        point_balls.append(
            spawn_point_ball(
                PLAY_WIDTH,
                PLAY_HEIGHT,
                mother_ball,
                point_balls,
                upgrade_manager.pb_speed,
                upgrade_manager.pb_size,
                upgrade_manager.pb_points,
            )
        )

    # Visual feedback lists
    particles: List[Particle] = []
    floating_texts: List[FloatingText] = []
    ripples: List[ClickRipple] = []
    has_nudged_once = False

    running = True
    while running:
        # Clamp delta time to prevent physics tunneling on browser tab switches or lag spikes
        dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)
        mouse_pos = pygame.mouse.get_pos()

        # 1. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx < PLAY_WIDTH:
                    # Click inside playable area: steer Mother Ball without affecting upgrades
                    mother_ball.nudge_toward(mx, my)
                    ripples.append(ClickRipple(x=float(mx), y=float(my)))
                    has_nudged_once = True
                else:
                    # Click inside right-hand side panel: check upgrade buttons
                    purchased = upgrade_manager.handle_click((mx, my), mother_ball, point_balls)
                    if purchased == "pb_count":
                        while len(point_balls) < upgrade_manager.pb_target_count:
                            point_balls.append(
                                spawn_point_ball(
                                    PLAY_WIDTH,
                                    PLAY_HEIGHT,
                                    mother_ball,
                                    point_balls,
                                    upgrade_manager.pb_speed,
                                    upgrade_manager.pb_size,
                                    upgrade_manager.pb_points,
                                )
                            )

        # 2. Physics & State Updates
        mother_ball.update(dt)
        if mother_ball.just_triggered_boost:
            spawn_burst(
                particles,
                mother_ball.x,
                mother_ball.y,
                color=(255, 225, 95),
                count=14,
                speed_range=(60.0, 180.0),
            )

        for pb in point_balls:
            pb.update(dt)

        # Check collisions between Mother Ball and Point Balls
        for idx, pb in enumerate(point_balls):
            if mother_ball.collides_with(pb):
                earned = pb.point_value
                upgrade_manager.add_points(earned)

                spawn_burst(particles, pb.x, pb.y, color=(255, 95, 115), count=9)
                floating_texts.append(
                    FloatingText(
                        x=pb.x,
                        y=pb.y - pb.size,
                        text=f"+{earned}",
                        color=(255, 235, 130),
                    )
                )

                # Spawn a replacement Point Ball inheriting all purchased upgrades
                others = [b for i, b in enumerate(point_balls) if i != idx]
                point_balls[idx] = spawn_point_ball(
                    PLAY_WIDTH,
                    PLAY_HEIGHT,
                    mother_ball,
                    others,
                    upgrade_manager.pb_speed,
                    upgrade_manager.pb_size,
                    upgrade_manager.pb_points,
                )

        # Update visual effects & UI timers
        upgrade_manager.update(dt)

        for p in particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
        particles = [p for p in particles if p.life > 0.0]

        for ft in floating_texts:
            ft.y -= 34.0 * dt
            ft.life -= dt
        floating_texts = [ft for ft in floating_texts if ft.life > 0.0]

        for rp in ripples:
            rp.life -= dt
            progress = 1.0 - max(0.0, rp.life / 0.35)
            rp.radius = 4.0 + (rp.max_radius - 4.0) * progress
        ripples = [rp for rp in ripples if rp.life > 0.0]

        # 3. Rendering
        draw_arena_background(screen)

        # Click ripples
        for rp in ripples:
            pygame.draw.circle(
                screen,
                (70, 195, 245),
                (int(rp.x), int(rp.y)),
                int(rp.radius),
                width=2,
            )

        # Point Balls & Mother Ball
        for pb in point_balls:
            pb.draw(screen)
        mother_ball.draw(screen)

        # Particles & Floating Score Text
        for p in particles:
            scale = max(0.0, p.life / p.max_life)
            pygame.draw.circle(
                screen,
                p.color,
                (int(p.x), int(p.y)),
                max(1, int(p.radius * scale)),
            )

        for ft in floating_texts:
            txt_surf = font_popup.render(ft.text, True, ft.color)
            screen.blit(txt_surf, (int(ft.x - txt_surf.get_width() / 2), int(ft.y)))

        # Minimalist Top-Left Arena HUD
        actual_speed = int(round(mother_ball.get_speed()))
        if mother_ball.is_boosted:
            speed_str = f"SPEED: {actual_speed} px/s  [BOOST {mother_ball.boost_bounces_remaining}x]"
            speed_color = (255, 228, 105)
        else:
            speed_str = f"SPEED: {actual_speed} px/s"
            speed_color = (120, 225, 255)

        balls_str = f"POINT BALLS: {len(point_balls)}"

        hud_bg = pygame.Rect(10, 10, 265 if mother_ball.is_boosted else 175, 48)
        pygame.draw.rect(screen, (16, 23, 38), hud_bg, border_radius=6)
        pygame.draw.rect(screen, (38, 56, 86), hud_bg, width=1, border_radius=6)

        screen.blit(font_hud.render(speed_str, True, speed_color), (18, 16))
        screen.blit(font_hud.render(balls_str, True, (245, 125, 140)), (18, 36))

        if not has_nudged_once:
            hint_surf = font_hint.render(
                "Click anywhere in the arena to steer the Mother Ball",
                True,
                (130, 155, 190),
            )
            screen.blit(
                hint_surf,
                (PLAY_WIDTH // 2 - hint_surf.get_width() // 2, PLAY_HEIGHT - 28),
            )

        # Right-hand Upgrade Side Panel
        upgrade_manager.draw(screen, mouse_pos, mother_ball)

        pygame.display.flip()

        # Yield control back to the browser event loop (required for Pygbag)
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())