"""pygame front-end: board track, car tokens, spinner, modals, HUD, controls.

The renderer only reads ``engine`` state plus the ``View`` frame data handed to
it by ``main.py``; every clickable region is registered and reported back as an
action string so the app owns all state transitions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from engine import PLAYER_COLORS, Game, Kind, Pending, Player, Tile

WINDOW = (1440, 920)
FPS = 60
DEFAULT_NAMES = ("Maya", "Leo", "Nora", "Kai")

BG = (11, 15, 22)
BOARD_BG = (17, 22, 32)
BOARD_EDGE = (33, 41, 57)
PANEL = (20, 26, 38)
CARD = (27, 34, 48)
CARD_HI = (37, 47, 65)
EDGE = (52, 63, 84)
TEXT = (232, 237, 245)
MUTED = (146, 159, 181)
DIM = (92, 102, 122)
GOLD = (233, 196, 108)
GOLD_DIM = (150, 124, 66)
GOOD = (96, 202, 132)
BAD = (222, 100, 100)

TILE_W, TILE_H = 92, 56
TOKEN_R = 10

KIND_COLORS: dict[Kind, tuple[int, int, int]] = {
    Kind.START: (74, 110, 200),
    Kind.PAYDAY: (48, 146, 84),
    Kind.EVENT: (114, 78, 206),
    Kind.TAX: (188, 58, 58),
    Kind.MARRIAGE: (206, 74, 122),
    Kind.HOUSE: (214, 108, 44),
    Kind.FAMILY: (20, 148, 126),
    Kind.CAREER: (46, 116, 194),
    Kind.FORK: (216, 152, 40),
    Kind.RETIRE: (238, 206, 128),
    Kind.SAFE: (84, 98, 122),
}

LEGEND = (
    (Kind.PAYDAY, "Pay Day"),
    (Kind.EVENT, "Event"),
    (Kind.CAREER, "Career"),
    (Kind.MARRIAGE, "Wedding"),
    (Kind.HOUSE, "Home"),
    (Kind.FAMILY, "Child"),
    (Kind.TAX, "Tax"),
    (Kind.FORK, "Fork"),
    (Kind.RETIRE, "Retire"),
)


@dataclass
class View:
    mode: str
    phase: str
    game: Game | None
    speed_key: str
    spin_value: int
    spin_angle: float
    spin_active: bool
    token_px: dict[int, tuple[float, float]]
    pending: Pending | None
    primary_label: str
    primary_enabled: bool
    count: int
    slots: list[bool]
    mouse: tuple[int, int]


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.game: Game | None = None
        self.board_rect = pygame.Rect(20, 96, 980, 800)
        self.panel_rect = pygame.Rect(1016, 16, 408, 888)
        self.mouse: tuple[int, int] = (-1, -1)
        self.buttons: list[tuple[str, pygame.Rect, bool]] = []
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}

    # --- primitives ------------------------------------------------------

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont("dejavusans,arial,tahoma", size, bold=bold)
        return self._fonts[key]

    def text(
        self,
        value: str,
        size: int,
        color: tuple[int, int, int],
        pos: tuple[float, float],
        *,
        bold: bool = False,
        anchor: str = "topleft",
    ) -> pygame.Rect:
        surf = self.font(size, bold).render(value, True, color)
        rect = surf.get_rect(**{anchor: pos})
        self.screen.blit(surf, rect)
        return rect

    def wrap(self, value: str, size: int, width: int) -> list[str]:
        font = self.font(size)
        lines: list[str] = []
        line = ""
        for word in value.split():
            probe = f"{line} {word}".strip()
            if font.size(probe)[0] <= width or not line:
                line = probe
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def ellipsis(self, value: str, size: int, width: int) -> str:
        font = self.font(size)
        if font.size(value)[0] <= width:
            return value
        while value and font.size(value + "...")[0] > width:
            value = value[:-1]
        return value + "..."

    def button(
        self,
        action: str,
        rect: pygame.Rect,
        label: str,
        *,
        enabled: bool = True,
        primary: bool = False,
        active: bool = False,
        sub: str = "",
        size: int = 14,
    ) -> None:
        hover = enabled and rect.collidepoint(self.mouse)
        if not enabled:
            base, fg = (24, 30, 42), DIM
        elif primary:
            base, fg = ((246, 214, 138) if hover else GOLD), (26, 22, 12)
        else:
            base, fg = ((46, 58, 78) if hover else CARD), TEXT
        pygame.draw.rect(self.screen, base, rect, border_radius=10)
        if not primary:
            pygame.draw.rect(self.screen, EDGE if enabled else (36, 44, 58), rect, 1, border_radius=10)
        if active:
            pygame.draw.rect(self.screen, GOLD, rect, 2, border_radius=10)
        if sub:
            self.text(label, size, fg, (rect.centerx, rect.centery - 9), bold=True, anchor="center")
            self.text(sub, 11, MUTED if enabled else DIM, (rect.centerx, rect.centery + 12), anchor="center")
        else:
            self.text(label, size, fg, rect.center, bold=True, anchor="center")
        self.buttons.append((action, rect, enabled))

    def hit(self, pos: tuple[int, int]) -> str | None:
        for action, rect, enabled in reversed(self.buttons):
            if enabled and rect.collidepoint(pos):
                return action
        return None

    def tile_center(self, tile_id: str) -> tuple[float, float]:
        if self.game is None:
            return (0.0, 0.0)
        tile = self.game.board[tile_id]
        return (
            self.board_rect.x + tile.x * self.board_rect.w,
            self.board_rect.y + tile.y * self.board_rect.h,
        )

    # --- frame -----------------------------------------------------------

    def draw(self, view: View) -> None:
        self.buttons.clear()
        self.mouse = view.mouse
        self.game = view.game
        self.screen.fill(BG)
        if view.mode == "setup" or view.game is None:
            self._setup(view)
            return
        self._board(view.game)
        self._tokens(view)
        self._panel(view)
        if view.pending is not None:
            self._modal(view, view.pending)
        if view.mode == "over":
            self._over(view)

    # --- board -----------------------------------------------------------

    def _board(self, game: Game) -> None:
        pygame.draw.rect(self.screen, BOARD_BG, self.board_rect.inflate(16, 16), border_radius=20)
        pygame.draw.rect(self.screen, BOARD_EDGE, self.board_rect.inflate(16, 16), 1, border_radius=20)
        for tile in game.board.values():
            start = self.tile_center(tile.id)
            for target in (*tile.next, *(route.key for route in tile.routes)):
                pygame.draw.line(self.screen, EDGE, start, self.tile_center(target), 3)
        for tile in game.board.values():
            self._tile(tile)
        self._legend()

    def _tile(self, tile: Tile) -> None:
        cx, cy = self.tile_center(tile.id)
        rect = pygame.Rect(0, 0, TILE_W, TILE_H)
        rect.center = (round(cx), round(cy))
        pygame.draw.rect(self.screen, KIND_COLORS[tile.kind], rect, border_radius=9)
        pygame.draw.rect(self.screen, (14, 18, 26), rect, 1, border_radius=9)
        fg = (28, 24, 14) if tile.kind is Kind.RETIRE else TEXT
        self.text(tile.label, 13, fg, (rect.centerx, rect.centery - 10), bold=True, anchor="center")

    def _legend(self) -> None:
        x = self.board_rect.x + 18
        y = self.board_rect.y + 52
        self.text("BOARD KEY", 11, MUTED, (self.board_rect.x + 18, self.board_rect.y + 24), bold=True)
        for kind, label in LEGEND:
            pygame.draw.rect(self.screen, KIND_COLORS[kind], pygame.Rect(x, y + 4, 14, 14), border_radius=4)
            self.text(label, 12, MUTED, (x + 22, y + 2))
            x += 36 + self.font(12).size(label)[0]

    def _tokens(self, view: View) -> None:
        game = view.game
        if game is None:
            return
        for player in game.players:
            pos = view.token_px.get(player.pid)
            if pos is None:
                continue
            center = (round(pos[0]), round(pos[1]))
            if player.pid == game.cur.pid and view.mode == "play":
                pygame.draw.circle(self.screen, GOLD, center, TOKEN_R + 3, 2)
            pygame.draw.circle(self.screen, (8, 11, 17), (center[0], center[1] + 3), TOKEN_R)
            pygame.draw.circle(self.screen, player.color, center, TOKEN_R)
            pygame.draw.circle(self.screen, (16, 20, 28), center, TOKEN_R, 2)
            self.text(player.name[:1].upper(), 10, (13, 17, 25), center, bold=True, anchor="center")

    # --- panel -----------------------------------------------------------

    def _panel(self, view: View) -> None:
        game = view.game
        if game is None:
            return
        panel = self.panel_rect
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=18)
        pygame.draw.rect(self.screen, BOARD_EDGE, panel, 1, border_radius=18)

        self.text("THE GAME OF LIFE", 20, GOLD, (panel.x + 20, panel.y + 16), bold=True)
        self.text("financial road simulation", 11, MUTED, (panel.x + 20, panel.y + 44))

        for i, (key, label) in enumerate((("1x", "1x"), ("2x", "2x"), ("4x", "4x"), ("step", "Step"))):
            rect = pygame.Rect(panel.x + 20 + i * 92, panel.y + 64, 84, 32)
            self.button(f"speed:{key}", rect, label, active=view.speed_key == key, size=13)

        self._banner(game)
        self._spinner_block(view)
        self.button(
            "spin",
            pygame.Rect(panel.x + 20, panel.y + 330, panel.w - 40, 48),
            view.primary_label,
            enabled=view.primary_enabled,
            primary=view.primary_enabled,
            size=16,
        )

        cards_y = panel.y + 392
        for i, player in enumerate(game.players):
            rect = pygame.Rect(panel.x + 20, cards_y + i * 80, panel.w - 40, 74)
            self._player_card(player, rect, player.pid == game.cur.pid)
        self._log(game, cards_y + len(game.players) * 80 + 8)

    def _banner(self, game: Game) -> None:
        panel = self.panel_rect
        rect = pygame.Rect(panel.x + 20, panel.y + 108, panel.w - 40, 44)
        pygame.draw.rect(self.screen, CARD, rect, border_radius=10)
        cur = game.cur
        pygame.draw.circle(self.screen, cur.color, (rect.x + 20, rect.centery), 8)
        who = f"{cur.name}'s turn" if not cur.retired else f"{cur.name} retired"
        self.text(who, 15, TEXT, (rect.x + 38, rect.centery - 10), bold=True, anchor="midleft")
        tag = "AI" if cur.is_ai else "HUMAN"
        self.text(f"ROUND {game.round} - {tag}", 10, MUTED, (rect.x + 38, rect.centery + 8), anchor="midleft")
        self.text(f"${cur.net_worth:,}", 15, GOLD, (rect.right - 16, rect.centery), bold=True, anchor="midright")

    def _spinner_block(self, view: View) -> None:
        panel = self.panel_rect
        top = panel.y + 162
        self._spinner((panel.x + 96, top + 74), 72, view.spin_angle, view.spin_value, view.spin_active)
        self.text("SPIN", 10, MUTED, (panel.x + 188, top + 28), bold=True)
        self.text(str(view.spin_value) if view.spin_value else "?", 40, GOLD, (panel.x + 186, top + 44), bold=True)
        last = self.game.cur.spin if self.game else 0
        note = f"last spin {last}" if last else "waiting for first spin"
        self.text(note, 11, MUTED, (panel.x + 188, top + 104))

    def _spinner(
        self,
        center: tuple[int, int],
        radius: int,
        angle: float,
        value: int,
        active: bool,
    ) -> None:
        cx, cy = center
        for i in range(10):
            a0 = math.radians(angle + i * 36)
            a1 = math.radians(angle + (i + 1) * 36)
            points = [(cx, cy)]
            for step in range(5):
                a = a0 + (a1 - a0) * step / 4
                points.append((cx + radius * math.sin(a), cy - radius * math.cos(a)))
            shade = (58, 70, 94) if i % 2 == 0 else (44, 54, 74)
            pygame.draw.polygon(self.screen, shade, points)
            mid = (a0 + a1) / 2
            self.text(
                str(i + 1),
                13,
                TEXT if not active else GOLD,
                (cx + radius * 0.72 * math.sin(mid), cy - radius * 0.72 * math.cos(mid)),
                bold=True,
                anchor="center",
            )
        pygame.draw.circle(self.screen, GOLD_DIM, center, radius, 2)
        pygame.draw.circle(self.screen, (15, 19, 27), center, 26)
        pygame.draw.circle(self.screen, GOLD_DIM, center, 26, 2)
        pygame.draw.polygon(
            self.screen,
            GOLD,
            [(cx - 10, cy - radius - 18), (cx + 10, cy - radius - 18), (cx, cy - radius + 2)],
        )
        if value:
            self.text(str(value), 20, GOLD, center, bold=True, anchor="center")

    def _player_card(self, player: Player, rect: pygame.Rect, current: bool) -> None:
        pygame.draw.rect(self.screen, CARD_HI if current else CARD, rect, border_radius=10)
        if current:
            pygame.draw.rect(self.screen, GOLD, rect, 2, border_radius=10)
        pygame.draw.circle(self.screen, player.color, (rect.x + 18, rect.y + 17), 8)
        self.text(player.name, 14, TEXT, (rect.x + 34, rect.y + 6), bold=True)
        tag = "DONE" if player.retired else ("AI" if player.is_ai else "YOU")
        self.text(tag, 10, MUTED if player.retired else GOLD, (rect.right - 14, rect.y + 8), bold=True, anchor="topright")
        self.text(f"cash ${player.cash:,}", 11, MUTED, (rect.x + 14, rect.y + 24))
        self.text(f"assets ${player.assets:,}", 11, MUTED, (rect.right - 14, rect.y + 24), anchor="topright")
        self.text(
            f"net ${player.net_worth:,}",
            13,
            GOOD if player.net_worth >= 0 else BAD,
            (rect.x + 14, rect.y + 40),
            bold=True,
        )
        self.text(f"salary ${player.salary:,}", 11, MUTED, (rect.right - 14, rect.y + 41), anchor="topright")
        status = ["married" if player.married else "single", f"{player.children} kids"]
        status.append("home" if player.house else "renting")
        self.text(" - ".join(status), 10, MUTED, (rect.x + 14, rect.y + 58))

    def _log(self, game: Game, top: int) -> None:
        panel = self.panel_rect
        rect = pygame.Rect(panel.x + 20, top, panel.w - 40, panel.bottom - 24 - top)
        pygame.draw.rect(self.screen, CARD, rect, border_radius=10)
        self.text("TURN LOG", 10, MUTED, (rect.x + 12, rect.y + 9), bold=True)
        y = rect.y + 26
        for entry in game.log[-6:]:
            color = game.players[entry.pid].color if 0 <= entry.pid < len(game.players) else MUTED
            self.text(self.ellipsis(entry.text, 11, rect.w - 24), 11, color, (rect.x + 12, y))
            y += 18

    # --- overlays --------------------------------------------------------

    def _modal(self, view: View, pending: Pending) -> None:
        self._dim()
        count = len(pending.options)
        rect = pygame.Rect(0, 0, 620, 104 + count * 68 + 26)
        rect.center = (WINDOW[0] // 2, WINDOW[1] // 2)
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=16)
        pygame.draw.rect(self.screen, GOLD_DIM, rect, 1, border_radius=16)
        self.text(pending.title.upper(), 19, GOLD, (rect.x + 26, rect.y + 20), bold=True)
        y = rect.y + 52
        for line in self.wrap(pending.prompt, 13, rect.w - 52):
            self.text(line, 13, MUTED, (rect.x + 26, y))
            y += 19
        y = rect.y + 104
        for i, option in enumerate(pending.options):
            self.button(
                f"choice:{option.key}",
                pygame.Rect(rect.x + 26, y, rect.w - 52, 60),
                f"{i + 1}. {option.label}",
                sub=option.detail,
                size=15,
            )
            y += 68
        tag = "AI decides in a moment" if view.game and view.game.cur.is_ai else f"click or press 1-{count}"
        self.text(tag, 11, MUTED, (rect.centerx, rect.bottom - 14), anchor="center")

    def _over(self, view: View) -> None:
        game = view.game
        if game is None:
            return
        self._dim()
        ranking = game.standings()
        rect = pygame.Rect(0, 0, 720, 184 + 46 * len(ranking))
        rect.center = (WINDOW[0] // 2, WINDOW[1] // 2)
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=18)
        pygame.draw.rect(self.screen, GOLD_DIM, rect, 1, border_radius=18)
        self.text("RETIREMENT", 26, GOLD, (rect.centerx, rect.y + 34), bold=True, anchor="center")
        self.text("richest net worth wins", 12, MUTED, (rect.centerx, rect.y + 66), anchor="center")
        y = rect.y + 98
        for rank, player in enumerate(ranking, start=1):
            row = pygame.Rect(rect.x + 30, y, rect.w - 60, 40)
            winner = rank == 1
            pygame.draw.rect(self.screen, CARD_HI if winner else CARD, row, border_radius=9)
            if winner:
                pygame.draw.rect(self.screen, GOLD, row, 2, border_radius=9)
            pygame.draw.circle(self.screen, player.color, (row.x + 20, row.centery), 8)
            self.text(player.name, 14, TEXT, (row.x + 36, row.centery), bold=True, anchor="midleft")
            self.text(f"#{rank}", 12, MUTED, (row.x + 130, row.centery), anchor="midleft")
            self.text(
                f"${player.net_worth:,}",
                15,
                GOLD if winner else TEXT,
                (row.right - 16, row.centery),
                bold=True,
                anchor="midright",
            )
            detail = f"cash ${player.cash:,} - assets ${player.assets:,}"
            self.text(detail, 11, MUTED, (row.right - 130, row.centery), anchor="midright")
            y += 46
        self.button(
            "new",
            pygame.Rect(rect.centerx - 140, rect.bottom - 62, 280, 44),
            "NEW GAME",
            primary=True,
            size=15,
        )

    def _dim(self) -> None:
        overlay = pygame.Surface(WINDOW, pygame.SRCALPHA)
        overlay.fill((5, 8, 13, 195))
        self.screen.blit(overlay, (0, 0))

    # --- setup -----------------------------------------------------------

    def _setup(self, view: View) -> None:
        card = pygame.Rect(0, 0, 680, 300 + view.count * 68)
        card.center = (WINDOW[0] // 2, WINDOW[1] // 2)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=18)
        pygame.draw.rect(self.screen, BOARD_EDGE, card, 1, border_radius=18)
        self.text("THE GAME OF LIFE", 32, GOLD, (card.centerx, card.y + 44), bold=True, anchor="center")
        self.text("Spin, pick your road, retire the richest.", 13, MUTED, (card.centerx, card.y + 80), anchor="center")

        y = card.y + 122
        self.text("PLAYERS", 11, MUTED, (card.x + 36, y + 10), bold=True)
        minus = pygame.Rect(card.x + 150, y, 42, 36)
        plus = pygame.Rect(card.x + 232, y, 42, 36)
        self.button("count:-", minus, "-", enabled=view.count > 2, size=18)
        self.button("count:+", plus, "+", enabled=view.count < 4, size=18)
        self.text(str(view.count), 20, TEXT, ((minus.right + plus.x) // 2, y + 18), bold=True, anchor="center")

        for i in range(view.count):
            row = pygame.Rect(card.x + 36, card.y + 176 + i * 68, card.w - 72, 56)
            pygame.draw.rect(self.screen, CARD, row, border_radius=10)
            pygame.draw.circle(self.screen, PLAYER_COLORS[i], (row.x + 26, row.centery), 10)
            self.text(DEFAULT_NAMES[i], 15, TEXT, (row.x + 48, row.centery), bold=True, anchor="midleft")
            toggle = pygame.Rect(row.right - 200, row.y + 10, 180, 36)
            ai = view.slots[i]
            self.button(
                f"slot:{i}",
                toggle,
                "AI player" if ai else "Human player",
                sub="click to switch seat",
                size=13,
            )

        self.button(
            "start",
            pygame.Rect(card.x + 36, card.bottom - 88, card.w - 72, 52),
            "START GAME",
            primary=True,
            size=17,
        )
        self.text(
            "Space = spin  -  1-3 = choose  -  R = new game",
            11,
            MUTED,
            (card.centerx, card.bottom - 18),
            anchor="center",
        )
