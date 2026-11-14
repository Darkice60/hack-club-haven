from dataclasses import dataclass
import math
import random
from typing import Dict, List, Optional, Tuple
import pygame
from ball import Ghost, MiniGhost, Soul


def format_number(value: int) -> str:
    """Format large integers cleanly (e.g., 12,450 -> 12.4K, 3,200,000 -> 3.20M)."""
    num = int(value)
    if num < 10_000:
        return f"{num:,}"
    for suffix, threshold in [
        ("T", 1_000_000_000_000),
        ("B", 1_000_000_000),
        ("M", 1_000_000),
        ("K", 1_000),
    ]:
        if num >= threshold:
            scaled = num / threshold
            if scaled >= 100:
                return f"{scaled:.0f}{suffix}"
            if scaled >= 10:
                return f"{scaled:.1f}{suffix}"
            return f"{scaled:.2f}{suffix}"
    return f"{num:,}"


@dataclass
class Upgrade:
    """Data container representing a single Cookie Clicker-style exponential upgrade."""

    key: str
    category: str  # "ghost" or "soul"
    name: str
    short_perk: str
    base_cost: int
    cost_multiplier: float
    effect_amount: float
    requires_rebirth: bool = False
    level: int = 0
    max_level: Optional[int] = None
    rect: Optional[pygame.Rect] = None
    purchase_flash: float = 0.0
    error_flash: float = 0.0

    def is_maxed(self) -> bool:
        return self.max_level is not None and self.level >= self.max_level

    def get_cost(self) -> int:
        """Calculate current integer cost using exponential scaling."""
        return int(math.ceil(self.base_cost * (self.cost_multiplier ** self.level)))


