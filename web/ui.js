'use strict';

const E = ENGINE;

const SPEEDS = [
  ['1x', 1],
  ['2x', 0.5],
  ['4x', 0.25],
  ['step', 0.3],
];

const DEFAULT_SEATS = [
  { name: 'Maya', isAi: false },
  { name: 'Leo', isAi: true },
  { name: 'Nora', isAi: true },
  { name: 'Kai', isAi: true },
];

const LEGEND = ['payday', 'event', 'career', 'marriage', 'house', 'family', 'tax', 'fork', 'retire'];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const el = (selector) => document.querySelector(selector);

let game = null;
let mode = 'setup';
let busy = false;
let speedKey = '1x';
let seatCount = 2;
let seats = DEFAULT_SEATS.map((seat) => ({ ...seat }));
let wheelAngle = 0;
let resolveChoice = null;
let tokenEls = [];
let spinValue = 0;

function speedFactor() {
  return SPEEDS.find(([key]) => key === speedKey)[1];
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function signed(value) {
  return `${value < 0 ? '-' : ''}${Math.abs(value).toLocaleString('en-US')}`;
}

/* --- board ---------------------------------------------------------------- */

function buildLegend() {
  const legend = el('#legend');
  legend.innerHTML = '<span class="legend-title">BOARD KEY</span>' + LEGEND.map((kind) => `
    <span class="key">
      <span class="swatch" style="background:${E.kindColors[kind]}"></span>${E.kindLabels[kind]}
    </span>`).join('');
}

function mountBoard() {
  const tiles = el('#tiles');
  const tokens = el('#tokens');
  const links = el('#links');
  tiles.innerHTML = '';
  links.innerHTML = '';
  tokens.innerHTML = '';

  for (const tile of game.board.values()) {
    const node = document.createElement('div');
    node.className = `tile${tile.kind === 'retire' ? ' retire' : ''}`;
    node.style.left = `${(tile.x * 100).toFixed(3)}%`;
    node.style.top = `${(tile.y * 100).toFixed(3)}%`;
    node.style.background = E.kindColors[tile.kind];
    node.textContent = tile.label;
    node.title = tile.name;
    tiles.appendChild(node);
  }

  const ns = 'http://www.w3.org/2000/svg';
  for (const tile of game.board.values()) {
    for (const targetId of [...tile.next, ...tile.routes.map((route) => route.key)]) {
      const target = game.board.get(targetId);
      const line = document.createElementNS(ns, 'line');
      line.setAttribute('x1', tile.x * 100);
      line.setAttribute('y1', tile.y * 100);
      line.setAttribute('x2', target.x * 100);
      line.setAttribute('y2', target.y * 100);
      links.appendChild(line);
    }
  }

  tokenEls = game.players.map((player) => {
    const node = document.createElement('div');
    node.className = 'token';
    node.style.background = player.color;
    node.textContent = player.name.slice(0, 1).toUpperCase();
    tokens.appendChild(node);
    return node;
  });
  updateTokens();
}

function tokenOffset(pid) {
  const angle = (pid * Math.PI) / 2 - Math.PI / 4;
  return [Math.cos(angle) * 13, Math.sin(angle) * 13];
}

function placeToken(pid, tileId) {
  const tile = game.board.get(tileId);
  const [dx, dy] = tokenOffset(pid);
  const node = tokenEls[pid];
  node.style.left = `calc(${(tile.x * 100).toFixed(3)}% + ${dx.toFixed(2)}px)`;
  node.style.top = `calc(${(tile.y * 100).toFixed(3)}% + ${dy.toFixed(2)}px)`;
}

function updateTokens() {
  if (!game) return;
  for (const player of game.players) placeToken(player.pid, player.pos);
  for (const player of game.players) {
    const active = mode === 'play' && !game.over && player.pid === game.turnIndex;
    tokenEls[player.pid].classList.toggle('active', active);
  }
}

/* --- panel ---------------------------------------------------------------- */

function renderSpeed() {
  el('#speed').innerHTML = SPEEDS.map(([key, factor]) => `
    <button type="button" data-speed="${key}" class="${key === speedKey ? 'active' : ''}">
      ${key === 'step' ? 'Step' : `${factor === 1 ? '1x' : `${1 / factor}x`}`}
    </button>`).join('');
}

function renderBanner() {
  const cur = game.cur;
  el('#banner').innerHTML = `
    <span class="dot" style="background:${cur.color}"></span>
    <div class="who">
      <strong>${escapeHtml(cur.name)}${cur.retired ? ' retired' : "'s turn"}</strong>
      <small>ROUND ${game.round} · ${cur.isAi ? 'AI' : 'HUMAN'}</small>
    </div>
    <span class="worth">${E.dollars(E.netWorth(cur))}</span>`;
}

function renderSpin() {
  el('#spin-value').textContent = spinValue ? String(spinValue) : '?';
  const last = game.cur.spin;
  el('#spin-note').textContent = last ? `last spin ${last}` : 'waiting for first spin';
}

function renderCards() {
  el('#cards').innerHTML = game.players.map((player) => {
    const current = player.pid === game.turnIndex && !game.over;
    const tag = player.retired ? 'DONE' : player.isAi ? 'AI' : 'YOU';
    const net = E.netWorth(player);
    const status = [player.married ? 'married' : 'single', `${player.children} kids`, player.house ? 'home' : 'renting'];
    return `
      <div class="pcard${current ? ' current' : ''}">
        <div class="pc-top">
          <span class="dot" style="background:${player.color}"></span>
          <strong>${escapeHtml(player.name)}</strong>
          <span class="tag${player.retired ? ' done' : ''}">${tag}</span>
        </div>
        <div class="pc-row"><span>cash ${E.dollars(player.cash)}</span><span>assets ${E.dollars(E.assets(player))}</span></div>
        <div class="pc-row"><strong class="net${net < 0 ? ' neg' : ''}">net ${E.dollars(net)}</strong><span>salary ${E.dollars(player.salary)}</span></div>
        <div class="pc-status">${status.join(' - ')}</div>
      </div>`;
  }).join('');
}

function renderLog() {
  const items = game.log.slice(-6);
  el('#log-list').innerHTML = items.map((entry) => {
    const player = game.players[entry.pid];
    const color = player ? player.color : 'var(--muted)';
    return `<li style="color:${color}" title="${escapeHtml(entry.text)}">${escapeHtml(entry.text)}</li>`;
  }).join('');
}

function renderPrimary() {
  const button = el('#primary');
  if (mode !== 'play' || !game || game.over) {
    button.disabled = true;
    button.textContent = 'SPIN';
    return;
  }
  if (game.pending) {
    button.disabled = true;
    button.textContent = 'CHOOSE';
    return;
  }
  if (busy) {
    button.disabled = true;
    button.textContent = game.cur.isAi ? 'AI TURN…' : 'MOVING…';
    return;
  }
  if (game.cur.isAi && speedKey !== 'step') {
    button.disabled = true;
    button.textContent = 'AI TURN';
    return;
  }
  button.disabled = false;
  button.textContent = game.cur.isAi ? 'STEP' : 'SPIN';
}

function render() {
  if (!game) return;
  renderSpeed();
  renderBanner();
  renderSpin();
  renderCards();
  renderLog();
  updateTokens();
  renderPrimary();
}

/* --- wheel ---------------------------------------------------------------- */

function buildWheel() {
  const svg = el('#wheel');
  const ns = 'http://www.w3.org/2000/svg';
  const point = (angle, radius = 92) => {
    const rad = (angle * Math.PI) / 180;
    return [100 + radius * Math.sin(rad), 100 - radius * Math.cos(rad)];
  };
  const group = document.createElementNS(ns, 'g');
  group.id = 'wheel-rot';

  for (let i = 0; i < 10; i += 1) {
    const start = i * 36;
    const end = start + 36;
    const [x0, y0] = point(start);
    const [x1, y1] = point(end);
    const slice = document.createElementNS(ns, 'path');
    slice.setAttribute('d', `M100,100 L${x0.toFixed(2)},${y0.toFixed(2)} A92,92 0 0 1 ${x1.toFixed(2)},${y1.toFixed(2)} Z`);
    slice.setAttribute('fill', i % 2 === 0 ? '#3a465e' : '#2c364a');
    slice.setAttribute('stroke', '#0f131b');
    slice.setAttribute('stroke-width', '1.5');
    group.appendChild(slice);

    const [tx, ty] = point(start + 18, 66);
    const label = document.createElementNS(ns, 'text');
    label.setAttribute('x', tx.toFixed(2));
    label.setAttribute('y', ty.toFixed(2));
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('dominant-baseline', 'central');
    label.setAttribute('fill', '#e8edf5');
    label.setAttribute('font-size', '15');
    label.setAttribute('font-weight', '700');
    label.textContent = String(i + 1);
    group.appendChild(label);
  }

  svg.innerHTML = '';
  svg.appendChild(group);
  svg.insertAdjacentHTML('beforeend', `
    <circle cx="100" cy="100" r="92" fill="none" stroke="#967c42" stroke-width="2"></circle>
    <circle cx="100" cy="100" r="26" fill="#0f131b" stroke="#967c42" stroke-width="2"></circle>
    <polygon points="90,6 110,6 100,30" fill="#e9c46c"></polygon>`);
}

async function spinWheel(value) {
  const duration = Math.max(280, Math.round(1150 * speedFactor()));
  const center = (value - 1) * 36 + 18;
  const delta = (((360 - ((center + wheelAngle) % 360)) % 360) + 360) % 360;
  const target = wheelAngle + 1440 + delta;
  const group = el('#wheel-rot');
  group.style.transition = `transform ${duration}ms cubic-bezier(.12,.7,.1,1)`;
  group.style.transform = `rotate(${target}deg)`;
  wheelAngle = target;
  await sleep(duration + 80);
}

async function walkToken(player, visited) {
  const step = Math.max(70, Math.round(235 * speedFactor()));
  for (const tileId of visited) {
    placeToken(player.pid, tileId);
    await sleep(step);
  }
  updateTokens();
}
