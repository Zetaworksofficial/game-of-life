"""The Game of Life: window, turn flow, speed controls and new-game setup."""

from __future__ import annotations

import argparse
import os

import pygame

from engine import Game
from ui import DEFAULT_NAMES, FPS, Renderer, View, WINDOW

SPEED_MULT = {"1x": 1.0, "2x": 2.0, "4x": 4.0, "step": 4.0}
STEP_SECONDS = 0.17
OFFSETS: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((0, 14),),
    2: ((-15, 14), (15, 14)),
    3: ((-22, 14), (0, 14), (22, 14)),
    4: ((-30, 14), (-10, 14), (10, 14), (30, 14)),
}


class App:
    def __init__(self, seed: int | None = None) -> None:
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption("The Game of Life")
        self.screen = pygame.display.set_mode(WINDOW)
        self.renderer = Renderer(self.screen)
        self.clock = pygame.time.Clock()
        self.seed = seed
        self.running = True
        self.mode = "setup"
        self.count = 3
        self.slots = [False, True, True, True]
        self.speed_key = "2x"
        self.game: Game | None = None
        self.phase = "ready"
        self.spin_value = 0
        self.spin_angle = 0.0
        self.spin_from = 0.0
        self.spin_to = 0.0
        self.spin_t = 0.0
        self.spin_dur = 0.85
        self.spin_active = False
        self.path: list[str] = []
        self.origin = "s00"
        self.step_i = 0
        self.step_t = 0.0
        self.timer = 0.0
        self.hurry = False
        self.tokens: dict[int, tuple[float, float]] = {}
        self.mouse = (-1, -1)

    # --- game lifecycle --------------------------------------------------

    def new_game(self) -> None:
        specs = [(DEFAULT_NAMES[i], self.slots[i]) for i in range(self.count)]
        self.game = Game(specs, seed=self.seed)
        self.renderer.game = self.game
        self.mode = "play"
        self.phase = "ready"
        self.timer = 0.7
        self.hurry = False
        self.spin_value = 0
        self.spin_angle = 0.0
        self.spin_active = False
        self.path = []
        self.step_i = 0
        self.tokens = self.token_positions()

    def back_to_setup(self) -> None:
        self.mode = "setup"
        self.game = None
        self.renderer.game = None
        self.phase = "ready"
        self.tokens = {}

    # --- turn flow -------------------------------------------------------

    def do_spin(self) -> None:
        if self.game is None:
            return
        self.spin_value = self.game.spin()
        self.spin_from = self.spin_angle % 360
        final = -(self.spin_value - 1) * 36 - 18
        self.spin_to = self.spin_from + 360 * 3 + ((final - self.spin_from) % 360)
        self.spin_t = 0.0
        self.spin_dur = 0.85
        self.spin_active = True
        self.phase = "spin"

    def begin_move(self) -> None:
        game = self.game
        if game is None:
            return
        self.origin = game.cur.pos
        self.path = game.walk(self.spin_value)
        if not self.path:
            self.resolve()
            return
        self.step_i = 0
        self.step_t = 0.0
        self.phase = "move"

    def advance_move(self, dt: float) -> None:
        self.step_t += dt
        if self.step_t < STEP_SECONDS:
            return
        self.step_t = 0.0
        self.step_i += 1
        if self.step_i >= len(self.path):
            self.resolve()

    def resolve(self) -> None:
        game = self.game
        if game is None:
            return
        game.resolve_landing()
        if game.over:
            self.end_game()
            return
        if game.pending is not None:
            self.phase = "choice"
            self.timer = 0.35
        else:
            self.phase = "pause"
            self.timer = 0.5

    def finish_turn(self) -> None:
        game = self.game
        if game is None:
            return
        game.end_turn()
        self.hurry = False
        if game.over:
            self.end_game()
            return
        self.phase = "ready"
        self.timer = 0.65

    def end_game(self) -> None:
        self.mode = "over"
        self.phase = "ready"
        self.path = []

    def choose(self, key: str) -> None:
        game = self.game
        if game is None or self.mode != "play" or game.pending is None:
            return
        game.answer(key)
        self.phase = "pause"
        self.timer = 0.45

    # --- input -----------------------------------------------------------

    def click(self, pos: tuple[int, int]) -> None:
        action = self.renderer.hit(pos)
        if action is None:
            return
        kind, _, arg = action.partition(":")
        if kind == "speed":
            self.speed_key = arg
        elif kind == "count":
            step = 1 if arg == "+" else -1
            self.count = max(2, min(4, self.count + step))
        elif kind == "slot":
            index = int(arg)
            self.slots[index] = not self.slots[index]
        elif kind == "start":
            self.new_game()
        elif kind == "new":
            self.back_to_setup()
        elif kind == "spin":
            self.primary()
        elif kind == "choice":
            self.choose(arg)

    def primary(self) -> None:
        game = self.game
        if game is None or self.mode != "play":
            return
        if self.phase == "ready":
            if game.pending is not None:
                self.phase = "choice"
            elif game.cur.retired:
                return
            elif game.cur.is_ai and self.speed_key != "step":
                self.timer = 0.0
            else:
                self.hurry = False
                self.do_spin()
        elif self.phase in ("pause", "choice"):
            self.hurry = True
            self.timer = min(self.timer, 0.05)

    def key(self, code: int) -> None:
        if code == pygame.K_ESCAPE:
            self.running = False
        elif code == pygame.K_SPACE:
            if self.mode == "setup":
                self.new_game()
            else:
                self.primary()
        elif code in (pygame.K_1, pygame.K_2, pygame.K_3):
            game = self.game
            if game is not None and game.pending is not None and self.mode == "play":
                options = game.pending.options
                index = code - pygame.K_1
                if index < len(options):
                    self.choose(options[index].key)
        elif code == pygame.K_r:
            self.back_to_setup()

    # --- frame -----------------------------------------------------------

    def update(self, dt: float) -> None:
        game = self.game
        if game is None or self.mode != "play":
            return
        speed = SPEED_MULT[self.speed_key]
        if self.phase == "spin":
            self.spin_t += dt * speed
            progress = min(1.0, self.spin_t / self.spin_dur)
            eased = 1 - (1 - progress) ** 3
            self.spin_angle = self.spin_from + (self.spin_to - self.spin_from) * eased
            if progress >= 1.0:
                self.spin_active = False
                self.begin_move()
        elif self.phase == "move":
            self.advance_move(dt * speed)
        elif self.phase == "pause":
            self.timer -= dt * speed
            if self.timer <= 0:
                self.finish_turn()
        elif self.phase == "ready":
            if game.pending is not None:
                self.phase = "choice"
                self.timer = 0.3
            elif game.cur.retired:
                game.end_turn()
                if game.over:
                    self.end_game()
                else:
                    self.timer = 0.4
            elif game.cur.is_ai:
                if self.speed_key == "step" and not self.hurry:
                    return
                self.timer -= dt * speed
                if self.timer <= 0:
                    self.do_spin()
        elif self.phase == "choice":
            if game.pending is None:
                self.phase = "pause"
                self.timer = 0.4
            elif game.cur.is_ai:
                self.timer -= dt * speed
                if self.timer <= 0:
                    game.answer(game.ai_choice())
                    self.phase = "pause"
                    self.timer = 0.5

    def token_positions(self) -> dict[int, tuple[float, float]]:
        game = self.game
        if game is None:
            return {}
        groups: dict[str, list[int]] = {}
        for player in game.players:
            groups.setdefault(player.pos, []).append(player.pid)
        tokens: dict[int, tuple[float, float]] = {}
        for tile_id, pids in groups.items():
            cx, cy = self.renderer.tile_center(tile_id)
            for i, pid in enumerate(pids):
                dx, dy = OFFSETS[len(pids)][i]
                tokens[pid] = (cx + dx, cy + dy)
        if self.phase == "move" and self.path and self.mode == "play":
            pid = game.cur.pid
            prev_id = self.origin if self.step_i == 0 else self.path[self.step_i - 1]
            cur_id = self.path[min(self.step_i, len(self.path) - 1)]
            x0, y0 = self.renderer.tile_center(prev_id)
            x1, y1 = self.renderer.tile_center(cur_id)
            t = min(1.0, self.step_t / STEP_SECONDS)
            eased = t * t * (3 - 2 * t)
            tokens[pid] = (x0 + (x1 - x0) * eased, y0 + (y1 - y0) * eased)
        return tokens

    def primary_label(self) -> str:
        game = self.game
        if game is None or self.mode != "play":
            return "SPIN"
        if self.phase == "ready":
            if game.pending is not None:
                return "CHOOSE A ROUTE"
            if game.cur.is_ai:
                return "STEP" if self.speed_key == "step" else "AI SPIN"
            return "SPIN"
        if self.phase == "choice":
            return "CHOOSE BELOW"
        return "WAIT"

    def primary_enabled(self) -> bool:
        game = self.game
        if game is None or self.mode != "play":
            return False
        if self.phase == "ready":
            return game.pending is None
        return self.phase in ("pause", "choice")

    def draw(self) -> None:
        self.tokens = self.token_positions()
        self.renderer.draw(
            View(
                mode=self.mode,
                phase=self.phase,
                game=self.game,
                speed_key=self.speed_key,
                spin_value=self.spin_value,
                spin_angle=self.spin_angle,
                spin_active=self.spin_active,
                token_px=self.tokens,
                pending=self.game.pending if self.game else None,
                primary_label=self.primary_label(),
                primary_enabled=self.primary_enabled(),
                count=self.count,
                slots=self.slots,
                mouse=self.mouse,
            )
        )

    # --- loops -----------------------------------------------------------

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEMOTION:
                    self.mouse = event.pos
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.mouse = event.pos
                    self.click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self.key(event.key)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def smoke(self) -> int:
        self.count = 4
        self.slots = [True, True, True, True]
        self.speed_key = "4x"
        self.draw()
        self.new_game()
        frames = 0
        while self.mode == "play" and frames < 200_000:
            frames += 1
            pygame.event.pump()
            self.update(1 / 60)
            self.draw()
        game = self.game
        if self.mode != "over" or game is None:
            print(f"smoke FAILED: still {self.mode} after {frames} frames")
            return 1
        print(
            f"smoke ok: {frames} frames, {game.turns} turns, "
            f"winner {game.leader.name} at ${game.leader.net_worth:,}"
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="The Game of Life - desktop simulation")
    parser.add_argument("--smoke", action="store_true", help="headless self-check, no window")
    parser.add_argument("--seed", type=int, default=None, help="fixed RNG seed")
    args = parser.parse_args()
    if args.smoke:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    app = App(seed=args.seed)
    if args.smoke:
        return app.smoke()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
