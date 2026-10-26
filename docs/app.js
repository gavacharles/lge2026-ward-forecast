(async () => {
  const PARTY = {
    ANC: { name: 'ANC', color: '#22a05a' }, DA: { name: 'DA', color: '#3b7ddd' }, MK: { name: 'MK', color: '#8c7a3a' },
    EFF: { name: 'EFF', color: '#d6334a' }, IFP: { name: 'IFP', color: '#e0a21b' }, PA: { name: 'PA', color: '#9a6fd6' },
    FFP: { name: 'FF+', color: '#f07f2a' }, ASA: { name: 'ActionSA', color: '#2fb3a6' }, OTH: { name: 'Other', color: '#8a8f98' },
  };
  const RATE_COLOR = { 'Toss-up': '#c2362f', Lean: '#e3a54a', Likely: '#9fb7c4', Safe: '#dfe4e1' };
  const METROS = ['JHB', 'CPT', 'ETH', 'TSH', 'EKU', 'NMA', 'BUF', 'MAN'];
  const titleCase = (s) => String(s).toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  const pname = (p) => (PARTY[p] ? PARTY[p].name : titleCase(p));
  const pcolor = (p) => (PARTY[p] ? PARTY[p].color : PARTY.OTH.color);
  const pct = (x) => Math.round(x * 100) + '%';
  const fmt = (x) => x.toLocaleString('en-ZA');
  const el = (tag, props = {}, ...kids) => { const e = document.createElement(tag); Object.assign(e, props); e.append(...kids); return e; };
  const partyTag = (p) => el('span', { className: 'party' }, el('span', { className: 'sw', style: `background:${pcolor(p)}` }), pname(p));

  const [F, topo] = await Promise.all([
    fetch('data/forecast.json').then((r) => r.json()),
    fetch('data/wards.topo.json').then((r) => r.json()),
  ]);
  const P = F.parties;
  const wardRows = Object.entries(F.wards).map(([id, w]) => {
    const live = w.live && w.live.rep > 0 ? { f: w.live.f, p: w.live.p, s: w.live.s, rep: w.live.rep } : {};
    return { id, ...w, ...live, pre: { f: w.f, p: w.p }, muni: F.munis[w.m].name, prov: F.munis[w.m].prov };
  });
  const byId = Object.fromEntries(wardRows.map((w) => [w.id, w]));
  const nat = Object.fromEntries(F.national.map((r) => [r.party, r]));

  // ---------- header ----------
  const lede = document.getElementById('lede');
  lede.replaceChildren(
    'The ANC is favoured in ', el('b', {}, fmt(nat.ANC.fav)), ' of ', el('b', {}, fmt(wardRows.length)),
    ' wards, the DA in ', el('b', {}, fmt(nat.DA.fav)), ' and MK in ', el('b', {}, fmt(nat.MK.fav)), '. ',
    el('b', {}, fmt(F.ratings['Toss-up'] || 0)), ' wards are toss-ups, and ', el('b', {}, fmt(F.flips)),
    ' wards are forecast to change hands from their estimated 2021 winner.'
  );
  document.getElementById('generated').textContent = `Forecast generated ${F.generated}, using polls to ${F.polls.as_of} and ${F.byelections_used} by-elections. Election day ${F.election_date}.`;
  if (F.live) {
    const counted = wardRows.filter((w) => w.rep > 0).length;
    const banner = document.getElementById('live-banner');
    banner.hidden = false;
    banner.replaceChildren(el('b', {}, 'Live count. '), `Results are coming in: ${fmt(counted)} wards have at least one voting district counted. Ward calls below blend counted votes with the forecast for districts still out.`);
  }
  const tiles = document.getElementById('tiles');
  for (const p of ['ANC', 'DA', 'MK', 'IFP']) {
    tiles.append(el('div', { className: 'tile' },
      el('div', { className: 'k' }, el('span', { className: 'sw', style: `background:${pcolor(p)}` }), `${pname(p)} favoured`),
      el('div', { className: 'v' }, fmt(nat[p].fav)),
      el('div', { className: 's' }, `${nat[p].share.toFixed(1)}% of the vote`)));
  }
  tiles.append(el('div', { className: 'tile' },
    el('div', { className: 'k' }, 'Toss-up wards'),
    el('div', { className: 'v' }, fmt(F.ratings['Toss-up'] || 0)),
    el('div', { className: 's' }, 'No party above 60% chance')));

  // ---------- map ----------
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  const map = L.map('map', { preferCanvas: true, zoomSnap: 0.5, minZoom: 4 });
  const base = dark ? 'Dark' : 'Light';
  const esri = (name) => `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_${base}_Gray_${name}/MapServer/tile/{z}/{y}/{x}`;
  L.tileLayer(esri('Base'), {
    attribution: 'Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors · Wards: Municipal Demarcation Board',
    maxZoom: 16,
  }).addTo(map);
  map.createPane('labels');
  map.getPane('labels').style.zIndex = 650;
  map.getPane('labels').style.pointerEvents = 'none';
  L.tileLayer(esri('Reference'), { pane: 'labels', maxZoom: 16 }).addTo(map);

  const geo = topojson.feature(topo, topo.objects.wards);
  let mode = 'fav';
  let shareParty = 'ANC';
  let selected = null;
  const lineColor = dark ? '#0d1110' : '#ffffff';

  function style(f) {
    const w = byId[f.properties.WardID];
    const s = { weight: 0.4, color: lineColor, fillOpacity: 0.85, fillColor: '#999' };
    if (!w) return { ...s, fillOpacity: 0.1 };
    if (mode === 'fav') { s.fillColor = pcolor(w.f); s.fillOpacity = 0.25 + 0.7 * Math.max(0, (w.p - 0.35) / 0.65); }
    else if (mode === 'rating') { s.fillColor = RATE_COLOR[w.r]; s.fillOpacity = 0.9; }
    else if (mode === 'flip') {
      const flip = w.f !== w.w21;
      s.fillColor = flip ? pcolor(w.f) : (dark ? '#3a423f' : '#d9dedb'); s.fillOpacity = flip ? 0.9 : 0.6;
    } else {
      const v = w.s[P.indexOf(shareParty)] / 100;
      s.fillColor = pcolor(shareParty); s.fillOpacity = Math.min(0.95, v / 0.6);
    }
    if (selected && f.properties.WardID === selected) { s.weight = 2.5; s.color = dark ? '#ffffff' : '#111111'; }
    return s;
  }
  const layer = L.geoJSON(geo, {
    style,
    onEachFeature: (f, lyr) => {
      lyr.on('click', () => select(f.properties.WardID, false));
      const w = byId[f.properties.WardID];
      if (w) lyr.bindTooltip(`${w.muni} ward ${w.n}: ${pname(w.f)} ${pct(w.p)}`, { sticky: true });
    },
  }).addTo(map);
  const layerById = {};
  layer.eachLayer((l) => { layerById[l.feature.properties.WardID] = l; });
  map.fitBounds(layer.getBounds(), { padding: [10, 10] });

  // ---------- ward panel ----------
  const panel = document.getElementById('panel');
  function select(id, zoom) {
    const w = byId[id];
    if (!w) return;
    const prev = selected;
    selected = id;
    if (prev && layerById[prev]) layerById[prev].setStyle(style(layerById[prev].feature));
    const lyr = layerById[id];
    if (lyr) { lyr.setStyle(style(lyr.feature)); lyr.bringToFront(); if (zoom) map.fitBounds(lyr.getBounds(), { maxZoom: 13, padding: [40, 40] }); }
    const order = P.map((p, i) => [p, w.s[i]]).sort((a, b) => b[1] - a[1]);
    const bars = el('div', { className: 'bars' }, ...order.filter(([, v]) => v >= 0.5).map(([p, v]) =>
      el('div', { className: 'bar' }, el('span', {}, pname(p)),
        el('span', { className: 'track' }, el('span', { className: 'fill', style: `display:block;width:${Math.min(100, v)}%;background:${pcolor(p)}` })),
        el('span', { className: 'val' }, v.toFixed(1)))));
    const dl = el('dl', {},
      el('dt', {}, 'Rating'), el('dd', {}, el('span', { className: 'rate ' + w.r }, w.r)),
      el('dt', {}, 'Runner-up'), el('dd', {}, partyTag(w.u)),
      el('dt', {}, 'Margin'), el('dd', {}, `${w.g.toFixed(1)} points`),
      el('dt', {}, '2021 winner'), el('dd', {}, partyTag(w.w21), ' (estimated, new boundaries)'),
      ...(w.k ? [el('dt', {}, 'Community type'), el('dd', {}, `Voted ${w.k} in 2024`)] : []),
      ...(w.rep > 0 ? [el('dt', {}, 'Counted'), el('dd', {}, `${pct(w.rep)} of expected votes; pre-election favourite ${pname(w.pre.f)} (${pct(w.pre.p)})`)] : []));
    panel.replaceChildren(
      el('h3', {}, `${w.muni} ward ${w.n}`),
      el('p', { className: 'sub' }, `${w.prov} · ward ID ${id}`),
      el('div', { className: 'call' }, el('span', { className: 'sw', style: `background:${pcolor(w.f)};width:14px;height:14px` }),
        el('b', {}, pname(w.f)), `${pct(w.p)} chance to win`),
      dl,
      el('p', { className: 'sub' }, 'Forecast vote share (%), ward ballot'),
      bars,
      ...(w.c < 0.8 ? [el('p', { className: 'sub' }, 'Part of this ward has no past results at voting-district level, so this forecast leans more on the municipality as a whole.')] : []),
    );
  }

  // ---------- map controls ----------
  const sharePick = document.getElementById('share-party');
  sharePick.append(...P.map((p) => new Option(pname(p), p)));
  sharePick.addEventListener('change', () => { shareParty = sharePick.value; restyle(); });
  document.querySelectorAll('.seg button').forEach((b) => b.addEventListener('click', () => {
    mode = b.dataset.mode;
    document.querySelectorAll('.seg button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
    sharePick.hidden = mode !== 'share';
    restyle();
  }));
  function restyle() { layer.setStyle(style); drawLegend(); }

  const legend = document.getElementById('legend');
  function drawLegend() {
    legend.replaceChildren();
    const item = (color, label) => el('span', {}, el('span', { className: 'sw', style: `background:${color}` }), label);
    if (mode === 'fav') {
      const shown = ['ANC', 'DA', 'MK', 'EFF', 'IFP', 'PA', 'FFP', 'ASA', 'OTH'];
      legend.append(...shown.map((p) => item(pcolor(p), p === 'OTH' ? 'Local party / independent' : pname(p))), el('span', {}, 'Stronger colour means a safer ward'));
    } else if (mode === 'rating') {
      legend.append(...['Toss-up', 'Lean', 'Likely', 'Safe'].map((r) => item(RATE_COLOR[r], { 'Toss-up': 'Toss-up (under 60%)', Lean: 'Lean (60–75%)', Likely: 'Likely (75–90%)', Safe: 'Safe (90%+)' }[r])));
    } else if (mode === 'flip') {
      legend.append(el('span', {}, 'Coloured wards are forecast to change hands, in the colour of the new favourite. Grey wards stay with their 2021 winner.'));
    } else {
      legend.append(el('span', {}, '0%'), el('span', { className: 'ramp', style: `background:linear-gradient(90deg, transparent, ${pcolor(shareParty)})` }), el('span', {}, `60%+ ${pname(shareParty)} share`));
    }
  }
  drawLegend();

  // zoom to municipality
  const zProv = document.getElementById('z-prov'), zMuni = document.getElementById('z-muni');
  const provinces = [...new Set(wardRows.map((w) => w.prov))].sort();
  zProv.append(new Option('All provinces', ''), ...provinces.map((p) => new Option(p, p)));
  function fillZMuni() {
    const list = Object.entries(F.munis).filter(([, m]) => !zProv.value || m.prov === zProv.value).sort((a, b) => a[1].name.localeCompare(b[1].name));
    zMuni.replaceChildren(new Option('Zoom to municipality…', ''), ...list.map(([k, m]) => new Option(m.name, k)));
  }
  fillZMuni();
  function zoomTo(filterFn) {
    const ls = Object.values(layerById).filter((l) => byId[l.feature.properties.WardID] && filterFn(byId[l.feature.properties.WardID]));
    if (ls.length) map.fitBounds(L.featureGroup(ls).getBounds(), { padding: [20, 20] });
  }
  zProv.addEventListener('change', () => { fillZMuni(); zoomTo((w) => !zProv.value || w.prov === zProv.value); });
  zMuni.addEventListener('change', () => { if (zMuni.value) zoomTo((w) => w.m === zMuni.value); });

  // ---------- tables ----------
  const st = document.querySelector('#share-table tbody');
  for (const r of F.national) {
    const tr = el('tr');
    tr.append(el('td', {}, partyTag(r.party)));
    tr.append(el('td', { className: 'n' }, r.share.toFixed(1)));
    tr.append(el('td', { className: 'n' }, r.poll == null ? '—' : `${r.poll.toFixed(1)} ±${r.poll_sd.toFixed(1)}`));
    for (const v of [r.lge21, r.npe24]) tr.append(el('td', { className: 'n' }, v == null ? '—' : v.toFixed(1)));
    tr.append(el('td', { className: 'n' }, fmt(r.fav)));
    tr.addEventListener('click', () => { mode = 'share'; shareParty = r.party; sharePick.value = r.party; sharePick.hidden = false;
      document.querySelectorAll('.seg button').forEach((x) => x.setAttribute('aria-selected', String(x.dataset.mode === 'share'))); restyle();
      document.getElementById('map-section').scrollIntoView({ behavior: 'smooth' }); });
    st.append(tr);
  }
  const mt = document.querySelector('#metro-table tbody');
  for (const k of METROS) {
    const m = F.munis[k]; if (!m) continue;
    const tr = el('tr');
    tr.append(el('td', {}, m.name), el('td', {}, partyTag(m.largest)), el('td', { className: 'n' }, pct(m.pl)),
      el('td', { className: 'n' }, pct(m.hung)));
    for (const p of ['ANC', 'DA', 'MK', 'EFF']) tr.append(el('td', { className: 'n' }, Math.round(m.st[P.indexOf(p)])));
    tr.append(el('td', { className: 'n' }, String(m.seats)));
    tr.addEventListener('click', () => { zoomTo((w) => w.m === k); document.getElementById('map-section').scrollIntoView({ behavior: 'smooth' }); });
    mt.append(tr);
  }

  const bt2 = document.getElementById('bloc-table');
  const blocNames = Object.keys(F.blocs);
  const blocLabel = (b) => F.blocs[b].map(pname).join(' + ');
  bt2.querySelector('thead tr').append(...blocNames.map((b) => el('th', { className: 'n' }, blocLabel(b))));
  for (const k of METROS) {
    const m = F.munis[k]; if (!m) continue;
    const tr = el('tr', {}, el('td', {}, m.name), ...blocNames.map((b) => el('td', { className: 'n' }, pct(m.bl[b]))));
    tr.addEventListener('click', () => { zoomTo((w) => w.m === k); document.getElementById('map-section').scrollIntoView({ behavior: 'smooth' }); });
    bt2.querySelector('tbody').append(tr);
  }

  function sortable(table, rows, state, draw) {
    table.querySelectorAll('th button').forEach((b) => b.addEventListener('click', () => {
      if (state.k === b.dataset.k) state.dir *= -1; else { state.k = b.dataset.k; state.dir = 1; }
      draw();
    }));
  }
  const cmp = (k, dir) => (a, b) => { const x = a[k] ?? '', y = b[k] ?? ''; return (x < y ? -1 : x > y ? 1 : 0) * dir; };
  const ariaSort = (table, s) => table.querySelectorAll('th').forEach((th) => {
    const b = th.querySelector('button');
    th.setAttribute('aria-sort', b && b.dataset.k === s.k ? (s.dir > 0 ? 'ascending' : 'descending') : 'none');
  });

  const fProv = document.getElementById('f-prov'), fMuni = document.getElementById('f-muni'), fRate = document.getElementById('f-rate'), fQ = document.getElementById('f-q');
  fProv.append(new Option('All provinces', ''), ...provinces.map((p) => new Option(p, p)));
  fRate.append(new Option('All ratings', ''), ...['Toss-up', 'Lean', 'Likely', 'Safe'].map((r) => new Option(r, r)));
  function fillFMuni() {
    const list = Object.entries(F.munis).filter(([, m]) => !fProv.value || m.prov === fProv.value).sort((a, b) => a[1].name.localeCompare(b[1].name));
    fMuni.replaceChildren(new Option('All municipalities', ''), ...list.map(([k, m]) => new Option(m.name, k)));
  }
  fillFMuni();
  const ws = { k: 'p', dir: 1 };
  const wt = document.getElementById('ward-table');
  const MAX = 500;
  function drawWards() {
    const q = fQ.value.trim().toLowerCase();
    let rows = wardRows.filter((w) => (!fProv.value || w.prov === fProv.value) && (!fMuni.value || w.m === fMuni.value) && (!fRate.value || w.r === fRate.value)
      && (!q || [w.muni, w.prov, pname(w.f), pname(w.u), pname(w.w21)].join(' ').toLowerCase().includes(q)));
    rows = rows.sort(cmp(ws.k, ws.dir));
    ariaSort(wt, ws);
    const tb = wt.querySelector('tbody');
    tb.replaceChildren(...rows.slice(0, MAX).map((w) => {
      const tr = el('tr', {},
        el('td', {}, w.muni), el('td', { className: 'n' }, String(w.n)), el('td', {}, partyTag(w.f)),
        el('td', { className: 'n' }, pct(w.p)), el('td', {}, el('span', { className: 'rate ' + w.r }, w.r)),
        el('td', { className: 'wide' }, partyTag(w.u)), el('td', { className: 'n wide' }, w.g.toFixed(1)),
        el('td', { className: 'wide' }, partyTag(w.w21)));
      tr.addEventListener('click', () => { select(w.id, true); document.getElementById('map-section').scrollIntoView({ behavior: 'smooth' }); });
      return tr;
    }));
    document.getElementById('ward-count').textContent = rows.length > MAX
      ? `Showing ${fmt(MAX)} of ${fmt(rows.length)} wards. Choose a municipality or search to narrow the list.`
      : `${fmt(rows.length)} wards`;
  }
  fProv.addEventListener('change', () => { fillFMuni(); drawWards(); });
  [fMuni, fRate].forEach((s) => s.addEventListener('change', drawWards));
  fQ.addEventListener('input', drawWards);
  sortable(wt, wardRows, ws, drawWards);
  drawWards();

  const muniRows = Object.entries(F.munis).map(([k, m]) => ({ k, ...m, ew0: m.ew[0], ew1: m.ew[1], ew2: m.ew[2] }));
  const ms = { k: 'wards', dir: -1 };
  const mtab = document.getElementById('muni-table');
  const mQ = document.getElementById('m-q');
  function drawMunis() {
    const q = mQ.value.trim().toLowerCase();
    const rows = muniRows.filter((m) => !q || (m.name + ' ' + m.prov + ' ' + m.k).toLowerCase().includes(q)).sort(cmp(ms.k, ms.dir));
    ariaSort(mtab, ms);
    mtab.querySelector('tbody').replaceChildren(...rows.map((m) => {
      const tr = el('tr', {},
        el('td', {}, m.name), el('td', { className: 'wide' }, m.prov), el('td', { className: 'n' }, String(m.wards)),
        el('td', {}, partyTag(m.largest)), el('td', { className: 'n' }, pct(m.pl)),
        el('td', {}, m.maj ? partyTag(m.maj) : 'None likely'),
        el('td', { className: 'n' }, pct(m.hung)),
        el('td', { className: 'n wide' }, m.ew0.toFixed(0)), el('td', { className: 'n wide' }, m.ew1.toFixed(0)), el('td', { className: 'n wide' }, m.ew2.toFixed(0)));
      tr.addEventListener('click', () => { zoomTo((w) => w.m === m.k); document.getElementById('map-section').scrollIntoView({ behavior: 'smooth' }); });
      return tr;
    }));
  }
  mQ.addEventListener('input', drawMunis);
  sortable(mtab, muniRows, ms, drawMunis);
  drawMunis();

  // ---------- backtest ----------
  const lo = 0.85, hi = 0.96;
  const btBox = document.getElementById('bt');
  for (const year of ['2016', '2021']) {
    const b = F.backtest[year];
    if (!b) continue;
    const rows = [
      ['Carry forward the previous local winner', b.naive_prev_lge, false],
      ['Carry forward the last national-ballot winner', b.naive_npe, false],
      ['This model', b.model, true],
      ['This model with by-elections', b.model_byelections, true],
    ];
    btBox.append(el('h3', {}, `${year} (${fmt(b.wards)} wards)`), ...rows.map(([label, v, model]) =>
      el('div', { className: 'btrow' + (model ? ' model' : '') },
        el('div', { className: 'lab' }, el('span', {}, label), el('span', {}, (v * 100).toFixed(1) + '%')),
        el('div', { className: 'track' }, el('div', { className: 'fill', style: `width:${Math.max(2, (v - lo) / (hi - lo) * 100)}%` })))));
  }
  btBox.append(el('p', { className: 'note' }, 'Bars start at 85%. In both years the model was called with the actual national result standing in for perfect polls; real poll error is added in the forecast simulations.'));
})().catch((err) => {
  const lede = document.getElementById('lede');
  if (lede) lede.textContent = 'The forecast data could not load. Refresh the page to try again.';
  console.error(err);
});
