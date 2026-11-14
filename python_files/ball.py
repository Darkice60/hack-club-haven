import math
import random
from collections import deque
from typing import Deque, Tuple
import pygame


class Ball:
    """Base physics entity for all circular balls in the playable arena."""

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
        Safely picks a random direction if the ball currently has zero velocity.
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
            # Ignore zero-length direction vectors (e.g., clicking dead center on the ball)
            return

        speed = self.get_speed()
        nx = dx / length
        ny = dy / length
        self.vx = nx * speed
        self.vy = ny * speed

    def set_size(self, new_size: float) -> None:
        """Update radius and immediately clamp position so the ball stays inside walls."""
        self.size = float(new_size)
        self.clamp_to_bounds()

    def clamp_to_bounds(self) -> None:
        """Prevent the ball from escaping or getting stuck outside the arena walls."""
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
        Move the ball using delta time and bounce off the four arena walls.
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
        """Return True if this ball overlaps with another ball."""
        dist = math.hypot(self.x - other.x, self.y - other.y)
        return dist <= (self.size + other.size)


class MotherBall(Ball):
    """The player's primary bouncing ball with upgrades, mouse nudging, and speed boosts."""

    BOOST_DURATION_BOUNCES: int = 4
    BOOST_SPEED_BONUS: float = 135.0

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
            color=(56, 214, 255),
            arena_width=arena_width,
            arena_height=arena_height,
        )

        self.base_speed: float = float(speed)
        self.boost_chance: float = 0.0  # Percentage from 0.0 to 100.0
        self.boost_bounces_remaining: int = 0
        self.just_triggered_boost: bool = False

        # Store recent positions for an arcade motion trail: (x, y, is_boosted)
        self.trail: Deque[Tuple[float, float, bool]] = deque(maxlen=16)

    @property
    def is_boosted(self) -> bool:
        return self.boost_bounces_remaining > 0

    def _sync_effective_speed(self) -> None:
        """Apply base speed plus any active temporary boost while preserving direction."""
        target_speed = self.base_speed
        if self.is_boosted:
            target_speed += self.BOOST_SPEED_BONUS
        self.set_speed(target_speed)

    def apply_speed_upgrade(self, amount: float) -> None:
        """Permanently increase base speed without altering movement direction."""
        self.base_speed += float(amount)
        self._sync_effective_speed()

    def apply_size_upgrade(self, amount: float) -> None:
        """Permanently increase radius and keep ball safely inside arena walls."""
        self.set_size(self.size + float(amount))

    def apply_boost_chance_upgrade(self, amount: float) -> None:
        """Increase wall-bounce speed boost probability (capped at 100%)."""
        self.boost_chance = min(100.0, self.boost_chance + float(amount))

    def nudge_toward(self, target_x: float, target_y: float) -> None:
        """Steer the Mother Ball toward a clicked point while keeping current speed."""
        self.change_dir(target_x - self.x, target_y - self.y)

    def update(self, dt: float) -> bool:
        """Advance physics, manage 4-bounce boost countdown, and roll for new boosts."""
        self.just_triggered_boost = False
        self.trail.append((self.x, self.y, self.is_boosted))

        bounced = super().update(dt)

        if bounced:
            # Count down any active temporary boost first
            if self.boost_bounces_remaining > 0:
                self.boost_bounces_remaining -= 1
                if self.boost_bounces_remaining == 0:
                    self._sync_effective_speed()

            # Roll for a new temporary speed boost (refreshes duration if already boosted)
            if self.boost_chance > 0.0 and random.uniform(0.0, 100.0) < self.boost_chance:
                self.boost_bounces_remaining = self.BOOST_DURATION_BOUNCES
                self.just_triggered_boost = True
                self._sync_effective_speed()

        return bounced

    def draw(self, surface: pygame.Surface) -> None:
        """Render the motion trail, layered neon glow, and core Mother Ball."""
        # 1. Motion trail
        trail_len = len(self.trail)
        for idx, (tx, ty, was_boosted) in enumerate(self.trail):
            progress = (idx + 1) / max(1, trail_len)
            trail_radius = max(2, int(self.size * progress * 0.78))
            if was_boosted:
                trail_color = (
                    int(40 + 180 * progress),
                    int(140 + 95 * progress),
                    int(90 + 40 * progress),
                )
            else:
                trail_color = (
                    int(16 + 24 * progress),
                    int(45 + 110 * progress),
                    int(85 + 130 * progress),
                )
            pygame.draw.circle(surface, trail_color, (int(tx), int(ty)), trail_radius)

        cx, cy = int(self.x), int(self.y)
        r = int(self.size)

        # 2. Outer glow rings (shifts to electric gold-cyan when speed-boosted)
        if self.is_boosted:
            outer_glow = (95, 85, 30)
            mid_glow = (195, 175, 55)
            core_color = (255, 232, 110)
            inner_color = (255, 252, 220)
        else:
            outer_glow = (18, 52, 88)
            mid_glow = (30, 115, 175)
            core_color = self.color
            inner_color = (205, 248, 255)

        pygame.draw.circle(surface, outer_glow, (cx, cy), r + 8)
        pygame.draw.circle(surface, mid_glow, (cx, cy), r + 4)

        # 3. Main body & specular highlight
        pygame.draw.circle(surface, core_color, (cx, cy), r)
        highlight_offset = max(2, r // 3)
        highlight_radius = max(2, r // 3)
        pygame.draw.circle(
            surface,
            inner_color,
            (cx - highlight_offset, cy - highlight_offset),
            highlight_radius,
        )

        # 4. Boost pips around perimeter showing remaining boosted bounces
        if self.is_boosted:
            pip_orbit = r + 12
            for i in range(self.boost_bounces_remaining):
                angle = -math.pi / 2 + i * (math.tau / self.BOOST_DURATION_BOUNCES)
                px = int(cx + math.cos(angle) * pip_orbit)
                py = int(cy + math.sin(angle) * pip_orbit)
                pygame.draw.circle(surface, (255, 235, 115), (px, py), 3)


class PointBall(Ball):
    """Collectible red target ball that awards currency when touched by the Mother Ball."""

    def __init__(
        self,
        x: float,
        y: float,
        speed: float,
        size: float,
        point_value: int,
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
            color=(248, 72, 92),
            arena_width=arena_width,
            arena_height=arena_height,
        )
        self.point_value: int = int(point_value)
        self.pulse_phase: float = random.uniform(0.0, math.tau)

    def update(self, dt: float) -> bool:
        """Advance movement and subtle visual pulse phase."""
        self.pulse_phase = (self.pulse_phase + dt * 4.5) % math.tau
        return super().update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Render the red Point Ball with a soft crimson glow."""
        cx, cy = int(self.x), int(self.y)
        r = int(self.size)
        pulse = 1 if math.sin(self.pulse_phase) > 0 else 0

        pygame.draw.circle(surface, (82, 22, 34), (cx, cy), r + 4 + pulse)
        pygame.draw.circle(surface, self.color, (cx, cy), r)

        if r >= 5:
            offset = max(1, r // 3)
            pygame.draw.circle(
                surface,
                (255, 175, 185),
                (cx - offset, cy - offset),
                max(1, r // 3),
            )