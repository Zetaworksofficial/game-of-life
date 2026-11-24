function buildBoard() {
  const tiles = new Map();
  const order = [];
  SPINE.forEach(([id, name, label, kind], index) => {
    const row = Math.floor(index / COLS);
    const col = index % COLS;
    const tile = {
      id,
      name,
      label,
      kind,
      x: X0 + (row % 2 === 0 ? col : COLS - 1 - col) * DX,
      y: ROW_Y[row],
      next: [],
      routes: [],
      cost: 0,
      salary: 0,
      job: '',
    };
    if (index + 1 < SPINE.length) tile.next.push(SPINE[index + 1][0]);
    if (id === 's14') {
      tile.salary = 36000;
      tile.job = 'Entry-Level Analyst';
    }
    tiles.set(id, tile);
    order.push(id);
  });

  tiles.get('career').routes = [
    { key: 's14', label: 'Direct Career', detail: '1 stop · $36k salary', cost: 0, salary: 36000, paydays: 0, risk: 0 },
    { key: 'col1', label: 'College', detail: '4 stops · $15k tuition · $62k salary', cost: 15000, salary: 62000, paydays: 0, risk: 0 },
  ];
  tiles.get('detour').routes = [
    { key: 's23', label: 'Straight On', detail: '3 stops · payday, event, home', cost: 0, salary: 0, paydays: 0, risk: 0 },
    { key: 'sc1', label: 'Short Cut', detail: '2 stops · skips two paydays', cost: 0, salary: 0, paydays: 0, risk: 0 },
    { key: 'sc2', label: 'Scenic Route', detail: '4 stops · 2 paydays, 1 event', cost: 0, salary: 0, paydays: 2, risk: 6000 },
  ];

  const branches = [
    { id: 'col1', name: 'College: Enroll', label: 'College', kind: 'career', x: 0.39, y: 0.76, next: ['col2'], cost: 9000 },
    { id: 'col2', name: 'College: Textbooks', label: 'Study', kind: 'career', x: 0.28, y: 0.76, next: ['col3'], cost: 6000 },
    { id: 'col3', name: 'College: Graduate', label: 'Grad', kind: 'career', x: 0.17, y: 0.76, next: ['s16'], salary: 62000, job: 'Graduate Engineer' },
    { id: 'sc1', name: 'Short Cut', label: 'Short Cut', kind: 'safe', x: 0.61, y: 0.29, next: ['s25'] },
    { id: 'sc2', name: 'Roadside Diner', label: 'Pay Day', kind: 'payday', x: 0.61, y: 0.52, next: ['sc3'] },
    { id: 'sc3', name: 'Motel Detour', label: 'Event', kind: 'event', x: 0.72, y: 0.52, next: ['sc4'] },
    { id: 'sc4', name: 'Casino Night', label: 'Pay Day', kind: 'payday', x: 0.83, y: 0.52, next: ['s26'] },
  ];
  for (const branch of branches) {
    tiles.set(branch.id, {
      id: branch.id,
      name: branch.name,
      label: branch.label,
      kind: branch.kind,
      x: branch.x,
      y: branch.y,
      next: branch.next,
      routes: [],
      cost: branch.cost || 0,
      salary: branch.salary || 0,
      job: branch.job || '',
    });
    order.push(branch.id);
  }
  return { tiles, order };
}
