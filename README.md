# The Game of Life — Desktop Simulation

A playable desktop take on *The Game of Life* in Python + pygame. Four players
(human or AI) drive the spinner around a 43-tile board, choose between college
and a direct career, take detours, get married, start a family, buy a house and
retire with the highest net worth.

## Features

- **Full board track** — a 36-tile serpentine spine ending at Retirement, plus a
  three-tile college path, a short cut and a scenic loop.
- **Animated spinner** — a wheel that eases out to a random 1–10, with a numeric
  readout and a turn log.
- **Human choice modals** — career fork, detour fork, marriage, children and the
  house offer all pause the game for a real decision.
- **AI players** — score every affordable route by salary, paydays, cost and
  risk; buy the house only when they keep a $12k buffer; accept positive-EV
  offers only with an $8k cushion.
- **Clean HUD** — cash, assets, net worth, salary and status for every player,
  plus the last few log entries.
- **Speed control** — `1x`, `2x`, `4x`, and a `Step` mode that advances one AI
  turn per click.
- **Deterministic tests** — seeded AI games and rules checks, no pygame needed.

## Screens

- **Setup** — pick 2–4 players and set each seat to human or AI.
- **Board** — the spine snakes right-to-left across four rows, with the college
  lane below and the scenic detour above; tokens stack on shared tiles.
- **Modals** — dimmed overlay with each fork option and its trade-off.
- **Retirement** — final standings ranked by net worth.

## Rules

| Item | Value |
| --- | --- |
| Starting cash | $22,000 |
| Starting salary | $12,000 (Part-Timer) |
| Direct career | $36,000, 1 stop |
| College | −$15,000, then $62,000, 4 stops |
| House | $60,000 cash for $68,000 of net worth |
| Turn cap | 500 turns, forces a finish |

- Landing on or passing a payday tile pays your salary; taxes and living
  expenses are deducted at each payday.
- Fork tiles store the chosen route per player and consume it on departure.
  Passing through a fork without landing takes the default spine route.
- Retirement ranks by net worth, breaking ties by cash, then house value, then
  player order.

## Controls

| Input | Action |
| --- | --- |
| `Space` / click **SPIN** | Spin the wheel on your turn |
| Click an option in a modal | Resolve career, detour, marriage, child or house |
| `1` `2` `3` | Choose option 1–3 in the open modal |
| `R` | Reset back to the setup screen |

## Getting started

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python main.py                 # play
```

### Headless checks

```bash
python tests/test_engine.py            # engine rules + 20 seeded AI games
python main.py --smoke --seed 7        # run a full game with no window
```

`--smoke` uses SDL's dummy drivers, so it works over SSH and in CI.

## Project layout

```
engine.py             # pure rules: board, spinner, money, milestones, AI — no pygame
ui.py                 # rendering, hit regions, modals, HUD, setup screen
main.py               # window loop, turn state machine, speed, CLI flags
tests/test_engine.py  # engine self-tests
```

The engine holds all state and decisions and imports nothing from pygame; the
renderer only reads engine state and reports clicks back as action strings, so
the same rules can be driven by tests or a headless run.

## License

MIT
