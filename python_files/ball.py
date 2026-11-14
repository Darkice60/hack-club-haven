import math
import random
from collections import deque
from typing import Deque, Tuple
import pygame


class Ball:
    """Base physics entity for all circular characters in the playable woods."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        size: float,
        color: Tuple[int, int, int],
        arena_width: int,
        arena_height: int,
    ) -> None:
        self.x: float = float(x)
        self.y: float = float(y)
        self.vx: float = float(vx)
        self.vy: float = float(vy)
        self.size: float = float(size)
        self.color: Tuple[int, int, int] = color
        self.arena_width: int = arena_width
        self.arena_height: int = arena_height

    def get_speed(self) -> float:
        """Return the scalar magnitude of the current velocity vector."""
        return math.hypot(self.vx, self.vy)

    def set_speed(self, new_speed: float) -> None:
        """
        Change the magnitude of velocity while preserving its current direction.
        Safely picks a random direction if current velocity is zero.
        """
        new_speed = max(0.0, float(new_speed))
        current_speed = self.get_speed()

        if current_speed > 1e-6:
            scale = new_speed / current_speed
            self.vx *= scale
            self.vy *= scale
        else:
            angle = random.uniform(0.0, math.tau)
            self.vx = math.cos(angle) * new_speed
            self.vy = math.sin(angle) * new_speed

    def change_dir(self, dx: float, dy: float) -> None:
        """
        Update velocity direction toward vector (dx, dy) while preserving
        the current speed magnitude.
        """
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return

        speed = self.get_speed()
        nx = dx / length
        ny = dy / length
        self.vx = nx * speed
        self.vy = ny * speed

    def set_size(self, new_size: float) -> None:
        """Update radius and immediately clamp position so the entity stays inside walls."""
        self.size = float(new_size)
        self.clamp_to_bounds()

    def clamp_to_bounds(self) -> None:
        """Prevent the entity from escaping or getting stuck outside the arena walls."""
        min_x = self.size
        max_x = max(self.size, self.arena_width - self.size)
        min_y = self.size
        max_y = max(self.size, self.arena_height - self.size)

        if self.x < min_x:
            self.x = min_x
        elif self.x > max_x:
            self.x = max_x

        if self.y < min_y:
            self.y = min_y
        elif self.y > max_y:
            self.y = max_y

    def update(self, dt: float) -> bool:
        """
        Move using delta time and bounce off the four arena walls.
        Returns True if at least one wall collision occurred during this step.
        """
        self.x += self.vx * dt
        self.y += self.vy * dt

        bounced = False

        # Left and right wall collisions
        if self.x - self.size <= 0.0:
            self.x = self.size
            self.vx = abs(self.vx)
            bounced = True
        elif self.x + self.size >= self.arena_width:
            self.x = self.arena_width - self.size
            self.vx = -abs(self.vx)
            bounced = True

        # Top and bottom wall collisions
        if self.y - self.size <= 0.0:
            self.y = self.size
            self.vy = abs(self.vy)
            bounced = True
        elif self.y + self.size >= self.arena_height:
            self.y = self.arena_height - self.size
            self.vy = -abs(self.vy)
            bounced = True

        return bounced

    def collides_with(self, other: "Ball") -> bool:
        """Return True if this entity overlaps with another entity."""
        dist = math.hypot(self.x - other.x, self.y - other.y)
        return dist <= (self.size + other.size)


class Ghost(Ball):
    """The player's Ghost character with wall boosts, Wind Gust dash, and Rebirth Black Hole."""

    BOOST_DURATION_BOUNCES: int = 4
    BOOST_SPEED_BONUS: float = 165.0
    CLICK_COOLDOWN: float = 0.20  # Snappy 0.2s cooldown between clicks

    def __init__(
        self,
        x: float,
        y: float,
        speed: float,
        size: float,
        arena_width: int,
        arena_height: int,
    ) -> None:
        angle = random.uniform(0.0, math.tau)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        super().__init__(
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            size=size,
            color=(236, 224, 210),
            arena_width=arena_width,
            arena_height=arena_height,
        )

        self.base_speed: float = float(speed)
        self.boost_chance: float = 0.0
        self.boost_bounces_remaining: int = 0
        self.just_triggered_boost: bool = False

        # Click steering cooldown
        self.click_cooldown_timer: float = 0.0

        # Wind Gust ability (short burst dash strictly shorter than 0.20s click cooldown)
        self.wind_gust_level: int = 0
        self.wind_gust_power: float = 0.0
        self.wind_gust_timer: float = 0.0
        self.wind_gust_duration: float = 0.15

        # Black Hole suction reach beyond the Ghost's own radius (unlocked via Rebirth)
        self.black_hole_level: int = 0
        self.black_hole_reach: float = 0.0
        self.black_hole_strength: float = 0.0
        self.vortex_angle: float = 0.0

        # Facing direction, hover bob, and juicy eat-chomp animation timer
        self.facing: int = 1 if vx >= 0 else -1
        self.bob_phase: float = 0.0
        self.chomp_timer: float = 0.0

        # Recent positions for a spectral motion trail: (x, y, is_boosted)
        self.trail: Deque[Tuple[float, float, bool]] = deque(maxlen=15)

    @property
    def can_nudge(self) -> bool:
        """Return True when the click cooldown has finished."""
        return self.click_cooldown_timer <= 0.0

    @property
    def cooldown_progress(self) -> float:
        """Return remaining cooldown fraction from 1.0 (just clicked) to 0.0 (ready)."""
        if self.CLICK_COOLDOWN <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self.click_cooldown_timer / self.CLICK_COOLDOWN))

    @property
    def is_boosted(self) -> bool:
        return self.boost_bounces_remaining > 0

    @property
    def is_gusting(self) -> bool:
        return self.wind_gust_timer > 0.0 and self.wind_gust_power > 0.0

    @property
    def black_hole_radius(self) -> float:
        """Total outer radius of the Black Hole vortex around the Ghost."""
        if self.black_hole_level <= 0:
            return 0.0
        return self.size + self.black_hole_reach

    def trigger_chomp(self) -> None:
        """Start a brief squash-and-stretch chomp animation when eating a Soul."""
        self.chomp_timer = 0.20

    def _sync_effective_speed(self) -> None:
        """Compute effective speed from permanent base speed + active temporary bonuses."""
        target_speed = self.base_speed
        if self.is_boosted:
            target_speed += self.BOOST_SPEED_BONUS
        if self.is_gusting:
            gust_ratio = self.wind_gust_timer / max(0.01, self.wind_gust_duration)
            target_speed += self.wind_gust_power * gust_ratio
        self.set_speed(target_speed)

    def _recalculate_black_hole(self) -> None:
        """Update Black Hole reach and pull strength from current black_hole_level."""
        lvl = self.black_hole_level
        if lvl <= 0:
            self.black_hole_reach = 0.0
            self.black_hole_strength = 0.0
        else:
            self.black_hole_reach = 14.0 + (4.0 * lvl) + (0.95 * (lvl ** 2))
            self.black_hole_strength = 48.0 + (18.0 * lvl) + (2.5 * (lvl ** 2))

    def reset_for_rebirth(self, speed: float, size: float, rebirth_count: int) -> None:
        """
        Reset run-specific Ghost stats on Rebirth while granting the Black Hole
        at a starting level equal to the player's Rebirth count.
        """
        self.base_speed = float(speed)
        self.set_size(size)
        self.boost_chance = 0.0
        self.boost_bounces_remaining = 0
        self.just_triggered_boost = False
        self.click_cooldown_timer = 0.0

        self.wind_gust_level = 0
        self.wind_gust_power = 0.0
        self.wind_gust_timer = 0.0
        self.wind_gust_duration = 0.15

        self.black_hole_level = max(1, int(rebirth_count))
        self._recalculate_black_hole()

        self.trail.clear()
        self._sync_effective_speed()

    def apply_speed_upgrade(self, amount: float) -> None:
        """Permanently increase Ghost base speed without altering direction."""
        self.base_speed += float(amount)
        self._sync_effective_speed()

    def apply_size_upgrade(self, amount: float) -> None:
        """Permanently increase Ghost radius and keep inside arena walls."""
        self.set_size(self.size + float(amount))

    def apply_boost_chance_upgrade(self, amount: float) -> None:
        """Increase wall-bounce speed boost probability (capped at 100%)."""
        self.boost_chance = min(100.0, self.boost_chance + float(amount))

    def apply_wind_gust_upgrade(self, power_step: float) -> None:
        """Unlock or strengthen the click-triggered Wind Gust speed dash."""
        self.wind_gust_level += 1
        if self.wind_gust_level == 1:
            self.wind_gust_power = 110.0
        else:
            self.wind_gust_power += float(power_step)
            self.wind_gust_duration = min(0.18, self.wind_gust_duration + 0.005)

    def apply_black_hole_upgrade(self) -> None:
        """Increase the Black Hole vortex reach and pull strength."""
        self.black_hole_level += 1
        self._recalculate_black_hole()

    def nudge_toward(self, target_x: float, target_y: float) -> Tuple[bool, bool]:
        """
        Attempt to steer the Ghost toward a clicked point.
        Returns (accepted, gust_triggered). Ignored while on click cooldown.
        """
        if not self.can_nudge:
            return False, False

        self.click_cooldown_timer = self.CLICK_COOLDOWN
        self.change_dir(target_x - self.x, target_y - self.y)
        if abs(self.vx) > 1e-3:
            self.facing = 1 if self.vx >= 0 else -1

        if self.wind_gust_level > 0:
            self.wind_gust_timer = self.wind_gust_duration
            self._sync_effective_speed()
            return True, True
        return True, False

    def update(self, dt: float) -> bool:
        """Advance physics, animations, click cooldown, Wind Gust decay, and boost rolls."""
        self.just_triggered_boost = False
        self.bob_phase = (self.bob_phase + dt * 5.5) % math.tau
        self.vortex_angle = (self.vortex_angle + dt * 3.2) % math.tau

        if self.click_cooldown_timer > 0.0:
            self.click_cooldown_timer = max(0.0, self.click_cooldown_timer - dt)

        if self.chomp_timer > 0.0:
            self.chomp_timer = max(0.0, self.chomp_timer - dt)

        if self.wind_gust_timer > 0.0:
            self.wind_gust_timer = max(0.0, self.wind_gust_timer - dt)
            self._sync_effective_speed()

        self.trail.append((self.x, self.y, self.is_boosted or self.is_gusting))

        bounced = super().update(dt)

        if abs(self.vx) > 1e-3:
            self.facing = 1 if self.vx >= 0 else -1

        if bounced:
            if self.boost_bounces_remaining > 0:
                self.boost_bounces_remaining -= 1
                if self.boost_bounces_remaining == 0:
                    self._sync_effective_speed()

            if self.boost_chance > 0.0 and random.uniform(0.0, 100.0) < self.boost_chance:
                self.boost_bounces_remaining = self.BOOST_DURATION_BOUNCES
                self.just_triggered_boost = True
                self._sync_effective_speed()

        return bounced

    def draw(self, surface: pygame.Surface, soul_nearby: bool = False) -> None:
        """Render the Black Hole vortex, spectral trail, and Boo-style Ghost."""
        cx = int(self.x)
        cy = int(self.y + math.sin(self.bob_phase) * 2.0)

        chomp_scale = 1.0
        if self.chomp_timer > 0.0:
            chomp_scale = 1.0 + 0.14 * math.sin((self.chomp_timer / 0.20) * math.pi)

        r = max(10, int(self.size * chomp_scale))
        f = self.facing  # 1 when facing right, -1 when facing left

        # 1. Black Hole gravitational vortex field (drawn behind the Ghost)
        bh_r = int(self.black_hole_radius)
        if bh_r > 0:
            pygame.draw.circle(surface, (62, 32, 92), (cx, cy), bh_r, width=2)
            if bh_r > r + 16:
                mid_r = int((r + bh_r) * 0.52)
                pygame.draw.circle(surface, (94, 50, 136), (cx, cy), mid_r, width=1)

            orbit_dots = min(16, 4 + self.black_hole_level // 2)
            for i in range(orbit_dots):
                ang = self.vortex_angle + i * (math.tau / orbit_dots)
                ring_dist = r + (bh_r - r) * (0.40 + 0.55 * (i % 2))
                ox = int(cx + math.cos(ang) * ring_dist)
                oy = int(cy + math.sin(ang) * ring_dist)
                pygame.draw.circle(surface, (198, 140, 255), (ox, oy), 2)

        # 2. Ghostly motion trail
        trail_len = len(self.trail)
        for idx, (tx, ty, was_boosted) in enumerate(self.trail):
            progress = (idx + 1) / max(1, trail_len)
            trail_radius = max(2, int(r * progress * 0.72))
            if was_boosted:
                trail_color = (
                    int(75 + 175 * progress),
                    int(45 + 115 * progress),
                    int(20 + 35 * progress),
                )
            else:
                trail_color = (
                    int(52 + 75 * progress),
                    int(38 + 68 * progress),
                    int(34 + 66 * progress),
                )
            pygame.draw.circle(surface, trail_color, (int(tx), int(ty)), trail_radius)

        # 3. Spectral aura ring
        if self.is_boosted:
            aura_color = (235, 130, 35)
            body_shadow = (212, 176, 132)
            body_color = (255, 236, 198)
            highlight_color = (255, 252, 240)
        elif self.is_gusting:
            aura_color = (110, 215, 185)
            body_shadow = (196, 192, 182)
            body_color = (242, 244, 238)
            highlight_color = (255, 255, 255)
        else:
            aura_color = (74, 58, 52)
            body_shadow = (192, 178, 164)
            body_color = (236, 225, 212)
            highlight_color = (252, 248, 242)

        pygame.draw.circle(surface, aura_color, (cx, cy), r + 4)

        # 4. Pointed Ghost tail on the trailing side
        tail_points = [
            (cx - f * int(r * 0.72), cy - int(r * 0.18)),
            (cx - f * int(r * 1.24), cy + int(r * 0.04)),
            (cx - f * int(r * 0.65), cy + int(r * 0.45)),
        ]
        pygame.draw.polygon(surface, body_shadow, tail_points)

        # 5. Stubby back arm
        back_arm_pos = (cx - f * int(r * 0.78), cy + int(r * 0.08))
        pygame.draw.circle(surface, body_shadow, back_arm_pos, max(3, int(r * 0.25)))

        # 6. Main round Ghost body + shading + top highlight
        pygame.draw.circle(surface, body_shadow, (cx, cy), r)
        pygame.draw.circle(
            surface,
            body_color,
            (cx + f * max(1, r // 12), cy - max(1, r // 12)),
            max(5, int(r * 0.93)),
        )
        pygame.draw.circle(
            surface,
            highlight_color,
            (cx - f * int(r * 0.28), cy - int(r * 0.36)),
            max(2, int(r * 0.26)),
        )

        # 7. Stubby front arm
        front_arm_pos = (cx + f * int(r * 0.86), cy + int(r * 0.06))
        pygame.draw.circle(surface, body_color, front_arm_pos, max(3, int(r * 0.24)))

        # 8. Two vertical dark oval eyes
        eye_color = (24, 16, 14)
        eye_w = max(2, int(r * 0.18))
        eye_h = max(5, int(r * 0.38))
        eye_y = cy - int(r * 0.34)

        front_eye_x = cx + f * int(r * 0.44) - eye_w // 2
        back_eye_x = cx + f * int(r * 0.14) - eye_w // 2
        pygame.draw.ellipse(surface, eye_color, pygame.Rect(back_eye_x, eye_y, eye_w, eye_h))
        pygame.draw.ellipse(surface, eye_color, pygame.Rect(front_eye_x, eye_y, eye_w, eye_h))

        # 9. Round open 'O' mouth
        mouth_scale = 0.29 if (soul_nearby or self.is_boosted or self.chomp_timer > 0.0) else 0.20
        mouth_w = max(3, int(r * mouth_scale * 1.4))
        mouth_h = max(4, int(r * mouth_scale * 1.7))
        mouth_x = cx + f * int(r * 0.30) - mouth_w // 2
        mouth_y = cy + int(r * 0.14)
        pygame.draw.ellipse(surface, eye_color, pygame.Rect(mouth_x, mouth_y, mouth_w, mouth_h))

        # 10. Boost pips around perimeter showing remaining boosted bounces
        if self.is_boosted:
            pip_orbit = r + 11
            for i in range(self.boost_bounces_remaining):
                angle = -math.pi / 2 + i * (math.tau / self.BOOST_DURATION_BOUNCES)
                px = int(cx + math.cos(angle) * pip_orbit)
                py = int(cy + math.sin(angle) * pip_orbit)
                pygame.draw.circle(surface, (255, 195, 75), (px, py), 3)


class MiniGhost(Ball):
    """Autonomous baby Ghost companion unlocked via upgrades that hunts Souls for you."""

    def __init__(
        self,
        x: float,
        y: float,
        speed: float,
        arena_width: int,
        arena_height: int,
    ) -> None:
        angle = random.uniform(0.0, math.tau)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        super().__init__(
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            size=11.0,
            color=(218, 224, 240),
            arena_width=arena_width,
            arena_height=arena_height,
        )
        self.facing: int = 1 if vx >= 0 else -1
        self.bob_phase: float = random.uniform(0.0, math.tau)

    def update(self, dt: float) -> bool:
        self.bob_phase = (self.bob_phase + dt * 7.0) % math.tau
        bounced = super().update(dt)
        if abs(self.vx) > 1e-3:
            self.facing = 1 if self.vx >= 0 else -1
        return bounced

    def draw(self, surface: pygame.Surface) -> None:
        cx = int(self.x)
        cy = int(self.y + math.sin(self.bob_phase) * 1.6)
        r = int(self.size)
        f = self.facing

        pygame.draw.circle(surface, (58, 62, 84), (cx, cy), r + 3)
        tail_pts = [
            (cx - f * int(r * 0.7), cy - int(r * 0.15)),
            (cx - f * int(r * 1.2), cy + int(r * 0.05)),
            (cx - f * int(r * 0.6), cy + int(r * 0.42)),
        ]
        pygame.draw.polygon(surface, (176, 184, 206), tail_pts)

        pygame.draw.circle(surface, (218, 226, 244), (cx, cy), r)
        pygame.draw.circle(surface, (246, 250, 255), (cx - f * 3, cy - 4), 3)

        eye_col = (24, 18, 22)
        pygame.draw.ellipse(surface, eye_col, pygame.Rect(cx + f * 1 - 1, cy - 4, 2, 4))
        pygame.draw.ellipse(surface, eye_col, pygame.Rect(cx + f * 4 - 1, cy - 4, 2, 4))


class Soul(Ball):
    """
    Glowing Soul wisp eaten by the Ghost.
    Variations:
      - 'normal': Cyan wisp (1x base points)
      - 'golden': Radiant gold wisp (5x base points)
      - 'devil':  Crimson horned spirit (15x base points)
    """

    VARIANT_MULTIPLIERS = {
        "normal": 1,
        "golden": 5,
        "devil": 15,
    }

    def __init__(
        self,
        x: float,
        y: float,
        speed: float,
        size: float,
        base_point_value: int,
        arena_width: int,
        arena_height: int,
        soul_type: str = "normal",
    ) -> None:
        self.soul_type: str = soul_type if soul_type in self.VARIANT_MULTIPLIERS else "normal"
        self.base_point_value: int = int(base_point_value)

        if self.soul_type == "devil":
            actual_size = size + 2.5
            actual_speed = speed * 1.25
            color = (255, 58, 88)
        elif self.soul_type == "golden":
            actual_size = size + 1.5
            actual_speed = speed * 1.12
            color = (255, 212, 64)
        else:
            actual_size = size
            actual_speed = speed
            color = (105, 240, 210)

        angle = random.uniform(0.0, math.tau)
        vx = math.cos(angle) * actual_speed
        vy = math.sin(angle) * actual_speed
        super().__init__(
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            size=actual_size,
            color=color,
            arena_width=arena_width,
            arena_height=arena_height,
        )
        self.base_speed: float = float(actual_speed)
        self.pulse_phase: float = random.uniform(0.0, math.tau)
        self.being_pulled: bool = False

    @property
    def point_value(self) -> int:
        """Total points awarded when collected, scaling with Soul Value upgrades."""
        return self.base_point_value * self.VARIANT_MULTIPLIERS[self.soul_type]

    def set_base_point_value(self, new_base_value: int) -> None:
        self.base_point_value = int(new_base_value)

    def pull_toward(
        self,
        target_x: float,
        target_y: float,
        pull_radius: float,
        pull_strength: float,
        dt: float,
    ) -> bool:
        """
        Pull the Soul toward the Ghost whenever it enters the Black Hole radius.
        Suction scales smoothly with both proximity and Black Hole level.
        """
        self.being_pulled = False
        if pull_radius <= 0.0 or pull_strength <= 0.0:
            return False

        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.hypot(dx, dy)

        if 1e-6 < dist <= pull_radius:
            nx = dx / dist
            ny = dy / dist
            proximity = 1.0 - (dist / pull_radius)
            suction = pull_strength * (0.30 + 0.95 * proximity)

            self.x += nx * suction * dt
            self.y += ny * suction * dt

            self.vx += nx * suction * 1.1 * dt
            self.vy += ny * suction * 1.1 * dt
            max_swirl_speed = self.base_speed * 1.90
            if self.get_speed() > max_swirl_speed:
                self.set_speed(max_swirl_speed)

            self.clamp_to_bounds()
            self.being_pulled = True
            return True

        current_speed = self.get_speed()
        if current_speed > self.base_speed + 1.0:
            self.set_speed(max(self.base_speed, current_speed - 85.0 * dt))

        return False

    def update(self, dt: float) -> bool:
        """Advance movement and spectral flicker phase."""
        self.pulse_phase = (self.pulse_phase + dt * 6.0) % math.tau
        return super().update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Render Normal, Golden, or Horned Devil Soul wisps."""
        cx, cy = int(self.x), int(self.y)
        r = max(4, int(self.size))
        pulse = 1 if math.sin(self.pulse_phase) > 0 else 0

        spd = self.get_speed()
        if spd > 1e-4:
            tx_dir = -self.vx / spd
            ty_dir = -self.vy / spd
        else:
            tx_dir, ty_dir = 0.0, 1.0

        perp_x, perp_y = -ty_dir, tx_dir
        tail_len = r * 2.2 + math.sin(self.pulse_phase) * 1.6
        tail_tip = (
            int(self.x + tx_dir * tail_len),
            int(self.y + ty_dir * tail_len),
        )
        side_a = (
            int(self.x + perp_x * (r * 0.72)),
            int(self.y + perp_y * (r * 0.72)),
        )
        side_b = (
            int(self.x - perp_x * (r * 0.72)),
            int(self.y - perp_y * (r * 0.72)),
        )

        if self.soul_type == "devil":
            outer_aura = (118, 22, 42)
            mid_color = (255, 58, 88)
            core_color = (255, 215, 190)
        elif self.soul_type == "golden":
            outer_aura = (115, 84, 20)
            mid_color = (255, 212, 64)
            core_color = (255, 252, 224)
        else:
            outer_aura = (92, 68, 155) if self.being_pulled else (32, 78, 72)
            mid_color = (165, 220, 255) if self.being_pulled else self.color
            core_color = (238, 255, 248)

        pygame.draw.circle(surface, outer_aura, (cx, cy), r + 4 + pulse)
        pygame.draw.polygon(surface, mid_color, [side_a, side_b, tail_tip])
        pygame.draw.circle(surface, mid_color, (cx, cy), r)

        if self.soul_type == "devil":
            horn_col = (255, 145, 95)
            left_horn = [(cx - r + 1, cy - 2), (cx - r - 4, cy - r - 3), (cx - 2, cy - r + 2)]
            right_horn = [(cx + r - 1, cy - 2), (cx + r + 4, cy - r - 3), (cx + 2, cy - r + 2)]
            pygame.draw.polygon(surface, horn_col, left_horn)
            pygame.draw.polygon(surface, horn_col, right_horn)

        core_r = max(2, int(r * 0.52))
        pygame.draw.circle(surface, core_color, (cx, cy), core_r)