from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pygame
from ball import MotherBall, PointBall


@dataclass
class Upgrade:
    """Data container representing a single incremental upgrade."""

    key: str
    name: str
    description: str
    base_cost: int
    cost_multiplier: float
    effect_amount: float
    level: int = 0
    max_level: Optional[int] = None
    rect: Optional[pygame.Rect] = None
    purchase_flash: float = 0.0
    error_flash: float = 0.0

    def is_maxed(self) -> bool:
        return self.max_level is not None and self.level >= self.max_level

    def get_cost(self) -> int:
        """Calculate current integer cost using exponential scaling."""
        return int(round(self.base_cost * (self.cost_multiplier ** self.level)))


class UpgradeManager:
    """Manages player currency, upgrade state, purchases, and the right-hand UI panel."""

    def __init__(self, panel_x: int, panel_width: int, panel_height: int) -> None:
        self.panel_x: int = panel_x
        self.panel_width: int = panel_width
        self.panel_height: int = panel_height

        # Player currency
        self.points: int = 0

        # Active Point Ball template attributes (inherited by all newly spawned Point Balls)
        self.pb_speed: float = 48.0
        self.pb_size: float = 7.0
        self.pb_points: int = 1
        self.pb_target_count: int = 5

        # Ordered upgrade definitions
        self.upgrades: Dict[str, Upgrade] = {
            "mb_speed": Upgrade(
                key="mb_speed",
                name="MB Speed",
                description="+22 Mother Ball speed",
                base_cost=5,
                cost_multiplier=1.35,
                effect_amount=22.0,
            ),
            "mb_size": Upgrade(
                key="mb_size",
                name="MB Size",
                description="+3 Mother Ball radius",
                base_cost=8,
                cost_multiplier=1.42,
                effect_amount=3.0,
                max_level=38,
            ),
            "mb_speedboost": Upgrade(
                key="mb_speedboost",
                name="Wall Boost",
                description="+4% bounce boost (4x)",
                base_cost=12,
                cost_multiplier=1.45,
                effect_amount=4.0,
                max_level=25,
            ),
            "pb_speed": Upgrade(
                key="pb_speed",
                name="PB Speed",
                description="+14 Point Ball speed",
                base_cost=6,
                cost_multiplier=1.32,
                effect_amount=14.0,
            ),
            "pb_size": Upgrade(
                key="pb_size",
                name="PB Size",
                description="+2 Point Ball radius",
                base_cost=10,
                cost_multiplier=1.40,
                effect_amount=2.0,
                max_level=18,
            ),
            "pb_points": Upgrade(
                key="pb_points",
                name="PB Value",
                description="+1 point per collection",
                base_cost=10,
                cost_multiplier=1.48,
                effect_amount=1.0,
            ),
            "pb_count": Upgrade(
                key="pb_count",
                name="PB Count",
                description="+1 Point Ball on screen",
                base_cost=15,
                cost_multiplier=1.50,
                effect_amount=1.0,
                max_level=55,
            ),
        }

        self._build_layout()

        # Built-in Pygame fonts (100% compatible with Pygbag WebAssembly)
        self.font_wallet_label = pygame.font.Font(None, 18)
        self.font_wallet_value = pygame.font.Font(None, 36)
        self.font_wallet_sub = pygame.font.Font(None, 18)
        self.font_card_title = pygame.font.Font(None, 21)
        self.font_card_level = pygame.font.Font(None, 19)
        self.font_card_desc = pygame.font.Font(None, 18)
        self.font_card_cost = pygame.font.Font(None, 19)

    def _build_layout(self) -> None:
        """Compute clickable pygame.Rect cards inside the right-hand side panel."""
        margin_x = 8
        card_w = self.panel_width - (margin_x * 2)
        start_y = 90
        card_h = 66
        gap_y = 6

        for idx, upgrade in enumerate(self.upgrades.values()):
            y = start_y + idx * (card_h + gap_y)
            upgrade.rect = pygame.Rect(self.panel_x + margin_x, y, card_w, card_h)

    def add_points(self, amount: int) -> None:
        """Award points to the player."""
        self.points += max(0, int(amount))

    def can_afford(self, upgrade_key: str) -> bool:
        """Return True if the upgrade exists, is not maxed, and player has enough points."""
        upgrade = self.upgrades.get(upgrade_key)
        if upgrade is None or upgrade.is_maxed():
            return False
        return self.points >= upgrade.get_cost()

    def purchase(
        self,
        upgrade_key: str,
        mother_ball: MotherBall,
        point_balls: List[PointBall],
    ) -> bool:
        """
        Attempt to purchase an upgrade. Deducts currency, increments level,
        and applies the upgrade's mechanical effect.
        """
        upgrade = self.upgrades.get(upgrade_key)
        if upgrade is None or upgrade.is_maxed():
            return False

        cost = upgrade.get_cost()
        if self.points < cost:
            upgrade.error_flash = 0.25
            return False

        # Deduct points and level up
        self.points -= cost
        upgrade.level += 1
        upgrade.purchase_flash = 0.30

        # Apply upgrade effect
        if upgrade_key == "mb_speed":
            mother_ball.apply_speed_upgrade(upgrade.effect_amount)
        elif upgrade_key == "mb_size":
            mother_ball.apply_size_upgrade(upgrade.effect_amount)
        elif upgrade_key == "mb_speedboost":
            mother_ball.apply_boost_chance_upgrade(upgrade.effect_amount)
        elif upgrade_key == "pb_speed":
            self.pb_speed += upgrade.effect_amount
            for pb in point_balls:
                pb.set_speed(self.pb_speed)
        elif upgrade_key == "pb_size":
            self.pb_size += upgrade.effect_amount
            for pb in point_balls:
                pb.set_size(self.pb_size)
        elif upgrade_key == "pb_points":
            self.pb_points += int(upgrade.effect_amount)
            for pb in point_balls:
                pb.point_value = self.pb_points
        elif upgrade_key == "pb_count":
            self.pb_target_count += int(upgrade.effect_amount)

        return True

    def handle_click(
        self,
        mouse_pos: Tuple[int, int],
        mother_ball: MotherBall,
        point_balls: List[PointBall],
    ) -> Optional[str]:
        """Check if a click hit any upgrade card and attempt purchase."""
        for key, upgrade in self.upgrades.items():
            if upgrade.rect is not None and upgrade.rect.collidepoint(mouse_pos):
                if self.purchase(key, mother_ball, point_balls):
                    return key
                return None
        return None

    def update(self, dt: float) -> None:
        """Decay visual feedback timers on upgrade cards."""
        for upgrade in self.upgrades.values():
            if upgrade.purchase_flash > 0.0:
                upgrade.purchase_flash = max(0.0, upgrade.purchase_flash - dt)
            if upgrade.error_flash > 0.0:
                upgrade.error_flash = max(0.0, upgrade.error_flash - dt)

    def _get_live_stat_hint(self, key: str, mother_ball: MotherBall) -> str:
        """Return a concise secondary readout showing current upgraded stat."""
        if key == "mb_speed":
            return f"Base: {int(mother_ball.base_speed)} px/s"
        if key == "mb_size":
            return f"Radius: {int(mother_ball.size)} px"
        if key == "mb_speedboost":
            return f"Chance: {int(mother_ball.boost_chance)}%"
        if key == "pb_speed":
            return f"Speed: {int(self.pb_speed)} px/s"
        if key == "pb_size":
            return f"Radius: {int(self.pb_size)} px"
        if key == "pb_points":
            return f"Value: +{self.pb_points} pts"
        if key == "pb_count":
            return f"Active: {self.pb_target_count} balls"
        return ""

    def draw(
        self,
        surface: pygame.Surface,
        mouse_pos: Tuple[int, int],
        mother_ball: MotherBall,
    ) -> None:
        """Render the side panel background, point wallet, and all upgrade buttons."""
        panel_rect = pygame.Rect(self.panel_x, 0, self.panel_width, self.panel_height)
        pygame.draw.rect(surface, (15, 21, 36), panel_rect)
        pygame.draw.line(
            surface,
            (38, 54, 84),
            (self.panel_x, 0),
            (self.panel_x, self.panel_height),
            2,
        )

        # Top currency wallet card
        wallet_rect = pygame.Rect(self.panel_x + 8, 8, self.panel_width - 16, 74)
        pygame.draw.rect(surface, (22, 31, 52), wallet_rect, border_radius=8)
        pygame.draw.rect(surface, (52, 82, 128), wallet_rect, width=1, border_radius=8)

        lbl_surf = self.font_wallet_label.render("POINTS", True, (135, 165, 205))
        surface.blit(lbl_surf, (wallet_rect.x + 10, wallet_rect.y + 7))

        pts_surf = self.font_wallet_value.render(f"{self.points:,}", True, (255, 255, 255))
        surface.blit(pts_surf, (wallet_rect.x + 10, wallet_rect.y + 24))

        sub_surf = self.font_wallet_sub.render(
            f"+{self.pb_points} pts / collection", True, (90, 215, 165)
        )
        surface.blit(sub_surf, (wallet_rect.x + 10, wallet_rect.y + 53))

        # Upgrade cards
        for key, upgrade in self.upgrades.items():
            if upgrade.rect is None:
                continue

            rect = upgrade.rect
            affordable = self.can_afford(key)
            maxed = upgrade.is_maxed()
            hovered = rect.collidepoint(mouse_pos)

            # Determine card colors based on affordability & recent click feedback
            if upgrade.purchase_flash > 0.0:
                bg_color = (28, 78, 62)
                border_color = (90, 245, 175)
            elif upgrade.error_flash > 0.0:
                bg_color = (72, 26, 36)
                border_color = (240, 85, 105)
            elif maxed:
                bg_color = (24, 30, 44)
                border_color = (90, 110, 145)
            elif affordable:
                bg_color = (26, 42, 66) if hovered else (21, 34, 54)
                border_color = (85, 225, 170) if hovered else (55, 155, 125)
            else:
                bg_color = (19, 25, 39)
                border_color = (42, 54, 78)

            pygame.draw.rect(surface, bg_color, rect, border_radius=7)
            pygame.draw.rect(surface, border_color, rect, width=1, border_radius=7)

            # Row 1: Upgrade Name & Level
            title_color = (242, 248, 255) if (affordable or maxed) else (145, 160, 185)
            title_surf = self.font_card_title.render(upgrade.name, True, title_color)
            surface.blit(title_surf, (rect.x + 8, rect.y + 6))

            lvl_text = f"Lv.{upgrade.level}"
            lvl_surf = self.font_card_level.render(lvl_text, True, (110, 195, 245))
            surface.blit(
                lvl_surf,
                (rect.right - lvl_surf.get_width() - 8, rect.y + 7),
            )

            # Row 2: Short description
            desc_surf = self.font_card_desc.render(upgrade.description, True, (155, 175, 205))
            surface.blit(desc_surf, (rect.x + 8, rect.y + 26))

            # Row 3: Cost on left, live stat on right
            if maxed:
                cost_text = "MAXED"
                cost_color = (145, 185, 240)
            else:
                cost_text = f"{upgrade.get_cost():,} pts"
                cost_color = (95, 240, 175) if affordable else (225, 105, 115)

            cost_surf = self.font_card_cost.render(cost_text, True, cost_color)
            surface.blit(cost_surf, (rect.x + 8, rect.y + 45))

            stat_text = self._get_live_stat_hint(key, mother_ball)
            stat_surf = self.font_card_desc.render(stat_text, True, (125, 145, 175))
            surface.blit(
                stat_surf,
                (rect.right - stat_surf.get_width() - 8, rect.y + 46),
            )