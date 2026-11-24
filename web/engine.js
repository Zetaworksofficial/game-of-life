class Game {
  constructor(seats) {
    if (!Array.isArray(seats) || seats.length < 2 || seats.length > PLAYER_COLORS.length) {
      throw new Error('The Game of Life needs 2 to 4 players');
    }
    const { tiles, order } = buildBoard();
    this.board = tiles;
    this.order = order;
    this.players = seats.map((seat, index) => ({
      pid: index,
      name: (seat.name || '').trim() || `Player ${index + 1}`,
      isAi: Boolean(seat.isAi),
      color: PLAYER_COLORS[index],
      cash: START_CASH,
      salary: START_SALARY,
      job: START_JOB,
      pos: 's00',
      married: false,
      children: 0,
      house: null,
      houseValue: 0,
      invest: 0,
      routes: {},
      retired: false,
      college: false,
      spin: 0,
    }));
    this.turnIndex = 0;
    this.round = 1;
    this.turns = 0;
    this.over = false;
    this.pending = null;
    this.log = [];
    this.lastSpin = 0;
    this.deck = shuffle(CARDS.slice());
    this.push(`New game: ${this.players.map((p) => p.name).join(', ')}. Spin to move.`, -1);
  }

  get cur() {
    return this.players[this.turnIndex];
  }

  standings() {
    return this.players.slice().sort((a, b) => {
      const worth = netWorth(b) - netWorth(a);
      if (worth !== 0) return worth;
      if (b.cash !== a.cash) return b.cash - a.cash;
      if (b.houseValue !== a.houseValue) return b.houseValue - a.houseValue;
      return a.pid - b.pid;
    });
  }

  tile(id) {
    return this.board.get(id);
  }

  canMove() {
    return this.board.get(this.cur.pos).next.length > 0 && !this.cur.retired;
  }

  spin() {
    this.lastSpin = 1 + Math.floor(Math.random() * SPIN_MAX);
    this.cur.spin = this.lastSpin;
    this.say(`spins ${this.lastSpin}.`);
    return this.lastSpin;
  }

  walk(steps) {
    const player = this.cur;
    const visited = [];
    const count = Math.max(0, Math.trunc(steps));
    for (let i = 0; i < count; i += 1) {
      const tile = this.board.get(player.pos);
      if (!tile.next.length) break;
      player.pos = this.depart(tile);
      visited.push(player.pos);
      if (this.board.get(player.pos).kind === 'retire') break;
    }
    if (visited.length) {
      this.say(`moves ${visited.length} to ${this.board.get(player.pos).name}.`);
    }
    return visited;
  }

  depart(tile) {
    const player = this.cur;
    if (tile.routes.length) {
      const chosen = player.routes[tile.id];
      delete player.routes[tile.id];
      for (const option of tile.routes) {
        if (option.key === chosen) return option.key;
      }
      return tile.routes[0].key;
    }
    return tile.next[0];
  }

  resolveLanding() {
    if (this.pending) throw new Error('resolve the pending choice before resolving another tile');
    const player = this.cur;
    const tile = this.board.get(player.pos);
    switch (tile.kind) {
      case 'start':
        this.say('is at the start.');
        return;
      case 'payday':
        this.payday(player);
        return;
      case 'tax':
        this.tax(player);
        return;
      case 'event':
        this.event(player);
        return;
      case 'marriage':
        this.marriage(player);
        return;
      case 'family':
        this.family(player);
        return;
      case 'house':
        this.house(player);
        return;
      case 'career':
        this.career(player, tile);
        return;
      case 'fork':
        this.fork(player, tile);
        return;
      case 'retire':
        this.retire(player);
        return;
      default:
        this.say(`takes the ${tile.name} — nothing happens.`);
    }
  }

  answer(key) {
    const pending = this.pending;
    if (!pending) return;
    const option = pending.options.find((o) => o.key === key) || pending.options[0];
    this.pending = null;
    const player = this.cur;

    if (pending.kind === 'route') {
      player.routes[pending.source] = option.key;
      this.say(`chooses ${option.label}.`);
      return;
    }

    if (pending.kind === 'house') {
      if (option.key === 'buy') {
        player.cash -= HOUSE_PRICE;
        player.house = 'Suburban House';
        player.houseValue = HOUSE_VALUE;
        this.say(`buys a home for ${dollars(HOUSE_PRICE)} (worth ${dollars(HOUSE_VALUE)}).`);
      } else {
        this.say('keeps renting for now.');
      }
      return;
    }

    const card = CARDS.find((c) => c.id === pending.source);
    const offer = card && card.offer;
    if (!offer) return;
    if (option.key !== 'accept') {
      this.say(`passes on ${card.title}.`);
      return;
    }
    if (player.cash < offer.cost) {
      this.say(`cannot afford ${card.title}.`);
      return;
    }
    player.cash -= offer.cost;
    if (Math.random() < offer.chance) {
      player.cash += offer.win;
      this.say(`${card.title} pays off: ${delta(offer.win)}.`);
    } else {
      player.cash += offer.lose;
      this.say(`${card.title} flops: -${dollars(offer.cost - offer.lose)} net.`);
    }
  }

  endTurn() {
    if (this.over) return;
    this.turns += 1;
    if (this.turns >= TURN_CAP) {
      for (const player of this.players) player.retired = true;
      this.finish('Turn limit reached — final tally.');
      return;
    }
    for (let i = 0; i < this.players.length; i += 1) {
      this.turnIndex = (this.turnIndex + 1) % this.players.length;
      if (this.turnIndex === 0) this.round += 1;
      if (!this.cur.retired) return;
    }
    this.finish('Everyone has retired.');
  }

  payday(player) {
    const expenses = player.children * CHILD_UPKEEP + (player.house ? HOUSE_UPKEEP : 0);
    const net = player.salary - expenses;
    player.cash += net;
    this.say(`Pay Day: ${delta(player.salary)} salary − ${dollars(expenses)} expenses = ${delta(net)}.`);
  }

  tax(player) {
    const due = Math.trunc(Math.max(0, player.cash) * TAX_RATE);
    player.cash -= due;
    this.say(`Tax audit: pays ${dollars(due)} (${Math.trunc(TAX_RATE * 100)}% of cash).`);
  }

  marriage(player) {
    if (player.married) {
      player.cash += ANNIVERSARY_GIFT;
      this.say(`anniversary gift: ${delta(ANNIVERSARY_GIFT)}.`);
      return;
    }
    player.married = true;
    player.cash -= WEDDING_COST;
    player.salary += SPOUSE_SALARY;
    this.say(`gets married: −${dollars(WEDDING_COST)} wedding, ${delta(SPOUSE_SALARY)} spouse salary.`);
  }

  family(player) {
    if (player.children >= CHILD_LIMIT) {
      this.say('has no room for another child — the house is full.');
      return;
    }
    player.children += 1;
    player.cash -= CHILD_COST;
    this.say(`welcomes child #${player.children}: −${dollars(CHILD_COST)}.`);
  }

  house(player) {
    if (player.house) {
      this.say(`already owns the ${player.house} and passes.`);
      return;
    }
    if (player.cash < HOUSE_PRICE) {
      this.say(`cannot afford the ${dollars(HOUSE_PRICE)} house and keeps renting.`);
      return;
    }
    this.pending = {
      kind: 'house',
      title: 'Buy a Home',
      prompt: `A ${dollars(HOUSE_PRICE)} house is on the market. It adds ${dollars(HOUSE_VALUE)} to your net worth.`,
      options: [
        { key: 'buy', label: 'Buy the house', detail: `−${dollars(HOUSE_PRICE)} cash · +${dollars(HOUSE_VALUE)} asset` },
        { key: 'pass', label: 'Keep renting', detail: 'no cash spent' },
      ],
      source: player.pos,
      ev: 0,
    };
    this.say('is house hunting.');
  }

  career(player, tile) {
    let spoke = false;
    if (tile.cost) {
      player.cash -= tile.cost;
      this.say(`pays ${dollars(tile.cost)} for ${tile.name}.`);
      spoke = true;
    }
    if (tile.salary) {
      player.salary = tile.salary;
      player.job = tile.job || tile.name;
      player.college = tile.id === 'col3';
      this.say(`becomes a ${player.job}: salary ${dollars(tile.salary)}.`);
      spoke = true;
    }
    if (!spoke) this.say(`visits ${tile.name}.`);
  }

  fork(player, tile) {
    if (!tile.routes.length) {
      this.say(`reaches ${tile.name}.`);
      return;
    }
    this.pending = {
      kind: 'route',
      title: tile.name,
      prompt:
        tile.id === 'career'
          ? 'Choose the road ahead — the route is yours for the rest of the trip.'
          : 'Pick your road: speed, paydays, or scenery.',
      options: tile.routes.map((route) => ({ ...route })),
      source: tile.id,
      ev: 0,
    };
    this.say(`stops at ${tile.name}.`);
  }

  event(player) {
    const card = this.drawCard();
    this.say(`draws ${card.title}: ${card.text}`);
    if (!card.offer) {
      this.applyCard(player, card);
      return;
    }
    const offer = card.offer;
    this.pending = {
      kind: 'offer',
      title: card.title,
      prompt: card.text,
      options: [
        { key: 'accept', label: 'Take the offer', detail: `−${dollars(offer.cost)} now` },
        { key: 'decline', label: 'Decline', detail: 'keep your cash' },
      ],
      source: card.id,
      ev: Math.trunc(offer.chance * offer.win + (1 - offer.chance) * offer.lose) - offer.cost,
    };
  }

  applyCard(player, card) {
    player.cash += card.cash || 0;
    player.salary = Math.max(0, player.salary + (card.salary || 0));
    player.invest = Math.max(0, player.invest + (card.invest || 0));
    player.houseValue = Math.max(0, player.houseValue + (card.house || 0));
  }

  retire(player) {
    player.retired = true;
    this.say(`retires with a net worth of ${dollars(netWorth(player))}.`);
    if (this.players.every((p) => p.retired)) this.finish('Everyone has retired.');
  }

  drawCard() {
    if (!this.deck.length) this.deck = shuffle(CARDS.slice());
    return this.deck.pop();
  }

  finish(reason) {
    if (this.over) return;
    this.over = true;
    this.pending = null;
    this.push(reason, -1);
    this.standings().forEach((player, index) => {
      this.push(
        `#${index + 1} ${player.name} — ${dollars(netWorth(player))} net worth (${dollars(player.cash)} cash, ${dollars(assets(player))} assets)`,
        player.pid,
      );
    });
  }

  aiChoice() {
    const pending = this.pending;
    if (!pending) throw new Error('no pending choice for the AI to answer');
    const player = this.cur;
    if (pending.kind === 'route') {
      const affordable = pending.options.filter((o) => o.cost <= player.cash);
      const pool = affordable.length ? affordable : pending.options.slice();
      return pool.reduce((best, option) => (routeScore(option, player) > routeScore(best, player) ? option : best)).key;
    }
    if (pending.kind === 'house') {
      const buy = player.cash - HOUSE_PRICE >= 12000 && !player.house;
      return buy ? 'buy' : 'pass';
    }
    if (pending.kind === 'offer') {
      const cost = pending.options[0].cost;
      return pending.ev > 0 && player.cash >= cost + 8000 ? 'accept' : 'decline';
    }
    return pending.options[0].key;
  }

  push(text, pid) {
    this.log.push({ text, pid });
    if (this.log.length > 400) this.log.splice(0, 200);
  }

  say(text) {
    this.push(`${this.cur.name}: ${text}`, this.cur.pid);
  }
}

function routeScore(option, player) {
  const salary = Math.max(player.salary, option.salary);
  return option.salary * 3 + Math.trunc(option.paydays * salary * 0.6) - option.cost - option.risk;
}

const ENGINE = {
  Game,
  buildBoard,
  routeScore,
  assets,
  netWorth,
  dollars,
  delta,
  cards: CARDS,
  spine: SPINE,
  kindColors: KIND_COLORS,
  kindLabels: KIND_LABELS,
  playerColors: PLAYER_COLORS,
  constants: {
    START_CASH,
    START_SALARY,
    START_JOB,
    SPIN_MAX,
    TURN_CAP,
    HOUSE_PRICE,
    HOUSE_VALUE,
    WEDDING_COST,
    SPOUSE_SALARY,
    CHILD_COST,
    CHILD_LIMIT,
    CHILD_UPKEEP,
    HOUSE_UPKEEP,
    TAX_RATE,
    ANNIVERSARY_GIFT,
  },
};

if (typeof module !== 'undefined' && module.exports) module.exports = ENGINE;
