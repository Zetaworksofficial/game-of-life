'use strict';

const START_CASH = 22000;
const START_SALARY = 12000;
const START_JOB = 'Part-Timer';
const SPIN_MAX = 10;
const TURN_CAP = 500;

const HOUSE_PRICE = 60000;
const HOUSE_VALUE = 68000;
const WEDDING_COST = 10000;
const SPOUSE_SALARY = 15000;
const CHILD_COST = 8000;
const CHILD_LIMIT = 3;
const CHILD_UPKEEP = 1800;
const HOUSE_UPKEEP = 1200;
const TAX_RATE = 0.1;
const ANNIVERSARY_GIFT = 6000;

const PLAYER_COLORS = ['#e45656', '#5694e4', '#48c48a', '#e8b048'];

const KIND_COLORS = {
  start: '#4a6ec8',
  payday: '#309254',
  event: '#724ece',
  tax: '#bc3a3a',
  marriage: '#ce4a7a',
  house: '#d66c2c',
  family: '#14947e',
  career: '#2e74c2',
  fork: '#d89828',
  retire: '#eece80',
  safe: '#54627a',
};

const COLS = 9;
const ROW_Y = [0.88, 0.645, 0.41, 0.175];
const X0 = 0.06;
const DX = 0.11;

const SPINE = [
  ['s00', 'Start', 'Start', 'start'],
  ['s01', 'Scholarship Award', 'Event', 'event'],
  ['s02', 'Pay Day', 'Pay Day', 'payday'],
  ['s03', 'Tie the Knot', 'Marry', 'marriage'],
  ['s04', 'Life Events', 'Event', 'event'],
  ['s05', 'Pay Day', 'Pay Day', 'payday'],
  ['s06', 'Buy a Home', 'House', 'house'],
  ['s07', 'Life Events', 'Event', 'event'],
  ['s08', 'Pay Day', 'Pay Day', 'payday'],
  ['s09', 'Life Events', 'Event', 'event'],
  ['s10', 'Pay Day', 'Pay Day', 'payday'],
  ['s11', 'Baby Boom', 'Baby', 'family'],
  ['s12', 'Life Events', 'Event', 'event'],
  ['career', 'Career Crossroads', 'Career', 'fork'],
  ['s14', 'Entry-Level Job', 'Job', 'career'],
  ['s15', 'Pay Day', 'Pay Day', 'payday'],
  ['s16', 'Life Events', 'Event', 'event'],
  ['s17', 'Tax Audit', 'Tax', 'tax'],
  ['s18', 'Life Events', 'Event', 'event'],
  ['s19', 'Pay Day', 'Pay Day', 'payday'],
  ['s20', 'Family Time', 'Baby', 'family'],
  ['s21', 'Life Events', 'Event', 'event'],
  ['detour', 'Scenic Detour', 'Detour', 'fork'],
  ['s23', 'Pay Day', 'Pay Day', 'payday'],
  ['s24', 'Life Events', 'Event', 'event'],
  ['s25', 'Second Home', 'House', 'house'],
  ['s26', 'Life Events', 'Event', 'event'],
  ['s27', 'Pay Day', 'Pay Day', 'payday'],
  ['s28', 'Life Events', 'Event', 'event'],
  ['s29', 'Tax Audit', 'Tax', 'tax'],
  ['s30', 'Pay Day', 'Pay Day', 'payday'],
  ['s31', 'Family Time', 'Baby', 'family'],
  ['s32', 'Life Events', 'Event', 'event'],
  ['s33', 'Pay Day', 'Pay Day', 'payday'],
  ['s35', 'Pay Day', 'Pay Day', 'payday'],
  ['s36', 'Retirement', 'Retire', 'retire'],
];

const CARDS = [
  { id: 'promo', title: 'Promotion', text: 'A senior role opens up: +$8,000 and +$3,000 salary.', cash: 8000, salary: 3000 },
  { id: 'car', title: 'Car Trouble', text: 'The transmission dies: -$6,500.', cash: -6500 },
  { id: 'index', title: 'Index Fund', text: 'Your portfolio climbs: +$9,000 invested.', invest: 9000 },
  { id: 'crash', title: 'Market Crash', text: 'The market tumbles: -$7,000 invested.', invest: -7000 },
  { id: 'medical', title: 'Medical Bill', text: 'An unexpected hospital stay: -$7,000.', cash: -7000 },
  { id: 'inherit', title: 'Inheritance', text: 'A great-aunt remembers you: +$15,000.', cash: 15000 },
  { id: 'mistake', title: 'Paperwork Error', text: "An accountant's mistake costs you: -$4,000.", cash: -4000 },
  { id: 'raise', title: 'Merit Raise', text: 'Your boss notices: +$5,000 salary.', salary: 5000 },
  { id: 'dentist', title: 'Root Canal', text: 'Dental work, no insurance: -$3,200.', cash: -3200 },
  { id: 'refi', title: 'Refinance', text: 'Lower payments free up cash: +$6,000.', cash: 6000 },
  { id: 'flood', title: 'Basement Flood', text: 'Repairs everywhere: -$5,500.', cash: -5500 },
  { id: 'royalty', title: 'Royalty Cheque', text: 'Something you made years ago sells: +$11,000.', cash: 11000 },
  {
    id: 'startup',
    title: 'Startup Offer',
    text: 'A friend needs $10,000 seed money. 45% chance of $26,000 back.',
    offer: { cost: 10000, chance: 0.45, win: 26000, lose: 0 },
  },
  {
    id: 'wager',
    title: 'Double or Nothing',
    text: 'Put $8,000 on a coin flip: win $8,000 or lose $8,000.',
    offer: { cost: 8000, chance: 0.5, win: 8000, lose: -8000 },
  },
];

const KIND_LABELS = {
  start: 'Start',
  payday: 'Pay Day',
  event: 'Event',
  tax: 'Tax',
  marriage: 'Wedding',
  house: 'Home',
  family: 'Child',
  career: 'Career',
  fork: 'Fork',
  retire: 'Retire',
  safe: 'Safe',
};

function dollars(amount) {
  return `${amount < 0 ? '-$' : '$'}${Math.abs(amount).toLocaleString('en-US')}`;
}

function delta(amount) {
  return `${amount < 0 ? '-$' : '+$'}${Math.abs(amount).toLocaleString('en-US')}`;
}

function assets(player) {
  return player.houseValue + player.invest;
}

function netWorth(player) {
  return player.cash + assets(player);
}

function shuffle(list) {
  for (let i = list.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [list[i], list[j]] = [list[j], list[i]];
  }
  return list;
}
