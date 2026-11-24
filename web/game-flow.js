/* --- choices -------------------------------------------------------------- */

function askChoice(pending) {
  return new Promise((resolve) => {
    resolveChoice = resolve;
    const overlay = el('#modal');
    overlay.classList.remove('hidden');
    overlay.innerHTML = `
      <div class="card modal-card">
        <h2>${escapeHtml(pending.title.toUpperCase())}</h2>
        <p class="prompt">${escapeHtml(pending.prompt)}</p>
        <div class="options">
          ${pending.options.map((option, index) => `
            <button type="button" class="option" data-key="${escapeHtml(option.key)}">
              <span class="opt-label">${index + 1}. ${escapeHtml(option.label)}</span>
              ${option.detail ? `<span class="opt-detail">${escapeHtml(option.detail)}</span>` : ''}
            </button>`).join('')}
        </div>
        <p class="hint">${game.cur.isAi ? 'AI decides in a moment' : `click or press 1-${pending.options.length}`}</p>
      </div>`;
    overlay.querySelectorAll('.option').forEach((button) => {
      button.addEventListener('click', () => chooseOption(button.dataset.key));
    });
    renderPrimary();
  });
}

function chooseOption(key) {
  if (!resolveChoice) return;
  const done = resolveChoice;
  resolveChoice = null;
  el('#modal').classList.add('hidden');
  el('#modal').innerHTML = '';
  done(key);
}

function pickByIndex(index) {
  if (!resolveChoice || !game || !game.pending) return;
  const option = game.pending.options[index];
  if (option) chooseOption(option.key);
}

/* --- turn flow ------------------------------------------------------------ */

async function takeTurn() {
  if (mode !== 'play' || busy || !game || game.over) return;
  if (game.pending) return;
  busy = true;
  spinValue = 0;
  render();

  const player = game.cur;
  const value = game.spin();
  spinValue = value;
  render();
  await spinWheel(value);

  const visited = game.walk(value);
  await walkToken(player, visited);
  render();

  game.resolveLanding();
  render();

  if (game.pending) {
    if (player.isAi) {
      await sleep(Math.max(240, Math.round(760 * speedFactor())));
      game.answer(game.aiChoice());
    } else {
      const key = await askChoice(game.pending);
      game.answer(key);
    }
    render();
  }

  await sleep(Math.max(120, Math.round(320 * speedFactor())));
  game.endTurn();
  busy = false;
  render();

  if (game.over) {
    await sleep(420);
    showGameOver();
    return;
  }
  maybeAuto();
}

function maybeAuto() {
  if (mode !== 'play' || busy || !game || game.over || game.pending) return;
  if (game.cur.isAi && speedKey !== 'step') takeTurn();
}

/* --- overlays ------------------------------------------------------------- */

function seatRow(index) {
  const seat = seats[index];
  return `
    <div class="seat">
      <span class="dot" style="background:${E.playerColors[index]}"></span>
      <input class="name" data-seat="${index}" maxlength="14" value="${escapeHtml(seat.name)}" aria-label="Player ${index + 1} name" />
      <button type="button" class="toggle${seat.isAi ? ' ai' : ''}" data-toggle="${index}">
        ${seat.isAi ? 'AI player' : 'Human player'}
        <small>click to switch seat</small>
      </button>
    </div>`;
}

function renderSetup() {
  mode = 'setup';
  game = null;
  busy = false;
  resolveChoice = null;
  spinValue = 0;
  el('#gameover').classList.add('hidden');
  el('#modal').classList.add('hidden');
  const setup = el('#setup');
  setup.classList.remove('hidden');
  setup.innerHTML = `
    <div class="card setup-card">
      <h2>THE GAME OF LIFE</h2>
      <p class="sub">Spin, pick your road, retire the richest.</p>
      <div class="row">
        <span class="kicker">PLAYERS</span>
        <div class="counter">
          <button type="button" data-count="-" ${seatCount <= 2 ? 'disabled' : ''}>-</button>
          <strong>${seatCount}</strong>
          <button type="button" data-count="+" ${seatCount >= 4 ? 'disabled' : ''}>+</button>
        </div>
      </div>
      <div class="seats">${seats.slice(0, seatCount).map((_, index) => seatRow(index)).join('')}</div>
      <button type="button" class="primary" id="start">START GAME</button>
      <p class="hint">Space = spin · 1-3 = choose · R = new game</p>
    </div>`;
}

function startGame() {
  el('#setup').classList.add('hidden');
  el('#setup').innerHTML = '';
  el('#modal').classList.add('hidden');
  el('#gameover').classList.add('hidden');
  game = new E.Game(seats.slice(0, seatCount));
  mode = 'play';
  busy = false;
  wheelAngle = 0;
  spinValue = 0;
  mountBoard();
  render();
  maybeAuto();
}

function showGameOver() {
  mode = 'over';
  const ranking = game.standings();
  const overlay = el('#gameover');
  overlay.classList.remove('hidden');
  overlay.innerHTML = `
    <div class="card over-card">
      <h2>RETIREMENT</h2>
      <p class="sub">richest net worth wins</p>
      <ol class="ranking">
        ${ranking.map((player, index) => `
          <li class="${index === 0 ? 'winner' : ''}">
            <span class="dot" style="background:${player.color}"></span>
            <strong>${escapeHtml(player.name)}</strong>
            <span class="rank">#${index + 1}</span>
            <span class="detail">cash ${E.dollars(player.cash)} · assets ${E.dollars(E.assets(player))}</span>
            <strong class="worth">${E.dollars(E.netWorth(player))}</strong>
          </li>`).join('')}
      </ol>
      <button type="button" class="primary" id="again">NEW GAME</button>
    </div>`;
  renderPrimary();
}

/* --- events --------------------------------------------------------------- */

function bindEvents() {
  document.addEventListener('click', (event) => {
    const target = event.target.closest('button');
    if (!target) return;

    if (target.dataset.speed) {
      speedKey = target.dataset.speed;
      render();
      maybeAuto();
      return;
    }
    if (target.dataset.count && target.closest('#setup')) {
      seedsToInputs();
      const step = target.dataset.count === '+' ? 1 : -1;
      seatCount = Math.min(4, Math.max(2, seatCount + step));
      renderSetup();
      return;
    }
    if (target.dataset.toggle !== undefined && target.closest('#setup')) {
      seedsToInputs();
      const index = Number(target.dataset.toggle);
      seats[index].isAi = !seats[index].isAi;
      renderSetup();
      return;
    }
    if (target.id === 'start') {
      seedsToInputs();
      startGame();
      return;
    }
    if (target.id === 'again') {
      renderSetup();
      return;
    }
    if (target.id === 'primary') {
      takeTurn();
    }
  });

  document.addEventListener('input', (event) => {
    const input = event.target.closest('.seat input');
    if (!input) return;
    seats[Number(input.dataset.seat)].name = input.value;
  });

  document.addEventListener('keydown', (event) => {
    if (event.target instanceof HTMLInputElement) return;
    if (event.key === ' ' || event.code === 'Space') {
      event.preventDefault();
      if (!el('#primary').disabled) takeTurn();
      return;
    }
    if (/^[1-3]$/.test(event.key) && resolveChoice) {
      pickByIndex(Number(event.key) - 1);
      return;
    }
    if (event.key === 'r' || event.key === 'R') {
      seedsToInputs();
      renderSetup();
    }
  });
}

function seedsToInputs() {
  document.querySelectorAll('.seat input').forEach((input) => {
    seats[Number(input.dataset.seat)].name = input.value;
  });
}

buildLegend();
buildWheel();
bindEvents();
renderSetup();
