"""The Game of Life: pure rules engine.

The board is a directed graph of tiles. Players spin, walk the graph, resolve
the tile they land on, and retire at the end. Every random draw comes from an
injectable ``random.Random`` so whole games can be replayed from a seed.
This module must stay free of pygame and of any I/O.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Sequence

START_CASH = 22_000
START_SALARY = 12_000
START_JOB = "Part-Timer"
SPIN_MAX = 10
TURN_CAP = 500

HOUSE_PRICE = 60_000
HOUSE_VALUE = 68_000
WEDDING_COST = 10_000
SPOUSE_SALARY = 15_000
CHILD_COST = 8_000
CHILD_LIMIT = 3
CHILD_UPKEEP = 1_800
HOUSE_UPKEEP = 1_200
TAX_RATE = 0.10
ANNIVERSARY_GIFT = 6_000

PLAYER_COLORS: tuple[tuple[int, int, int], ...] = (
    (228, 86, 86),
    (86, 148, 228),
    (72, 196, 138),
    (232, 176, 72),
)


class Kind(str, Enum):
    START = "start"
    PAYDAY = "payday"
    EVENT = "event"
    TAX = "tax"
    MARRIAGE = "marriage"
    HOUSE = "house"
    FAMILY = "family"
    CAREER = "career"
    FORK = "fork"
    RETIRE = "retire"
    SAFE = "safe"


@dataclass(frozen=True)
class Option:
    """A fork route or a modal button. ``key`` is the target tile id or an action id."""

    key: str
    label: str
    detail: str = ""
    cost: int = 0
    salary: int = 0
    paydays: int = 0
    risk: int = 0


@dataclass(frozen=True)
class Tile:
    id: str
    name: str
    label: str
    kind: Kind
    x: float
    y: float
    next: tuple[str, ...] = ()
    routes: tuple[Option, ...] = ()
    cost: int = 0
    salary: int = 0
    job: str = ""


@dataclass(frozen=True)
class Offer:
    cost: int
    chance: float
    win: int
    lose: int


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    text: str
    cash: int = 0
    salary: int = 0
    invest: int = 0
    house: int = 0
    offer: Offer | None = None


@dataclass(frozen=True)
class LogEntry:
    text: str
    pid: int


@dataclass(frozen=True)
class Pending:
    kind: str
    title: str
    prompt: str
    options: tuple[Option, ...]
    source: str = ""
    ev: int = 0


@dataclass
class Player:
    pid: int
    name: str
    is_ai: bool
    color: tuple[int, int, int]
    cash: int = START_CASH
    salary: int = START_SALARY
    job: str = START_JOB
    pos: str = "s00"
    married: bool = False
    children: int = 0
    house: str | None = None
    house_value: int = 0
    invest: int = 0
    routes: dict[str, str] = field(default_factory=dict)
    retired: bool = False
    college: bool = False
    spin: int = 0

    @property
    def assets(self) -> int:
        return self.house_value + self.invest

    @property
    def net_worth(self) -> int:
        return self.cash + self.assets


# --- board ---------------------------------------------------------------

COLS = 9
ROW_Y = (0.88, 0.645, 0.41, 0.175)
X0, DX = 0.06, 0.11

_SPINE: tuple[tuple[str, str, str, Kind], ...] = (
    ("s00", "Start", "Start", Kind.START),
    ("s01", "Scholarship Award", "Event", Kind.EVENT),
    ("s02", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s03", "Tie the Knot", "Marry", Kind.MARRIAGE),
    ("s04", "Life Events", "Event", Kind.EVENT),
    ("s05", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s06", "Buy a Home", "House", Kind.HOUSE),
    ("s07", "Life Events", "Event", Kind.EVENT),
    ("s08", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s09", "Life Events", "Event", Kind.EVENT),
    ("s10", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s11", "Baby Boom", "Baby", Kind.FAMILY),
    ("s12", "Life Events", "Event", Kind.EVENT),
    ("career", "Career Crossroads", "Career", Kind.FORK),
    ("s14", "Entry-Level Job", "Job", Kind.CAREER),
    ("s15", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s16", "Life Events", "Event", Kind.EVENT),
    ("s17", "Tax Audit", "Tax", Kind.TAX),
    ("s18", "Life Events", "Event", Kind.EVENT),
    ("s19", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s20", "Family Time", "Baby", Kind.FAMILY),
    ("s21", "Life Events", "Event", Kind.EVENT),
    ("detour", "Scenic Detour", "Detour", Kind.FORK),
    ("s23", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s24", "Life Events", "Event", Kind.EVENT),
    ("s25", "Second Home", "House", Kind.HOUSE),
    ("s26", "Life Events", "Event", Kind.EVENT),
    ("s27", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s28", "Life Events", "Event", Kind.EVENT),
    ("s29", "Tax Audit", "Tax", Kind.TAX),
    ("s30", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s31", "Family Time", "Baby", Kind.FAMILY),
    ("s32", "Life Events", "Event", Kind.EVENT),
    ("s33", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s35", "Pay Day", "Pay Day", Kind.PAYDAY),
    ("s36", "Retirement", "Retire", Kind.RETIRE),
)

_JOBS: dict[str, tuple[int, str]] = {"s14": (36_000, "Entry-Level Analyst")}


def _grid_pos(index: int) -> tuple[float, float]:
    row, col = divmod(index, COLS)
    x = X0 + (col if row % 2 == 0 else COLS - 1 - col) * DX
    return x, ROW_Y[row]


def build_board() -> tuple[dict[str, Tile], tuple[str, ...]]:
    """Return the tile graph keyed by id plus the spine order."""
    tiles: dict[str, Tile] = {}
    order: list[str] = []
    for i, (tid, name, label, kind) in enumerate(_SPINE):
        x, y = _grid_pos(i)
        nxt = (_SPINE[i + 1][0],) if i + 1 < len(_SPINE) else ()
        salary, job = _JOBS.get(tid, (0, ""))
        tiles[tid] = Tile(tid, name, label, kind, x, y, nxt, salary=salary, job=job)
        order.append(tid)

    career = (
        Option("s14", "Direct Career", "1 stop · $36k salary", salary=36_000),
        Option("col1", "College", "4 stops · $15k tuition · $62k salary", cost=15_000, salary=62_000),
    )
    detour = (
        Option("s23", "Straight On", "3 stops · payday, event, home"),
        Option("sc1", "Short Cut", "2 stops · skips two paydays"),
        Option("sc2", "Scenic Route", "4 stops · 2 paydays, 1 event", paydays=2, risk=6_000),
    )
    tiles["career"] = replace(tiles["career"], routes=career)
    tiles["detour"] = replace(tiles["detour"], routes=detour)

    branches = (
        Tile("col1", "College: Enroll", "College", Kind.CAREER, 0.39, 0.76, ("col2",), cost=9_000),
        Tile("col2", "College: Textbooks", "Study", Kind.CAREER, 0.28, 0.76, ("col3",), cost=6_000),
        Tile(
            "col3",
            "College: Graduate",
            "Grad",
            Kind.CAREER,
            0.17,
            0.76,
            ("s16",),
            salary=62_000,
            job="Graduate Engineer",
        ),
        Tile("sc1", "Short Cut", "Short Cut", Kind.SAFE, 0.61, 0.29, ("s25",)),
        Tile("sc2", "Roadside Diner", "Pay Day", Kind.PAYDAY, 0.61, 0.52, ("sc3",)),
        Tile("sc3", "Motel Detour", "Event", Kind.EVENT, 0.72, 0.52, ("sc4",)),
        Tile("sc4", "Casino Night", "Pay Day", Kind.PAYDAY, 0.83, 0.52, ("s26",)),
    )
    for tile in branches:
        tiles[tile.id] = tile
    return tiles, tuple(order)


# --- cards ---------------------------------------------------------------

CARDS: tuple[Card, ...] = (
    Card("promo", "Promotion", "A senior role opens up: +$8,000 and +$3,000 salary.", cash=8_000, salary=3_000),
    Card("car", "Car Trouble", "The transmission dies: -$6,500.", cash=-6_500),
    Card("index", "Index Fund", "Your portfolio climbs: +$9,000 invested.", invest=9_000),
    Card("crash", "Market Crash", "The market tumbles: -$7,000 invested.", invest=-7_000),
    Card("medical", "Medical Bill", "An unexpected hospital stay: -$7,000.", cash=-7_000),
    Card("inherit", "Inheritance", "A great-aunt remembers you: +$15,000.", cash=15_000),
    Card("mistake", "Paperwork Error", "An accountant's mistake costs you: -$4,000.", cash=-4_000),
    Card("raise", "Merit Raise", "Your boss notices: +$5,000 salary.", salary=5_000),
    Card("dentist", "Root Canal", "Dental work, no insurance: -$3,200.", cash=-3_200),
    Card("refi", "Refinance", "Lower payments free up cash: +$6,000.", cash=6_000),
    Card("flood", "Basement Flood", "Repairs everywhere: -$5,500.", cash=-5_500),
    Card("royalty", "Royalty Cheque", "Something you made years ago sells: +$11,000.", cash=11_000),
    Card(
        "startup",
        "Startup Offer",
        "A friend needs $10,000 seed money. 45% chance of $26,000 back.",
        offer=Offer(cost=10_000, chance=0.45, win=26_000, lose=0),
    ),
    Card(
        "wager",
        "Double or Nothing",
        "Put $8,000 on a coin flip: win $8,000 or lose $8,000.",
        offer=Offer(cost=8_000, chance=0.5, win=8_000, lose=-8_000),
    ),
)

_CARDS_BY_ID = {card.id: card for card in CARDS}


class Game:
    def __init__(self, players: Sequence[tuple[str, bool]], seed: int | None = None) -> None:
        if not 2 <= len(players) <= len(PLAYER_COLORS):
            raise ValueError("The Game of Life needs 2 to 4 players")
        self.rng = random.Random(seed)
        self.board, self.order = build_board()
        self.players = [
            Player(i, name.strip() or f"Player {i + 1}", ai, PLAYER_COLORS[i])
            for i, (name, ai) in enumerate(players)
        ]
        self.turn_index = 0
        self.round = 1
        self.turns = 0
        self.over = False
        self.pending: Pending | None = None
        self.log: list[LogEntry] = []
        self.last_spin = 0
        self._deck: list[Card] = list(CARDS)
        self.rng.shuffle(self._deck)
        names = ", ".join(p.name for p in self.players)
        self._push(f"New game: {names}. Spin to move.", -1)

    # --- queries ---------------------------------------------------------

    @property
    def cur(self) -> Player:
        return self.players[self.turn_index]

    def standings(self) -> list[Player]:
        return sorted(
            self.players,
            key=lambda p: (-p.net_worth, -p.cash, -p.house_value, p.pid),
        )

    @property
    def leader(self) -> Player:
        return self.standings()[0]

    def tile(self, tile_id: str) -> Tile:
        return self.board[tile_id]

    def can_move(self) -> bool:
        return bool(self.board[self.cur.pos].next) and not self.cur.retired

    # --- turn actions ----------------------------------------------------

    def spin(self) -> int:
        self.last_spin = self.rng.randint(1, SPIN_MAX)
        self.cur.spin = self.last_spin
        self._say(f"spins {self.last_spin}.")
        return self.last_spin

    def walk(self, steps: int) -> list[str]:
        """Advance the current player, returning the visited tile ids."""
        player = self.cur
        visited: list[str] = []
        for _ in range(max(0, int(steps))):
            tile = self.board[player.pos]
            if not tile.next:
                break
            player.pos = self._depart(tile)
            visited.append(player.pos)
            if self.board[player.pos].kind is Kind.RETIRE:
                break
        if visited:
            self._say(f"moves {len(visited)} to {self.board[player.pos].name}.")
        return visited

    def _depart(self, tile: Tile) -> str:
        player = self.cur
        if tile.routes:
            chosen = player.routes.pop(tile.id, None)
            for option in tile.routes:
                if option.key == chosen:
                    return option.key
            return tile.routes[0].key
        return tile.next[0]

    def resolve_landing(self) -> list[LogEntry]:
        if self.pending is not None:
            raise RuntimeError("resolve the pending choice before resolving another tile")
        player = self.cur
        tile = self.board[player.pos]
        kind = tile.kind

        if kind is Kind.START:
            return [self._say("is at the start.")]
        if kind is Kind.PAYDAY:
            return self._payday(player)
        if kind is Kind.TAX:
            return self._tax(player)
        if kind is Kind.EVENT:
            return self._event(player)
        if kind is Kind.MARRIAGE:
            return self._marriage(player)
        if kind is Kind.FAMILY:
            return self._family(player)
        if kind is Kind.HOUSE:
            return self._house(player)
        if kind is Kind.CAREER:
            return self._career(player, tile)
        if kind is Kind.FORK:
            return self._fork(player, tile)
        if kind is Kind.RETIRE:
            return self._retire(player)
        return [self._say(f"takes the {tile.name} — nothing happens.")]

    def answer(self, key: str) -> list[LogEntry]:
        pending = self.pending
        if pending is None:
            return []
        option = next((o for o in pending.options if o.key == key), pending.options[0])
        self.pending = None
        player = self.cur
        logs: list[LogEntry] = []

        if pending.kind == "route":
            player.routes[pending.source] = option.key
            logs.append(self._say(f"chooses {option.label}."))
            return logs

        if pending.kind == "house":
            if option.key == "buy":
                player.cash -= HOUSE_PRICE
                player.house = "Suburban House"
                player.house_value = HOUSE_VALUE
                logs.append(
                    self._say(
                        f"buys a home for ${HOUSE_PRICE:,} (worth ${HOUSE_VALUE:,})."
                    )
                )
            else:
                logs.append(self._say("keeps renting for now."))
            return logs

        card = _CARDS_BY_ID[pending.source]
        offer = card.offer
        if offer is None:
            return logs
        if option.key != "accept":
            logs.append(self._say(f"passes on {card.title}."))
            return logs
        if player.cash < offer.cost:
            logs.append(self._say(f"cannot afford {card.title}."))
            return logs
        player.cash -= offer.cost
        if self.rng.random() < offer.chance:
            player.cash += offer.win
            logs.append(
                self._say(f"{card.title} pays off: +${offer.win:,}.")
            )
        else:
            player.cash += offer.lose
            loss = offer.cost - offer.lose
            logs.append(self._say(f"{card.title} flops: -${loss:,} net."))
        return logs

    def end_turn(self) -> None:
        if self.over:
            return
        self.turns += 1
        if self.turns >= TURN_CAP:
            for player in self.players:
                player.retired = True
            self._finish("Turn limit reached — final tally.")
            return
        for _ in range(len(self.players)):
            self.turn_index = (self.turn_index + 1) % len(self.players)
            if self.turn_index == 0:
                self.round += 1
            if not self.cur.retired:
                return
        self._finish("Everyone has retired.")

    # --- tile effects ----------------------------------------------------

    def _payday(self, player: Player) -> list[LogEntry]:
        expenses = player.children * CHILD_UPKEEP + (HOUSE_UPKEEP if player.house else 0)
        income = player.salary
        net = income - expenses
        player.cash += net
        self._say(
            f"Pay Day: +${income:,} salary − ${expenses:,} expenses = {_money(net)}."
        )
        return self.log[-1:]

    def _tax(self, player: Player) -> list[LogEntry]:
        due = int(max(0, player.cash) * TAX_RATE)
        player.cash -= due
        self._say(f"Tax audit: pays ${due:,} ({int(TAX_RATE * 100)}% of cash).")
        return self.log[-1:]

    def _marriage(self, player: Player) -> list[LogEntry]:
        if player.married:
            player.cash += ANNIVERSARY_GIFT
            self._say(f"anniversary gift: +${ANNIVERSARY_GIFT:,}.")
            return self.log[-1:]
        player.married = True
        player.cash -= WEDDING_COST
        player.salary += SPOUSE_SALARY
        self._say(
            f"gets married: −${WEDDING_COST:,} wedding, +${SPOUSE_SALARY:,} spouse salary."
        )
        return self.log[-1:]

    def _family(self, player: Player) -> list[LogEntry]:
        if player.children >= CHILD_LIMIT:
            self._say("has no room for another child — the house is full.")
            return self.log[-1:]
        player.children += 1
        player.cash -= CHILD_COST
        self._say(f"welcomes child #{player.children}: −${CHILD_COST:,}.")
        return self.log[-1:]

    def _house(self, player: Player) -> list[LogEntry]:
        if player.house:
            self._say(f"already owns the {player.house} and passes.")
            return self.log[-1:]
        if player.cash < HOUSE_PRICE:
            self._say(f"cannot afford the ${HOUSE_PRICE:,} house and keeps renting.")
            return self.log[-1:]
        self.pending = Pending(
            "house",
            "Buy a Home",
            f"A ${HOUSE_PRICE:,} house is on the market. It adds ${HOUSE_VALUE:,} to your net worth.",
            (
                Option("buy", "Buy the house", f"−${HOUSE_PRICE:,} cash · +${HOUSE_VALUE:,} asset", cost=HOUSE_PRICE),
                Option("pass", "Keep renting", "no cash spent"),
            ),
            source=player.pos,
        )
        return [self._say("is house hunting.")]

    def _career(self, player: Player, tile: Tile) -> list[LogEntry]:
        logs: list[LogEntry] = []
        if tile.cost:
            player.cash -= tile.cost
            logs.append(self._say(f"pays ${tile.cost:,} for {tile.name}."))
        if tile.salary:
            player.salary = tile.salary
            player.job = tile.job or tile.name
            player.college = tile.id == "col3"
            logs.append(self._say(f"becomes a {player.job}: salary ${tile.salary:,}."))
        return logs or [self._say(f"visits {tile.name}.")]

    def _fork(self, player: Player, tile: Tile) -> list[LogEntry]:
        if not tile.routes:
            return [self._say(f"reaches {tile.name}.")]
        self.pending = Pending(
            "route",
            tile.name,
            "Choose the road ahead — the route is yours for the rest of the trip."
            if tile.id == "career"
            else "Pick your road: speed, paydays, or scenery.",
            tile.routes,
            source=tile.id,
        )
        return [self._say(f"stops at {tile.name}.")]

    def _event(self, player: Player) -> list[LogEntry]:
        card = self._draw_card()
        self._say(f"draws {card.title}: {card.text}")
        logs = self.log[-1:]
        if card.offer is not None:
            offer = card.offer
            ev = int(offer.chance * offer.win + (1 - offer.chance) * offer.lose) - offer.cost
            self.pending = Pending(
                "offer",
                card.title,
                card.text,
                (
                    Option("accept", "Take the offer", f"−${offer.cost:,} now", cost=offer.cost),
                    Option("decline", "Decline", "keep your cash"),
                ),
                source=card.id,
                ev=ev,
            )
            return logs
        self._apply_card(player, card)
        return logs

    def _apply_card(self, player: Player, card: Card) -> None:
        player.cash += card.cash
        player.salary = max(0, player.salary + card.salary)
        player.invest = max(0, player.invest + card.invest)
        player.house_value = max(0, player.house_value + card.house)

    def _retire(self, player: Player) -> list[LogEntry]:
        player.retired = True
        self._say(f"retires with a net worth of ${player.net_worth:,}.")
        logs = self.log[-1:]
        if all(p.retired for p in self.players):
            self._finish("Everyone has retired.")
        return logs

    def _draw_card(self) -> Card:
        if not self._deck:
            self._deck = list(CARDS)
            self.rng.shuffle(self._deck)
        return self._deck.pop()

    def _finish(self, reason: str) -> None:
        if self.over:
            return
        self.over = True
        self.pending = None
        self._push(reason, -1)
        for rank, player in enumerate(self.standings(), start=1):
            self._push(
                f"#{rank} {player.name} — ${player.net_worth:,} net worth "
                f"(${player.cash:,} cash, ${player.assets:,} assets)",
                player.pid,
            )

    # --- AI --------------------------------------------------------------

    def ai_choice(self) -> str:
        """Pick the AI's answer for the current pending choice."""
        pending = self.pending
        if pending is None:
            raise RuntimeError("no pending choice for the AI to answer")
        player = self.cur

        if pending.kind == "route":
            affordable = [o for o in pending.options if o.cost <= player.cash] or list(pending.options)
            return max(affordable, key=lambda o: self._route_score(o, player)).key
        if pending.kind == "house":
            buy = player.cash - HOUSE_PRICE >= 12_000 and not player.house
            return "buy" if buy else "pass"
        if pending.kind == "offer":
            cost = pending.options[0].cost
            return "accept" if pending.ev > 0 and player.cash >= cost + 8_000 else "decline"
        return pending.options[0].key

    @staticmethod
    def _route_score(option: Option, player: Player) -> int:
        salary = max(player.salary, option.salary)
        return option.salary * 3 + int(option.paydays * salary * 0.6) - option.cost - option.risk

    # --- log -------------------------------------------------------------

    def _push(self, text: str, pid: int) -> LogEntry:
        entry = LogEntry(text, pid)
        self.log.append(entry)
        if len(self.log) > 400:
            del self.log[:200]
        return entry

    def _say(self, text: str) -> LogEntry:
        return self._push(f"{self.cur.name}: {text}", self.cur.pid)


def _money(amount: int) -> str:
    return f"+${amount:,}" if amount >= 0 else f"-${abs(amount):,}"
