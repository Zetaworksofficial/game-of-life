"""Self-tests for engine.py. Run: python tests/test_engine.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import (  # noqa: E402
    CHILD_UPKEEP,
    HOUSE_PRICE,
    HOUSE_UPKEEP,
    TURN_CAP,
    Game,
    Kind,
    Option,
    Pending,
    build_board,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_board_graph() -> None:
    board, order = build_board()
    check(len(order) == 36, "spine should have 36 tiles")
    for tile in board.values():
        for target in tile.next:
            check(target in board, f"{tile.id} points at missing {target}")
        for route in tile.routes:
            check(route.key in board, f"{tile.id} route to missing {route.key}")
    seen = {"s00"}
    queue = ["s00"]
    while queue:
        tile = board[queue.pop()]
        for target in (*tile.next, *(r.key for r in tile.routes)):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    check(seen == set(board), f"unreachable tiles: {sorted(set(board) - seen)}")
    check(sum(1 for t in board.values() if t.kind is Kind.FORK) == 2, "two forks")
    check(board["s36"].kind is Kind.RETIRE, "last spine tile is retirement")


def test_movement_and_fork() -> None:
    game = Game([("A", False), ("B", False)], seed=1)
    start = game.cur.pos
    path = game.walk(5)
    check(len(path) == 5 and game.cur.pos == path[-1], "walk visits 5 tiles")
    check(game.cur.pos != start, "player moved")

    game = Game([("A", False), ("B", False)], seed=1)
    game.cur.pos = "career"
    game.pending = None
    game.resolve_landing()
    check(game.pending is not None and game.pending.kind == "route", "fork raises a route choice")
    game.answer("col1")
    check(game.cur.routes["career"] == "col1", "route stored")
    game.walk(1)
    check(game.cur.pos == "col1", "college lane entered")
    game.resolve_landing()
    check(game.cur.cash == 22_000 - 9_000, "tuition charged")
    game.walk(2)
    game.resolve_landing()
    check(game.cur.salary == 62_000 and game.cur.college, "graduate salary applied")
    game.walk(1)
    check(game.cur.pos == "s16", "college lane rejoins the spine")


def test_detour_routes() -> None:
    game = Game([("A", False), ("B", False)], seed=3)
    game.cur.pos = "detour"
    game.resolve_landing()
    check(game.pending is not None and len(game.pending.options) == 3, "detour has 3 routes")
    game.answer("sc2")
    game.walk(1)
    check(game.cur.pos == "sc2", "scenic route entered")
    game.walk(3)
    check(game.cur.pos == "s26", "scenic route rejoins s26")


def test_payday_and_tax() -> None:
    game = Game([("A", False), ("B", False)], seed=5)
    player = game.cur
    player.cash = 10_000
    player.salary = 36_000
    player.children = 2
    player.house = "Suburban House"
    game._payday(player)
    expected = 10_000 + 36_000 - 2 * CHILD_UPKEEP - HOUSE_UPKEEP
    check(player.cash == expected, f"payday math {player.cash} != {expected}")

    player.cash = 50_000
    game._tax(player)
    check(player.cash == 45_000, "10% tax on cash")

    player.cash = -1_000
    game._tax(player)
    check(player.cash == -1_000, "no tax on negative cash")


def test_retirement_tiebreak() -> None:
    game = Game([("A", False), ("B", False), ("C", False), ("D", False)], seed=7)
    a, b, c, d = game.players
    a.cash, a.house_value, a.invest = 30_000, 68_000, 0
    b.cash, b.house_value, b.invest = 50_000, 48_000, 0
    c.cash, c.house_value, c.invest = 98_000, 0, 0
    d.cash, d.house_value, d.invest = 30_000, 68_000, 0
    order = [p.pid for p in game.standings()]
    check(order == [2, 1, 0, 3], f"tie-break order {order}")
    for player in game.players:
        player.retired = True
    game._finish("test")
    check(game.over and game.leader is c, "winner is the highest net worth")


def test_house_choice_guard() -> None:
    game = Game([("A", False), ("B", False)], seed=11)
    player = game.cur
    player.cash = HOUSE_PRICE - 1
    game.cur.pos = "s06"
    game.resolve_landing()
    check(game.pending is None, "no modal when the house is unaffordable")
    player.cash = 100_000
    game.resolve_landing()
    check(game.pending is not None, "modal when affordable")
    game.answer("buy")
    check(player.cash == 100_000 - HOUSE_PRICE and player.house_value == 68_000, "house bought")
    game.pending = None
    game.resolve_landing()
    check(game.pending is None, "no second house")


def test_offer_guard() -> None:
    game = Game([("A", False), ("B", False)], seed=13)
    player = game.cur
    player.cash = 500
    game.pending = Pending(
        "offer",
        "Startup Offer",
        "seed money",
        (Option("accept", "Take", cost=10_000), Option("decline", "Pass")),
        source="startup",
        ev=1_700,
    )
    game.answer("accept")
    check(player.cash == 500, "cannot accept an offer without cash")
    check(game.pending is None, "pending cleared after answering")

    player.cash = 40_000
    game.pending = Pending(
        "offer",
        "Startup Offer",
        "seed money",
        (Option("accept", "Take", cost=10_000), Option("decline", "Pass")),
        source="startup",
        ev=1_700,
    )
    game.answer("accept")
    check(28_000 <= player.cash <= 56_000, f"offer resolved to {player.cash}")


def test_full_ai_games() -> None:
    for seed in range(20):
        game = Game([("Maya", True), ("Leo", True), ("Nora", True), ("Kai", True)], seed=seed)
        guard = 0
        while not game.over and guard < 4_000:
            guard += 1
            if game.pending is not None:
                game.answer(game.ai_choice())
                continue
            if game.cur.retired:
                game.end_turn()
                continue
            game.spin()
            game.walk(game.last_spin)
            game.resolve_landing()
            if game.pending is not None:
                game.answer(game.ai_choice())
            game.end_turn()
        check(game.over, f"seed {seed} never finished")
        check(all(p.retired for p in game.players), f"seed {seed} left players on the board")
        check(game.turns <= TURN_CAP, f"seed {seed} hit the turn cap")
        check(len(game.standings()) == 4, "standings complete")
    print("  20 seeded AI games finished cleanly")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print("engine self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