class UpgradeManager:
    """Manages Soul currency, Rebirth prestige, and the tabbed tree upgrade shop."""

    INITIAL_GHOST_SPEED: float = 135.0
    INITIAL_GHOST_SIZE: float = 20.0
    INITIAL_SOUL_SPEED: float = 54.0
    INITIAL_SOUL_SIZE: float = 7.0
    INITIAL_SOUL_POINTS: int = 1
    INITIAL_SOUL_COUNT: int = 12

    REBIRTH_BASE_COST: int = 2500
    REBIRTH_COST_MULTIPLIER: float = 6.0

    def __init__(self, panel_x: int, panel_width: int, panel_height: int) -> None:
        self.panel_x: int = panel_x
        self.panel_width: int = panel_width
        self.panel_height: int = panel_height

        # Player currency & Rebirth prestige state
        self.points: int = 0
        self.rebirth_count: int = 0
        self.rebirth_rect: Optional[pygame.Rect] = None
        self.rebirth_flash: float = 0.0
        self.rebirth_error_flash: float = 0.0

        # Active category tab ("ghost" or "soul")
        self.active_tab: str = "ghost"
        self.tab_rects: Dict[str, pygame.Rect] = {}

        # Active tiny Soul template attributes (inherited by all newly spawned Souls)
        self.soul_speed: float = self.INITIAL_SOUL_SPEED
        self.soul_size: float = self.INITIAL_SOUL_SIZE
        self.soul_points: int = self.INITIAL_SOUL_POINTS
        self.soul_target_count: int = self.INITIAL_SOUL_COUNT

        # Special Soul variation probabilities (percentage 0..100)
        self.golden_soul_chance: float = 4.0  # 5x points
        self.devil_soul_chance: float = 1.0   # 15x points

        # Organized into "ghost" upgrades and "soul" upgrades
        self.upgrades: Dict[str, Upgrade] = {
            "ghost_speed": Upgrade(
                key="ghost_speed",
                category="ghost",
                name="Ghost Speed",
                short_perk="Move faster",
                base_cost=5,
                cost_multiplier=1.52,
                effect_amount=24.0,
            ),
            "ghost_size": Upgrade(
                key="ghost_size",
                category="ghost",
                name="Ghost Size",
                short_perk="Grow bigger",
                base_cost=8,
                cost_multiplier=1.58,
                effect_amount=3.0,
                max_level=28,
            ),
            "wall_boost": Upgrade(
                key="wall_boost",
                category="ghost",
                name="Wall Boost",
                short_perk="Bounce burst",
                base_cost=12,
                cost_multiplier=1.60,
                effect_amount=5.0,
                max_level=20,
            ),
            "wind_gust": Upgrade(
                key="wind_gust",
                category="ghost",
                name="Wind Gust",
                short_perk="Click dash",
                base_cost=15,
                cost_multiplier=1.65,
                effect_amount=35.0,
                max_level=15,
            ),
            "black_hole": Upgrade(
                key="black_hole",
                category="ghost",
                name="Black Hole",
                short_perk="Pull souls in",
                base_cost=40,
                cost_multiplier=1.65,
                effect_amount=1.0,
                requires_rebirth=True,
                max_level=18,
            ),
            "mini_ghost": Upgrade(
                key="mini_ghost",
                category="ghost",
                name="Mini Ghost",
                short_perk="+1 Helper ghost",
                base_cost=25,
                cost_multiplier=1.85,
                effect_amount=1.0,
                max_level=6,
            ),
            "soul_luck": Upgrade(
                key="soul_luck",
                category="soul",
                name="Soul Luck",
                short_perk="Gold & Devil souls",
                base_cost=18,
                cost_multiplier=1.68,
                effect_amount=1.0,
                max_level=15,
            ),
            "soul_value": Upgrade(
                key="soul_value",
                category="soul",
                name="Soul Value",
                short_perk="Worth +1 soul",
                base_cost=12,
                cost_multiplier=1.72,
                effect_amount=1.0,
            ),
            "soul_count": Upgrade(
                key="soul_count",
                category="soul",
                name="Soul Count",
                short_perk="+3 Souls in woods",
                base_cost=10,
                cost_multiplier=1.62,
                effect_amount=3.0,
                max_level=35,
            ),
        }

        self._build_layout()

        # Bigger, friendlier Pygame fonts (100% Pygbag compatible)
        self.font_wallet_label = pygame.font.Font(None, 20)
        self.font_wallet_value = pygame.font.Font(None, 38)
        self.font_wallet_sub = pygame.font.Font(None, 20)
        self.font_tab = pygame.font.Font(None, 24)
        self.font_card_title = pygame.font.Font(None, 26)
        self.font_card_level = pygame.font.Font(None, 21)
        self.font_card_sub = pygame.font.Font(None, 22)

    def _build_layout(self) -> None:
        """Compute wallet, Rebirth button, Ghost/Souls tabs, and roomy upgrade cards."""
        margin_x = 12
        card_w = self.panel_width - (margin_x * 2)

        # Top Soul Wallet & Rebirth Button
        self.rebirth_rect = pygame.Rect(self.panel_x + margin_x, 80, card_w, 54)

        # Two category tabs ("Ghost" on left, "Souls" on right)
        tab_y = 140
        tab_h = 42
        tab_gap = 8
        single_tab_w = (card_w - tab_gap) // 2
        self.tab_rects = {
            "ghost": pygame.Rect(self.panel_x + margin_x, tab_y, single_tab_w, tab_h),
            "soul": pygame.Rect(
                self.panel_x + margin_x + single_tab_w + tab_gap, tab_y, single_tab_w, tab_h
            ),
        }

        # Roomy 74px upgrade cards for each tab
        start_y = 190
        card_h = 74
        gap_y = 9

        ghost_idx = 0
        soul_idx = 0
        for upgrade in self.upgrades.values():
            if upgrade.category == "ghost":
                y = start_y + ghost_idx * (card_h + gap_y)
                ghost_idx += 1
            else:
                y = start_y + soul_idx * (card_h + gap_y)
                soul_idx += 1
            upgrade.rect = pygame.Rect(self.panel_x + margin_x, y, card_w, card_h)

    @property
    def rebirth_multiplier(self) -> int:
        """Permanent Soul multiplier earned from Rebirths (1x at 0, 2x at 1, etc.)."""
        return 1 + self.rebirth_count

    def get_rebirth_cost(self) -> int:
        """Exponential Soul requirement for the next Rebirth."""
        return int(
            math.ceil(self.REBIRTH_BASE_COST * (self.REBIRTH_COST_MULTIPLIER ** self.rebirth_count))
        )

    def can_rebirth(self) -> bool:
        """Return True if player has enough Souls to perform a Rebirth."""
        return self.points >= self.get_rebirth_cost()

    def has_affordable_in_tab(self, category: str) -> bool:
        """Return True if at least one upgrade in the given tab can currently be purchased."""
        for key, upgrade in self.upgrades.items():
            if upgrade.category == category and self.can_afford(key):
                return True
        return False

    def perform_rebirth(self, ghost: Ghost, mini_ghosts: List[MiniGhost]) -> bool:
        """
        Reset current run currency and upgrades in exchange for +1 Rebirth level,
        a permanent +1x Soul multiplier, and the Black Hole power.
        """
        if not self.can_rebirth():
            self.rebirth_error_flash = 0.25
            return False

        self.rebirth_count += 1
        self.rebirth_flash = 0.45

        self.points = 0
        self.soul_speed = self.INITIAL_SOUL_SPEED
        self.soul_size = self.INITIAL_SOUL_SIZE
        self.soul_points = self.INITIAL_SOUL_POINTS
        self.soul_target_count = self.INITIAL_SOUL_COUNT
        self.golden_soul_chance = 4.0
        self.devil_soul_chance = 1.0

        mini_ghosts.clear()
        for upgrade in self.upgrades.values():
            upgrade.level = 0
            upgrade.purchase_flash = 0.0
            upgrade.error_flash = 0.0

        ghost.reset_for_rebirth(
            speed=self.INITIAL_GHOST_SPEED,
            size=self.INITIAL_GHOST_SIZE,
            rebirth_count=self.rebirth_count,
        )
        self.upgrades["black_hole"].level = self.rebirth_count
        self.active_tab = "ghost"

        return True

    def roll_soul_variant(self) -> str:
        """Roll whether a newly spawned Soul is 'devil', 'golden', or 'normal'."""
        roll = random.uniform(0.0, 100.0)
        if roll < self.devil_soul_chance:
            return "devil"
        if roll < (self.devil_soul_chance + self.golden_soul_chance):
            return "golden"
        return "normal"

    def add_points(self, amount: int) -> None:
        """Award Souls to the player."""
        self.points += max(0, int(amount))

    def is_upgrade_unlocked(self, upgrade: Upgrade) -> bool:
        """Check whether an upgrade's unlock prerequisite is met."""
        if upgrade.requires_rebirth and self.rebirth_count <= 0:
            return False
        return True

    def can_afford(self, upgrade_key: str) -> bool:
        """Return True if the upgrade is unlocked, not maxed, and player has enough Souls."""
        upgrade = self.upgrades.get(upgrade_key)
        if upgrade is None or not self.is_upgrade_unlocked(upgrade) or upgrade.is_maxed():
            return False
        return self.points >= upgrade.get_cost()

    def purchase(
        self,
        upgrade_key: str,
        ghost: Ghost,
        souls: List[Soul],
        mini_ghosts: List[MiniGhost],
    ) -> bool:
        """Attempt to purchase an upgrade and apply its mechanical effect."""
        upgrade = self.upgrades.get(upgrade_key)
        if upgrade is None or not self.is_upgrade_unlocked(upgrade) or upgrade.is_maxed():
            if upgrade is not None:
                upgrade.error_flash = 0.25
            return False

        cost = upgrade.get_cost()
        if self.points < cost:
            upgrade.error_flash = 0.25
            return False

        self.points -= cost
        upgrade.level += 1
        upgrade.purchase_flash = 0.30

        if upgrade_key == "ghost_speed":
            ghost.apply_speed_upgrade(upgrade.effect_amount)
            for mg in mini_ghosts:
                mg.set_speed(ghost.base_speed * 0.85)
        elif upgrade_key == "ghost_size":
            ghost.apply_size_upgrade(upgrade.effect_amount)
        elif upgrade_key == "wall_boost":
            ghost.apply_boost_chance_upgrade(upgrade.effect_amount)
        elif upgrade_key == "wind_gust":
            ghost.apply_wind_gust_upgrade(upgrade.effect_amount)
        elif upgrade_key == "black_hole":
            ghost.apply_black_hole_upgrade()
        elif upgrade_key == "mini_ghost":
            mini_ghosts.append(
                MiniGhost(
                    x=ghost.x,
                    y=ghost.y,
                    speed=ghost.base_speed * 0.85,
                    arena_width=ghost.arena_width,
                    arena_height=ghost.arena_height,
                )
            )
        elif upgrade_key == "soul_luck":
            self.golden_soul_chance = min(45.0, self.golden_soul_chance + 3.0)
            self.devil_soul_chance = min(20.0, self.devil_soul_chance + 1.2)
        elif upgrade_key == "soul_value":
            self.soul_points += int(upgrade.effect_amount)
            for soul in souls:
                soul.set_base_point_value(self.soul_points)
        elif upgrade_key == "soul_count":
            self.soul_target_count += int(upgrade.effect_amount)

        return True

    def handle_click(
        self,
        mouse_pos: Tuple[int, int],
        ghost: Ghost,
        souls: List[Soul],
        mini_ghosts: List[MiniGhost],
    ) -> Optional[str]:
        """Check if a click hit Rebirth, a category tab, or an active upgrade button."""
        if self.rebirth_rect is not None and self.rebirth_rect.collidepoint(mouse_pos):
            if self.perform_rebirth(ghost, mini_ghosts):
                return "rebirth"
            return None

        for tab_key, tab_rect in self.tab_rects.items():
            if tab_rect.collidepoint(mouse_pos):
                self.active_tab = tab_key
                return f"tab_{tab_key}"

        for key, upgrade in self.upgrades.items():
            if upgrade.category != self.active_tab:
                continue
            if upgrade.rect is not None and upgrade.rect.collidepoint(mouse_pos):
                if self.purchase(key, ghost, souls, mini_ghosts):
                    return key
                return None
        return None

    def update(self, dt: float) -> None:
        """Decay visual feedback timers on Rebirth and upgrade buttons."""
        if self.rebirth_flash > 0.0:
            self.rebirth_flash = max(0.0, self.rebirth_flash - dt)
        if self.rebirth_error_flash > 0.0:
            self.rebirth_error_flash = max(0.0, self.rebirth_error_flash - dt)

        for upgrade in self.upgrades.values():
            if upgrade.purchase_flash > 0.0:
                upgrade.purchase_flash = max(0.0, upgrade.purchase_flash - dt)
            if upgrade.error_flash > 0.0:
                upgrade.error_flash = max(0.0, upgrade.error_flash - dt)

    def _draw_tree_backdrop(self, surface: pygame.Surface) -> None:
        """Draw a giant autumn tree trunk with bark texture, roots, and canopy leaves."""
        px = self.panel_x
        pw = self.panel_width
        ph = self.panel_height

        pygame.draw.rect(surface, (52, 29, 17), pygame.Rect(px, 0, pw, ph))

        bark_grooves = [20, 56, 98, 148, 196, 244, 278]
        for idx, offset in enumerate(bark_grooves):
            gx = px + offset
            groove_col = (38, 20, 11) if idx % 2 == 0 else (66, 38, 22)
            width = 4 if idx % 2 == 0 else 2
            pygame.draw.line(surface, groove_col, (gx, 0), (gx, ph), width)

        pygame.draw.line(surface, (30, 15, 8), (px, 0), (px, ph), 4)
        pygame.draw.line(surface, (90, 52, 28), (px + 4, 0), (px + 4, ph), 2)
        root_poly = [
            (px, ph),
            (px + 30, ph - 16),
            (px + pw - 26, ph - 14),
            (px + pw, ph),
        ]
        pygame.draw.polygon(surface, (42, 22, 13), root_poly)

        canopy = [
            (px + 18, 5, 30, (156, 52, 20)),
            (px + 75, 2, 34, (194, 82, 24)),
            (px + 148, 0, 38, (218, 124, 32)),
            (px + 220, 2, 34, (182, 68, 22)),
            (px + 280, 5, 30, (148, 48, 18)),
        ]
        for lx, ly, lr, lcol in canopy:
            pygame.draw.circle(surface, lcol, (lx, ly), lr)

    def _draw_button_card(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        fill_color: Tuple[int, int, int],
        border_color: Tuple[int, int, int],
    ) -> None:
        """Render a clean, rounded wooden-framed upgrade button."""
        shadow_rect = rect.move(2, 3)
        pygame.draw.rect(surface, (24, 12, 7), shadow_rect, border_radius=9)
        pygame.draw.rect(surface, fill_color, rect, border_radius=9)
        pygame.draw.rect(surface, border_color, rect, width=2, border_radius=9)

    def _draw_mini_ghost_sprite(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        r: int,
        body_col: Tuple[int, int, int] = (242, 234, 224),
    ) -> None:
        """Helper to draw a cute mini Boo-style ghost inside an upgrade or tab icon."""
        pygame.draw.polygon(
            surface,
            (196, 184, 172),
            [
                (cx - int(r * 0.6), cy - 2),
                (cx - int(r * 1.25), cy + 1),
                (cx - int(r * 0.5), cy + int(r * 0.5)),
            ],
        )
        pygame.draw.circle(surface, body_col, (cx, cy), r)
        eye_col = (24, 16, 14)
        pygame.draw.ellipse(
            surface, eye_col, pygame.Rect(cx + 1, cy - int(r * 0.42), 2, max(3, int(r * 0.45)))
        )
        pygame.draw.ellipse(
            surface,
            eye_col,
            pygame.Rect(cx + int(r * 0.42), cy - int(r * 0.42), 2, max(3, int(r * 0.45))),
        )

    def _draw_upgrade_icon(
        self,
        surface: pygame.Surface,
        key: str,
        icon_rect: pygame.Rect,
    ) -> None:
        """Draw a custom picture of the item being upgraded inside a framed medallion."""
        pygame.draw.rect(surface, (34, 20, 14), icon_rect, border_radius=8)
        pygame.draw.rect(surface, (148, 108, 72), icon_rect, width=1, border_radius=8)

        cx = icon_rect.centerx
        cy = icon_rect.centery

        if key == "rebirth":
            pygame.draw.circle(surface, (145, 78, 228), (cx, cy), 14, width=2)
            pygame.draw.circle(surface, (218, 162, 255), (cx, cy), 9, width=2)
            pygame.draw.circle(surface, (28, 12, 42), (cx, cy), 5)
            pygame.draw.circle(surface, (255, 218, 86), (cx + 10, cy - 8), 2)
            pygame.draw.circle(surface, (115, 245, 215), (cx - 10, cy + 8), 2)

        elif key == "ghost_speed":
            for dy in (-7, 0, 7):
                pygame.draw.line(
                    surface, (255, 204, 72), (cx - 16, cy + dy), (cx - 6, cy + dy), 2
                )
            self._draw_mini_ghost_sprite(surface, cx + 5, cy, 11)

        elif key == "ghost_size":
            self._draw_mini_ghost_sprite(surface, cx, cy, 12)
            arrow_col = (255, 206, 76)
            for dx, dy in [(-14, -13), (14, -13), (-14, 13), (14, 13)]:
                pygame.draw.circle(surface, arrow_col, (cx + dx, cy + dy), 2)

        elif key == "wall_boost":
            pygame.draw.rect(
                surface,
                (168, 98, 42),
                pygame.Rect(icon_rect.x + 6, icon_rect.y + 6, 6, icon_rect.height - 12),
                border_radius=2,
            )
            pygame.draw.circle(surface, (245, 132, 36), (cx + 4, cy), 12)
            self._draw_mini_ghost_sprite(surface, cx + 4, cy, 9, body_col=(255, 236, 195))
            pygame.draw.circle(surface, (255, 215, 80), (cx - 7, cy - 9), 2)
            pygame.draw.circle(surface, (255, 215, 80), (cx - 7, cy + 9), 2)

        elif key == "wind_gust":
            wind_col = (125, 245, 212)
            pygame.draw.arc(surface, wind_col, pygame.Rect(cx - 15, cy - 12, 28, 13), 0.2, 3.0, 2)
            pygame.draw.line(surface, wind_col, (cx - 15, cy), (cx + 14, cy), 2)
            pygame.draw.arc(
                surface, (185, 255, 235), pygame.Rect(cx - 12, cy + 1, 25, 12), 3.3, 6.1, 2
            )

        elif key == "black_hole":
            pygame.draw.circle(surface, (158, 86, 238), (cx, cy), 16, width=2)
            pygame.draw.circle(surface, (206, 148, 255), (cx, cy), 10, width=1)
            pygame.draw.circle(surface, (24, 12, 36), (cx, cy), 6)
            pygame.draw.circle(surface, (105, 240, 210), (cx - 12, cy - 9), 3)
            pygame.draw.circle(surface, (105, 240, 210), (cx + 12, cy + 9), 3)

        elif key == "mini_ghost":
            self._draw_mini_ghost_sprite(surface, cx - 7, cy + 4, 7, body_col=(218, 226, 248))
            self._draw_mini_ghost_sprite(surface, cx + 7, cy - 4, 7, body_col=(236, 242, 255))

        elif key == "soul_luck":
            gx, gy = cx - 8, cy + 4
            pygame.draw.circle(surface, (255, 212, 64), (gx, gy), 7)
            pygame.draw.circle(surface, (255, 252, 224), (gx, gy), 3)

            dx, dy = cx + 8, cy - 2
            pygame.draw.circle(surface, (255, 58, 88), (dx, dy), 7)
            pygame.draw.polygon(
                surface, (255, 150, 95), [(dx - 6, dy - 2), (dx - 8, dy - 9), (dx - 1, dy - 6)]
            )
            pygame.draw.polygon(
                surface, (255, 150, 95), [(dx + 6, dy - 2), (dx + 8, dy - 9), (dx + 1, dy - 6)]
            )
            pygame.draw.circle(surface, (255, 215, 190), (dx, dy), 3)

        elif key == "soul_value":
            sx, sy = cx - 4, cy + 4
            pygame.draw.circle(surface, (36, 92, 84), (sx, sy), 10)
            pygame.draw.circle(surface, (105, 240, 210), (sx, sy), 7)
            pygame.draw.circle(surface, (238, 255, 248), (sx, sy), 3)
            px, py = cx + 9, cy - 8
            pygame.draw.line(surface, (255, 220, 72), (px - 5, py), (px + 5, py), 3)
            pygame.draw.line(surface, (255, 220, 72), (px, py - 5), (px, py + 5), 3)

        elif key == "soul_count":
            for ox, oy in [(-8, -7), (8, -6), (-6, 8), (7, 7)]:
                pygame.draw.circle(surface, (36, 92, 84), (cx + ox, cy + oy), 6)
                pygame.draw.circle(surface, (105, 240, 210), (cx + ox, cy + oy), 4)

    def _draw_tabs(self, surface: pygame.Surface, mouse_pos: Tuple[int, int]) -> None:
        """Draw the 'Ghost' and 'Souls' category selector tabs."""
        for tab_key, rect in self.tab_rects.items():
            is_active = self.active_tab == tab_key
            hovered = rect.collidepoint(mouse_pos)

            if is_active:
                fill_col = (108, 60, 30)
                border_col = (248, 188, 76)
                txt_col = (255, 248, 232)
            elif hovered:
                fill_col = (76, 42, 22)
                border_col = (186, 126, 62)
                txt_col = (235, 208, 178)
            else:
                fill_col = (44, 24, 14)
                border_col = (112, 72, 44)
                txt_col = (182, 148, 120)

            self._draw_button_card(surface, rect, fill_col, border_col)

            # Mini tab icon on left + friendly label
            icon_cx = rect.x + 22
            icon_cy = rect.centery
            if tab_key == "ghost":
                self._draw_mini_ghost_sprite(surface, icon_cx, icon_cy, 8)
                label = "Ghost"
            else:
                pygame.draw.circle(surface, (36, 92, 84), (icon_cx, icon_cy), 9)
                pygame.draw.circle(surface, (105, 240, 210), (icon_cx, icon_cy), 6)
                pygame.draw.circle(surface, (238, 255, 248), (icon_cx, icon_cy), 3)
                label = "Souls"

            lbl_surf = self.font_tab.render(label, True, txt_col)
            surface.blit(
                lbl_surf,
                (icon_cx + 16, rect.centery - lbl_surf.get_height() // 2),
            )

            # Green notification dot when an affordable upgrade is waiting in this tab
            if self.has_affordable_in_tab(tab_key):
                dot_pos = (rect.right - 11, rect.y + 11)
                pygame.draw.circle(surface, (32, 84, 44), dot_pos, 6)
                pygame.draw.circle(surface, (118, 255, 148), dot_pos, 4)

    def draw(
        self,
        surface: pygame.Surface,
        mouse_pos: Tuple[int, int],
        ghost: Ghost,
        mini_ghosts: List[MiniGhost],
    ) -> None:
        """Render the tree panel, Soul counter, Rebirth button, Tabs, and active upgrade cards."""
        self._draw_tree_backdrop(surface)

        # 1. Top carved wood sign for the player's Soul count
        wallet_rect = pygame.Rect(self.panel_x + 12, 8, self.panel_width - 24, 66)
        self._draw_button_card(
            surface,
            wallet_rect,
            fill_color=(76, 42, 22),
            border_color=(228, 152, 58),
        )

        lbl_surf = self.font_wallet_label.render("SOULS", True, (245, 196, 124))
        surface.blit(lbl_surf, (wallet_rect.x + 12, wallet_rect.y + 6))

        rb_badge = self.font_wallet_label.render(
            f"REBIRTH: {self.rebirth_count}", True, (216, 168, 255)
        )
        surface.blit(
            rb_badge,
            (wallet_rect.right - rb_badge.get_width() - 12, wallet_rect.y + 6),
        )

        pts_surf = self.font_wallet_value.render(format_number(self.points), True, (255, 250, 236))
        surface.blit(pts_surf, (wallet_rect.x + 12, wallet_rect.y + 21))

        sub_surf = self.font_wallet_sub.render(
            f"{self.rebirth_multiplier}x Souls  •  Gold 5x  •  Devil 15x",
            True,
            (255, 216, 108),
        )
        surface.blit(sub_surf, (wallet_rect.x + 12, wallet_rect.y + 47))

        # 2. Rebirth Card (Green when ready, Red tint when unaffordable; says "Black Hole" clearly)
        if self.rebirth_rect is not None:
            r_rect = self.rebirth_rect
            rb_ready = self.can_rebirth()
            rb_hovered = r_rect.collidepoint(mouse_pos)

            if self.rebirth_flash > 0.0:
                rb_bg = (68, 148, 86)
                rb_border = (195, 255, 205)
            elif self.rebirth_error_flash > 0.0:
                rb_bg = (135, 36, 36)
                rb_border = (255, 118, 118)
            elif rb_ready:
                rb_bg = (46, 128, 66) if rb_hovered else (36, 104, 54)
                rb_border = (165, 255, 182) if rb_hovered else (112, 238, 138)
            else:
                rb_bg = (96, 34, 38)
                rb_border = (206, 86, 92)

            self._draw_button_card(surface, r_rect, rb_bg, rb_border)

            rb_icon_rect = pygame.Rect(r_rect.x + 8, r_rect.y + 7, 40, 40)
            self._draw_upgrade_icon(surface, "rebirth", rb_icon_rect)

            rb_title_txt = (
                "Rebirth -> Black Hole"
                if self.rebirth_count == 0
                else "Rebirth (+Black Hole)"
            )
            rb_title_col = (255, 252, 242) if rb_ready else (246, 214, 216)
            rb_title_surf = self.font_card_title.render(rb_title_txt, True, rb_title_col)
            surface.blit(rb_title_surf, (rb_icon_rect.right + 10, r_rect.y + 7))

            rb_cost_txt = (
                f"{format_number(self.get_rebirth_cost())} souls  •  {self.rebirth_multiplier + 1}x mult"
            )
            rb_cost_col = (168, 255, 192) if rb_ready else (255, 142, 146)
            rb_cost_surf = self.font_card_sub.render(rb_cost_txt, True, rb_cost_col)
            surface.blit(rb_cost_surf, (rb_icon_rect.right + 10, r_rect.y + 30))

        # 3. Category Tabs ("Ghost" vs "Souls")
        self._draw_tabs(surface, mouse_pos)

        # 4. Active Tab Upgrade Cards (Green tint = can buy, Red tint = can't buy yet, Gold = Maxed)
        for key, upgrade in self.upgrades.items():
            if upgrade.category != self.active_tab or upgrade.rect is None:
                continue

            rect = upgrade.rect
            unlocked = self.is_upgrade_unlocked(upgrade)
            affordable = self.can_afford(key)
            maxed = upgrade.is_maxed()
            hovered = rect.collidepoint(mouse_pos)

            if upgrade.purchase_flash > 0.0:
                bg_color = (72, 152, 88)
                border_color = (198, 255, 208)
            elif upgrade.error_flash > 0.0:
                bg_color = (135, 36, 36)
                border_color = (255, 118, 118)
            elif not unlocked:
                bg_color = (54, 34, 62)
                border_color = (136, 94, 164)
            elif maxed:
                bg_color = (108, 78, 28)
                border_color = (245, 198, 84)
            elif affordable:
                bg_color = (48, 128, 68) if hovered else (36, 102, 52)
                border_color = (165, 255, 180) if hovered else (112, 236, 136)
            else:
                bg_color = (98, 34, 34)
                border_color = (212, 88, 88)

            self._draw_button_card(surface, rect, bg_color, border_color)

            # Large framed picture icon of what is being upgraded
            icon_rect = pygame.Rect(rect.x + 10, rect.y + 13, 48, 48)
            self._draw_upgrade_icon(surface, key, icon_rect)

            text_x = icon_rect.right + 12

            # Row 1: Upgrade Name & Level badge
            if maxed:
                title_color = (255, 238, 186)
            elif affordable:
                title_color = (255, 252, 240)
            elif not unlocked:
                title_color = (224, 198, 245)
            else:
                title_color = (245, 218, 218)

            title_surf = self.font_card_title.render(upgrade.name, True, title_color)
            surface.blit(title_surf, (text_x, rect.y + 12))

            lvl_text = "LOCKED" if not unlocked else f"Lv.{upgrade.level}"
            lvl_col = (204, 158, 245) if not unlocked else (255, 218, 118)
            lvl_surf = self.font_card_level.render(lvl_text, True, lvl_col)
            surface.blit(
                lvl_surf,
                (rect.right - lvl_surf.get_width() - 12, rect.y + 14),
            )

            # Row 2: Friendly Cost + Simple Perk in bigger text
            if not unlocked:
                sub_text = "Rebirth to unlock"
                sub_color = (204, 158, 245)
            elif maxed:
                sub_text = f"MAXED  •  {upgrade.short_perk}"
                sub_color = (255, 224, 125)
            elif affordable:
                sub_text = f"{format_number(upgrade.get_cost())} souls  •  {upgrade.short_perk}"
                sub_color = (165, 255, 188)
            else:
                sub_text = f"{format_number(upgrade.get_cost())} souls  •  {upgrade.short_perk}"
                sub_color = (255, 146, 146)

            sub_surf = self.font_card_sub.render(sub_text, True, sub_color)
            surface.blit(sub_surf, (text_x, rect.y + 42))