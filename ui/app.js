/**
 * app.js  —  Discovery Engine BI Dashboard v3.0
 * All data comes from PostgreSQL via the Python API server.
 * No mock data. No static JSON.
 *
 * Modules:
 *   API             — fetch helpers for all endpoints
 *   State           — shared live data
 *   TabManager      — tab switching + hash sync
 *   KPIStrip        — live KPI chips + click-to-open drawer
 *   KPIDrawer       — right-side detail drawer
 *   LiveData        — live-data table (paginated API, sort, filter, search)
 *   Charts          — standard Chart.js charts (sentiment, blocker, sources)
 *   ChartBuilder    — custom chart builder (CRUD, dynamic data)
 *   DrillDownMatrix — 3-level cascading tree (static structure, live mentions)
 *   SurveyForm      — in-dashboard survey modal → PostgreSQL
 *   OpenTracker     — live Open Data Tracker table
 *   Tooltip         — hover tooltip engine
 */

'use strict';

/* ════════════════════════════════════════════════════════════════════════════
   API  —  Fetch helpers
   ════════════════════════════════════════════════════════════════════════════ */
const API = {
  BASE: '',

  async get(path) {
    const res = await fetch(this.BASE + path);
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  },

  async post(path, body = {}) {
    const res = await fetch(this.BASE + path, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const json = await res.json().catch(() => ({ error: `POST ${path} failed` }));
    if (!res.ok && !json.error) json.error = `Server error ${res.status}`;
    return json;
  },

  async del(path) {
    const res = await fetch(this.BASE + path, { method: 'DELETE' });
    return res.json();
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   STATE  —  shared live data (set once, read everywhere)
   ════════════════════════════════════════════════════════════════════════════ */
const State = {
  kpis:     null,
  insights: null,
  sources:  [],
  intents:  ['complaint','observation','suggestion','praise','question'],
  categories: ['groceries','snacks','beverages','personal_care','baby_products',
               'pet_supplies','household','packaged_food','dairy','cleaning'],
};

/* ════════════════════════════════════════════════════════════════════════════
   TAB MANAGER
   ════════════════════════════════════════════════════════════════════════════ */
const TabManager = {
  tabs: ['scraping','insights','matrix','research','aisearch'],
  active: 'scraping',

  init() {
    this.tabs.forEach(id => {
      document.getElementById(`tab-btn-${id}`)
        ?.addEventListener('click', () => this.switchTo(id));
    });
    const hash = location.hash.replace('#','');
    if (this.tabs.includes(hash)) this.switchTo(hash, true);
  },

  switchTo(tabId, skipLazy = false) {
    if (this.active === tabId && !skipLazy) return;

    this.tabs.forEach(t => {
      document.getElementById(`tab-btn-${t}`)?.classList.remove('active');
      document.getElementById(`tab-btn-${t}`)?.setAttribute('aria-selected','false');
      document.getElementById(`tab-${t}`)?.classList.remove('active');
    });

    document.getElementById(`tab-btn-${tabId}`)?.classList.add('active');
    document.getElementById(`tab-btn-${tabId}`)?.setAttribute('aria-selected','true');
    document.getElementById(`tab-${tabId}`)?.classList.add('active');

    this.active = tabId;
    history.replaceState(null, '', `#${tabId}`);

    if (tabId === 'insights' && !Charts.initialized)
      Charts.init(State.insights);
    if (tabId === 'matrix'   && !DrillDownMatrix.initialized)
      DrillDownMatrix.init();
    if (tabId === 'research' && !OpenTracker.initialized)
      OpenTracker.init();
    if (tabId === 'aisearch' && !AISearch.initialized)
      AISearch.init();
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   KPI STRIP  —  live chips from /api/kpis
   ════════════════════════════════════════════════════════════════════════════ */
const KPIStrip = {
  async load() {
    try {
      const kpis = await API.get('/api/kpis');
      State.kpis = kpis;
      this.render(kpis);
      this._updateBadges(kpis);
      // Update last-updated
      const lu = document.getElementById('lastUpdated');
      if (lu && kpis.last_updated) {
        const d = new Date(kpis.last_updated);
        lu.textContent = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
      }
    } catch (e) {
      console.error('KPI load failed:', e);
      document.getElementById('kpiStrip').innerHTML =
        '<span style="font-size:11px;color:var(--negative)">DB offline — run: python scripts/api_server.py</span>';
    }
  },

  render(kpis) {
    const strip = document.getElementById('kpiStrip');
    if (!strip) return;

    const items = [
      { k: 'reviews',   v: Number(kpis.ai_analyzed).toLocaleString('en-IN'),  l: 'AI Reviews',    drawer: 'reviews'  },
      { k: 'themes',    v: kpis.themes,                                        l: 'Themes',        drawer: 'themes'   },
      { k: 'insights',  v: kpis.key_insights,                                  l: 'Key Insights',  drawer: 'insights' },
      { k: 'cats',      v: kpis.categories,                                    l: 'Categories',    drawer: 'cats'     },
      { k: 'sources',   v: kpis.data_sources,                                  l: 'Data Sources',  drawer: 'sources'  },
      { k: 'survey',    v: kpis.survey_responses,                              l: 'Respondents',   drawer: 'survey'   },
      { k: 'freq',      v: kpis.scrape_frequency,                              l: 'Sync Freq',     drawer: 'scrape'   },
    ];

    strip.innerHTML = items.map((item, i) => `
      <div class="kpi-chip" tabindex="0" role="button"
           aria-label="${item.l}: ${item.v} — click for details"
           onclick="KPIDrawer.open('${item.drawer}')"
           onkeydown="if(event.key==='Enter')KPIDrawer.open('${item.drawer}')"
           style="animation-delay:${i * 0.06}s"
           onmouseenter="Tooltip.show(event,'<b>${item.l}</b><br>Click to see detailed breakdown')"
           onmouseleave="Tooltip.hide()">
        <span class="kv">${item.v}</span>
        <span class="kl">${item.l}</span>
      </div>`).join('');
  },

  _updateBadges(kpis) {
    const b = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    b('badge-scraping', Number(kpis.ai_analyzed).toLocaleString('en-IN'));
    b('badge-insights', kpis.key_insights);
    b('badge-matrix',   kpis.categories);
    b('badge-research', kpis.survey_responses);
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   KPI DRAWER  —  right-side detail panel (slides in on chip click)
   ════════════════════════════════════════════════════════════════════════════ */
const KPIDrawer = {
  _chart: null,

  async open(type) {
    const drawer  = document.getElementById('kpiDrawer');
    const overlay = document.getElementById('drawerOverlay');
    const title   = document.getElementById('drawerTitle');
    const body    = document.getElementById('drawerBody');

    body.innerHTML = '<div class="table-loading"><div class="loading-spinner"></div><div>Loading…</div></div>';
    drawer.classList.add('open');
    overlay.classList.add('open');

    if (this._chart) { this._chart.destroy(); this._chart = null; }

    try {
      switch (type) {
        case 'reviews':  await this._reviews(title, body);  break;
        case 'themes':   await this._themes(title, body);   break;
        case 'insights': await this._insights(title, body); break;
        case 'cats':     await this._categories(title, body); break;
        case 'sources':  await this._sources(title, body);  break;
        case 'survey':   await this._survey(title, body);   break;
        case 'scrape':   await this._scrapeInfo(title, body); break;
      }
    } catch (e) {
      body.innerHTML = `<p style="color:var(--negative)">Error: ${e.message}</p>`;
    }
  },

  close() {
    document.getElementById('kpiDrawer')?.classList.remove('open');
    document.getElementById('drawerOverlay')?.classList.remove('open');
    if (this._chart) { this._chart.destroy(); this._chart = null; }
  },

  async _reviews(title, body) {
    title.textContent = '📊 Reviews Breakdown';
    const data = await API.get('/api/charts/data?x=intent&y=count');
    const kpis = State.kpis || {};
    body.innerHTML = `
      <div class="drawer-stat-row">
        <div class="drawer-stat"><span class="ds-val">${Number(kpis.ai_analyzed||0).toLocaleString('en-IN')}</span><div class="ds-lbl">Total Reviews</div></div>
        <div class="drawer-stat"><span class="ds-val">${kpis.data_sources||0}</span><div class="ds-lbl">Sources</div></div>
      </div>
      <h3 style="font-size:12px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.07em">By Intent</h3>
      <div class="drawer-bar-row">${this._bars(data.labels, data.values)}</div>
      <div class="drawer-canvas-wrap" style="height:180px"><canvas id="drawerCanvas"></canvas></div>`;
    this._makeChart('drawerCanvas', 'doughnut', data.labels, data.values);
  },

  async _themes(title, body) {
    title.textContent = '🎯 Discovery Themes';
    const d = State.insights;
    if (!d) { body.innerHTML = '<p style="color:var(--text-muted)">AI insights not loaded.</p>'; return; }
    body.innerHTML = `
      <div class="drawer-stat-row">
        <div class="drawer-stat"><span class="ds-val">${d.themes.length}</span><div class="ds-lbl">Themes</div></div>
        <div class="drawer-stat"><span class="ds-val">${d.themes.reduce((s,t)=>s+t.mentions,0)}</span><div class="ds-lbl">Total Mentions</div></div>
      </div>
      <div class="drawer-list">
        ${d.themes.map(t => `
          <div class="drawer-list-item">
            <span class="dl-label">${t.name}</span>
            <span class="badge badge-${t.frequency.toLowerCase()}">${t.frequency}</span>
            <span class="dl-val">${t.mentions}</span>
          </div>`).join('')}
      </div>`;
  },

  async _insights(title, body) {
    title.textContent = '💡 Key Insights';
    const d = State.insights;
    if (!d) { body.innerHTML = '<p style="color:var(--text-muted)">AI insights not loaded.</p>'; return; }
    body.innerHTML = d.insights.map(i => `
      <div class="rcard" style="margin-bottom:12px">
        <div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:8px">${i.title}</div>
        <div style="font-size:12px;color:var(--text-secondary);line-height:1.65">${i.observation}</div>
        ${i.opportunity ? `<div class="rcard-rec" style="margin-top:10px">${i.opportunity}</div>` : ''}
      </div>`).join('');
  },

  async _categories(title, body) {
    title.textContent = '📁 Category Summary';
    const data = await API.get('/api/charts/data?x=category&y=count');
    body.innerHTML = `
      <div class="drawer-bar-row">${this._bars(data.labels, data.values)}</div>
      <div class="drawer-canvas-wrap" style="height:200px"><canvas id="drawerCanvas"></canvas></div>`;
    this._makeChart('drawerCanvas', 'bar', data.labels, data.values, true);
  },

  async _sources(title, body) {
    title.textContent = '🔌 Data Sources';
    const data = await API.get('/api/charts/data?x=source&y=count');
    const kpis = State.kpis || {};
    body.innerHTML = `
      <div class="drawer-stat-row">
        <div class="drawer-stat"><span class="ds-val">${kpis.data_sources||0}</span><div class="ds-lbl">Active Sources</div></div>
        <div class="drawer-stat"><span class="ds-val">${kpis.scrape_frequency||'—'}</span><div class="ds-lbl">Sync Mode</div></div>
      </div>
      <div class="drawer-bar-row">${this._bars(data.labels, data.values)}</div>`;
  },

  async _survey(title, body) {
    title.textContent = '🔬 Survey Respondents';
    const d = await API.get('/api/survey/responses?limit=5');
    body.innerHTML = `
      <div class="drawer-stat-row">
        <div class="drawer-stat"><span class="ds-val">${d.total}</span><div class="ds-lbl">Total Responses</div></div>
        <div class="drawer-stat"><span class="ds-val">${d.responses.length ? Math.round(d.responses.reduce((s,r)=>s+r.quality_score,0)/d.responses.length) : 0}%</span><div class="ds-lbl">Avg Quality Score</div></div>
      </div>
      ${d.total === 0 ? '<p style="color:var(--text-muted);font-size:12px;text-align:center;padding:20px">No responses yet. Add one via "New Respondent".</p>' :
        '<div class="drawer-list">' +
        d.responses.map(r => `
          <div class="drawer-list-item">
            <span class="dl-label">${r.respondent_name} <span style="color:var(--text-muted);font-size:10px">· ${r.city}</span></span>
            <span class="score-badge ${r.quality_score>=80?'score-hi':r.quality_score>=60?'score-md':'score-lo'}">${r.quality_score}</span>
          </div>`).join('') +
        '</div>'}
      <button class="btn-primary" style="width:100%;justify-content:center" onclick="KPIDrawer.close();SurveyForm.open()">Add New Respondent</button>`;
  },

  async _scrapeInfo(title, body) {
    title.textContent = '⏱ Scrape Status';
    const st = await API.get('/api/scrape/status');
    const kpis = State.kpis || {};
    body.innerHTML = `
      <div class="drawer-stat-row">
        <div class="drawer-stat"><span class="ds-val">${st.running?'Running':'Idle'}</span><div class="ds-lbl">Status</div></div>
        <div class="drawer-stat"><span class="ds-val">${st.added||0}</span><div class="ds-lbl">Last Added</div></div>
      </div>
      <div class="drawer-list">
        <div class="drawer-list-item"><span class="dl-label">Total in DB</span><span class="dl-val">${Number(kpis.ai_analyzed||0).toLocaleString()}</span></div>
        <div class="drawer-list-item"><span class="dl-label">Last Scrape</span><span class="dl-val">${st.finished_at ? new Date(st.finished_at).toLocaleString('en-IN') : 'Never'}</span></div>
        <div class="drawer-list-item"><span class="dl-label">Error</span><span class="dl-val" style="color:${st.error?'var(--negative)':'var(--positive)'}">${st.error||'None'}</span></div>
      </div>
      <button class="btn-primary" style="width:100%;justify-content:center;margin-top:4px" onclick="KPIDrawer.close();LiveData.scrape()">
        Run Scrape Now
      </button>`;
  },

  _bars(labels, values) {
    const max = Math.max(...values, 1);
    return labels.slice(0,10).map((l, i) => `
      <div class="dbar-item">
        <div class="dbar-label">${l}</div>
        <div class="dbar-track"><div class="dbar-fill" style="width:${Math.round(values[i]/max*100)}%"></div></div>
        <div class="dbar-count">${values[i]}</div>
      </div>`).join('');
  },

  _makeChart(canvasId, type, labels, values, horizontal = false) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const palette = ['#f97316','#a78bfa','#22d3ee','#10b981','#ec4899','#f59e0b','#3b82f6','#14b8a6'];
    const cfg = type === 'doughnut' || type === 'pie'
      ? { type, data: { labels, datasets: [{ data: values, backgroundColor: palette, borderWidth:2, borderColor: '#111422', hoverOffset:8 }] },
          options: { plugins: { legend: { display: false } }, animation: { duration: 600 } } }
      : { type, data: { labels, datasets: [{ data: values,
              backgroundColor: palette.map(c=>c+'22'), borderColor: palette, borderWidth:1.5, borderRadius:4 }] },
          options: { indexAxis: horizontal ? 'y' : 'x',
            plugins: { legend: { display: false } },
            scales: { x: { grid:{color:'rgba(255,255,255,0.03)'}, ticks:{color:'#475569',font:{size:10}} },
                      y: { grid:{color:'rgba(255,255,255,0.03)'}, ticks:{color:'#475569',font:{size:10}} } },
            animation: { duration: 600 } } };
    this._chart = new Chart(ctx, cfg);
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   LIVE DATA  —  paginated table from /api/records
   ════════════════════════════════════════════════════════════════════════════ */
const LiveData = {
  PAGE_SIZE: 50,
  _page:    0,
  _total:   0,
  _sortCol: 'date',
  _sortDir: 'desc',
  _scrapeTimer: null,

  init() {
    this._populateFilters();
    this._bindEvents();
    this._load();
  },

  _populateFilters() {
    const addOpts = (id, vals) => {
      const el = document.getElementById(id); if (!el) return;
      vals.forEach(v => { const o = document.createElement('option'); o.value=v; o.textContent=v.replace(/_/g,' '); el.appendChild(o); });
    };
    addOpts('filterIntent',   State.intents);
    addOpts('filterCategory', State.categories);
    // Sources will be populated after first API call
  },

  _bindEvents() {
    ['filterSource','filterIntent','filterCategory'].forEach(id =>
      document.getElementById(id)?.addEventListener('change', () => { this._page=0; this._load(); }));

    let debounce;
    document.getElementById('searchInput')?.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this._page=0; this._load(); }, 300);
    });

    document.querySelectorAll('.vt-head-row .vt-cell.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        this._sortDir = this._sortCol === col && this._sortDir === 'desc' ? 'asc' : 'desc';
        this._sortCol = col;
        document.querySelectorAll('.vt-head-row .vt-cell.sortable').forEach(c => {
          c.classList.toggle('sort-active', c.dataset.col === col);
          const arr = c.querySelector('.sort-arrow');
          if (arr) arr.textContent = c.dataset.col === col ? (this._sortDir==='asc'?'↑':'↓') : '↕';
        });
        this._page = 0; this._load();
      });
    });
  },

  _params() {
    const qs = new URLSearchParams({
      offset:   this._page * this.PAGE_SIZE,
      limit:    this.PAGE_SIZE,
      sort:     this._sortCol,
      dir:      this._sortDir,
    });
    const s = document.getElementById('filterSource')?.value;
    const i = document.getElementById('filterIntent')?.value;
    const c = document.getElementById('filterCategory')?.value;
    const q = document.getElementById('searchInput')?.value;
    if (s) qs.set('source',   s);
    if (i) qs.set('intent',   i);
    if (c) qs.set('category', c);
    if (q) qs.set('search',   q);
    return qs.toString();
  },

  async _load() {
    try {
      const data  = await API.get(`/api/records?${this._params()}`);
      this._total = data.total;
      this._renderTable(data.records);
      this._renderPagination(data.offset, data.total);
      this._populateSourceFilter(data.records);
    } catch (e) {
      document.getElementById('vtRows').innerHTML =
        `<div class="table-loading"><p style="color:var(--negative)">Failed: ${e.message}</p></div>`;
    }
  },

  _populateSourceFilter(records) {
    const el = document.getElementById('filterSource');
    if (!el || el.options.length > 1) return;
    const seen = new Set();
    records.forEach(r => { if (r.source && !seen.has(r.source)) { seen.add(r.source); const o=document.createElement('option'); o.value=r.source; o.textContent=r.source; el.appendChild(o); }});
    // Load all sources from DB once
    API.get('/api/charts/data?x=source&y=count').then(d => {
      d.labels.forEach(src => {
        if (!seen.has(src)) {
          seen.add(src);
          const o=document.createElement('option'); o.value=src; o.textContent=src; el.appendChild(o);
        }
      });
    }).catch(()=>{});
  },

  _renderTable(records) {
    const rows = document.getElementById('vtRows');
    if (!rows) return;
    if (!records.length) {
      rows.innerHTML = '<div class="table-loading"><p style="color:var(--text-muted)">No records match the current filters.</p></div>';
      return;
    }
    const BADGE = { complaint:'badge-complaint', observation:'badge-observation', suggestion:'badge-suggestion', praise:'badge-praise', question:'badge-question' };
    rows.innerHTML = records.map((r, i) => {
      const stars   = '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating);
      const cats    = (r.categories||[]).map(c=>`<span class="cat-tag">${c.replace(/_/g,' ')}</span>`).join('');
      const snippet = r.text.length > 130 ? r.text.slice(0,130) + '…' : r.text;
      const tooltip = r.text.replace(/"/g,'&quot;').slice(0,280);
      return `<div class="vt-data-row ${i%2===0?'even':''}"
        onmouseenter="Tooltip.show(event,'<b>${r.id}</b><br><span style=color:var(--text-muted)>${r.source} · ${r.date}</span><br><br>${tooltip}')"
        onmouseleave="Tooltip.hide()">
        <div class="vt-cell vt-cell-id">${r.id}</div>
        <div class="vt-cell vt-cell-source">${r.source}</div>
        <div class="vt-cell vt-cell-date">${r.date}</div>
        <div class="vt-cell vt-cell-user">${r.user||'–'}</div>
        <div class="vt-cell vt-cell-location">${r.location}</div>
        <div class="vt-cell vt-cell-intent"><span class="badge ${BADGE[r.intent]||''}">${r.intent}</span></div>
        <div class="vt-cell vt-cell-categories">${cats}</div>
        <div class="vt-cell vt-cell-rating"><span class="stars">${stars}</span></div>
        <div class="vt-cell vt-cell-text">${snippet}</div>
      </div>`;
    }).join('');
  },

  _renderPagination(offset, total) {
    const page  = this._page;
    const pages = Math.ceil(total / this.PAGE_SIZE);
    const start = offset + 1;
    const end   = Math.min(offset + this.PAGE_SIZE, total);
    const cnt   = document.getElementById('recordCount');
    const info  = document.getElementById('vtInfo');
    const num   = document.getElementById('pgNum');
    const prev  = document.getElementById('pgPrev');
    const next  = document.getElementById('pgNext');
    if (cnt)  cnt.textContent  = `${total.toLocaleString('en-IN')} records`;
    if (info) info.textContent = total ? `Showing ${start}–${end} of ${total.toLocaleString('en-IN')} records` : 'No records';
    if (num)  num.textContent  = `Page ${page+1} of ${Math.max(pages,1)}`;
    if (prev) prev.disabled    = page === 0;
    if (next) next.disabled    = end >= total;
  },

  prevPage() { if (this._page > 0) { this._page--; this._load(); } },
  nextPage() { if ((this._page+1)*this.PAGE_SIZE < this._total) { this._page++; this._load(); } },

  // ── Scrape ─────────────────────────────────────────────────────────────────
  async scrape() {
    const btn   = document.getElementById('scrapeNowBtn');
    const lbl   = document.getElementById('scrapeLabel');
    const icon  = document.getElementById('scrapeIcon');
    const prog  = document.getElementById('scrapeProgress');
    const fill  = document.getElementById('progressFill');
    const text  = document.getElementById('progressText');

    if (btn?.disabled) return;
    if (btn) btn.disabled = true;
    if (lbl) lbl.textContent = 'Scraping…';
    if (icon) icon.classList.add('spin');
    if (prog) prog.hidden = false;
    if (fill) fill.style.width = '15%';
    if (text) text.textContent = 'Connecting to sources…';

    try {
      await API.post('/api/scrape');
      // Poll status
      let dots = 0;
      const spinners = ['|','/','-','\\'];
      this._scrapeTimer = setInterval(async () => {
        try {
          const st = await API.get('/api/scrape/status');
          dots++;
          if (fill) fill.style.width = st.running ? `${Math.min(15 + dots * 8, 85)}%` : '100%';
          if (text) text.textContent = st.running
            ? `Scraping ${spinners[dots%4]} Collecting from sources…`
            : st.error
              ? `Error: ${st.error}`
              : `Done — ${st.added} records added`;

          if (!st.running) {
            clearInterval(this._scrapeTimer);
            setTimeout(() => {
              if (prog) prog.hidden = true;
              if (fill) fill.style.width = '0%';
            }, 2500);
            // Refresh
            await KPIStrip.load();
            this._page = 0; this._load();
            Tooltip.flash(`✓ Scrape complete — ${st.added} records added`);
            if (btn)  btn.disabled = false;
            if (lbl)  lbl.textContent = 'Scrape Now';
            if (icon) icon.classList.remove('spin');
          }
        } catch (_) {}
      }, 1200);
    } catch (e) {
      if (prog) prog.hidden = true;
      if (btn)  btn.disabled = false;
      if (lbl)  lbl.textContent = 'Scrape Now';
      if (icon) icon.classList.remove('spin');
      Tooltip.flash(`⚠ Scrape failed: ${e.message}`);
    }
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   CHARTS  —  Standard AI Insights charts (lazy on tab switch)
   ════════════════════════════════════════════════════════════════════════════ */
const Charts = {
  initialized: false,
  _charts: {},

  async init(insightsData) {
    this.initialized = true;
    const d = insightsData || State.insights;
    if (d) {
      this._sentimentDonut(d.sentiment);
      this._blockerBar(d.themes);
      this._insightCards(d.insights);
      this._blockersTable(d.themes);
    }
    // Always pull live source chart from DB
    await this._sourceChart();
    // Load saved custom charts
    await ChartBuilder.loadSaved();
  },

  _mkChart(id, cfg) {
    const ctx = document.getElementById(id); if (!ctx) return;
    if (this._charts[id]) this._charts[id].destroy();
    this._charts[id] = new Chart(ctx, cfg);
  },

  _sentimentDonut(s) {
    if (!s) return;
    const { positive: pos, neutral: neu, negative: neg } = s;
    this._mkChart('sentimentChart', {
      type: 'doughnut',
      data: {
        labels: ['Positive','Neutral','Negative'],
        datasets: [{ data: [pos.count, neu.count, neg.count],
          backgroundColor: ['rgba(16,185,129,0.8)','rgba(245,158,11,0.8)','rgba(239,68,68,0.8)'],
          borderColor: ['#10b981','#f59e0b','#ef4444'], borderWidth:2, hoverOffset:10 }]
      },
      options: {
        cutout: '72%',
        plugins: { legend: { display:false },
          tooltip: { backgroundColor:'#1f2338', borderColor:'#2e3450', borderWidth:1,
            titleColor:'#e2e8f0', bodyColor:'#94a3b8', padding:12 } },
        animation: { duration:900, easing:'easeOutQuart' }
      }
    });
    const center = document.getElementById('sentimentCenter');
    if (center) center.innerHTML = `
      <div style="font-size:22px;font-weight:800;color:#ef4444;line-height:1">${neg.percentage}%</div>
      <div style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:.08em;margin-top:3px">Negative</div>`;
    const legend = document.getElementById('sentimentLegend');
    if (legend) legend.innerHTML = [
      { label:'Positive', count:pos.count, pct:pos.percentage, color:'#10b981' },
      { label:'Neutral',  count:neu.count, pct:neu.percentage, color:'#f59e0b' },
      { label:'Negative', count:neg.count, pct:neg.percentage, color:'#ef4444' },
    ].map(i => `
      <div class="legend-item">
        <span class="legend-dot" style="background:${i.color}"></span>
        <span class="legend-label">${i.label}</span>
        <span class="legend-val" style="color:${i.color}">${i.count} <span style="color:#475569;font-weight:400;font-size:10px">(${i.pct}%)</span></span>
      </div>`).join('');
  },

  _blockerBar(themes) {
    if (!themes) return;
    const sorted  = [...themes].sort((a,b)=>b.mentions-a.mentions);
    const labels  = sorted.map(t=>t.name);
    const values  = sorted.map(t=>t.mentions);
    const palette = ['#f97316','#a78bfa','#22d3ee','#10b981','#ec4899'];
    this._mkChart('blockerChart', {
      type:'bar', data:{ labels, datasets:[{
        label:'Mentions', data:values,
        backgroundColor: palette.map(c=>c+'22'), borderColor:palette, borderWidth:1.5, borderRadius:5,
      }]},
      options:{ indexAxis:'y', plugins:{ legend:{display:false},
        tooltip:{backgroundColor:'#1f2338',borderColor:'#2e3450',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}},
        scales:{x:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#475569',font:{size:11}}},
                y:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:11}}}},
        animation:{duration:750} }
    });
  },

  async _sourceChart() {
    try {
      const data = await API.get('/api/charts/data?x=source&y=count');
      const palette = ['#f97316','#a78bfa','#22d3ee','#10b981','#ec4899','#f59e0b','#3b82f6','#14b8a6'];
      this._mkChart('trendChart', {
        type:'bar', data:{ labels:data.labels, datasets:[{
          label:'Reviews', data:data.values,
          backgroundColor: data.labels.map((_,i)=>palette[i%palette.length]+'33'),
          borderColor:     data.labels.map((_,i)=>palette[i%palette.length]),
          borderWidth:1.5, borderRadius:5,
        }]},
        options:{ plugins:{ legend:{display:false},
          tooltip:{backgroundColor:'#1f2338',borderColor:'#2e3450',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}},
          scales:{x:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#475569',font:{size:10},maxRotation:35}},
                  y:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#475569',font:{size:11}}}},
          animation:{duration:800} }
      });
      // Update subtitle
      const sub = document.querySelector('#trendChartCard .chart-subtitle');
      if (sub) sub.textContent = `${data.labels.length} sources · ${data.values.reduce((s,v)=>s+v,0)} total reviews`;
    } catch (e) { console.warn('Source chart failed:', e); }
  },

  _insightCards(insights) {
    const grid = document.getElementById('insightsGrid');
    if (!grid || !insights) return;
    grid.innerHTML = insights.map((ins, idx) => `
      <div class="insight-card" id="ic-${idx}">
        <div class="insight-head" onclick="Charts.toggleInsight(${idx})" role="button" tabindex="0">
          <h3>${ins.title}</h3>
          <svg class="insight-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
        <div class="insight-body">
          ${[['OBSERVATION',ins.observation],['USER NEED',ins.user_need],['ROOT CAUSE',ins.root_cause],['OPPORTUNITY',ins.opportunity],['IMPLICATION',ins.implication]]
            .filter(([,v])=>v).map(([l,v])=>`
            <div class="insight-row">
              <span class="insight-row-label">${l}</span>
              <p>${v}</p>
            </div>`).join('')}
        </div>
      </div>`).join('');
  },

  toggleInsight(idx) { document.getElementById(`ic-${idx}`)?.classList.toggle('open'); },

  _blockersTable(themes) {
    const tbody = document.getElementById('blockersTableBody');
    if (!tbody || !themes) return;
    tbody.innerHTML = themes.map(t => `
      <tr>
        <td><strong style="color:var(--text-primary)">${t.name}</strong></td>
        <td><span class="badge badge-${t.frequency.toLowerCase()}">${t.frequency}</span></td>
        <td style="font-weight:700;color:var(--accent)">${t.mentions}</td>
        <td><div class="sentiment-mini">
          <span class="sm-pos">▲ ${t.sentiment.positive}</span>
          <span class="sm-neu">— ${t.sentiment.neutral}</span>
          <span class="sm-neg">▼ ${t.sentiment.negative}</span>
        </div></td>
        <td>${t.blockers.map(b=>`<div style="margin-bottom:4px;font-size:12px;color:var(--text-secondary)">• ${b}</div>`).join('')}</td>
        <td>${(t.triggers||[]).slice(0,2).map(tr=>`<span class="cat-tag" style="background:rgba(34,211,238,0.08);color:var(--cyan);border-color:rgba(34,211,238,0.2);display:inline-block;margin-bottom:4px">${tr}</span>`).join(' ')}</td>
      </tr>`).join('');
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   CHART BUILDER  —  custom charts, saved to PostgreSQL
   ════════════════════════════════════════════════════════════════════════════ */
const ChartBuilder = {
  _previewChart: null,
  _savedCharts:  {},   // id → Chart instance

  open() {
    document.getElementById('builderModal').hidden   = false;
    document.getElementById('builderOverlay').hidden = false;
    this._populateBuilderFilters();
    this.preview();
  },

  close() {
    document.getElementById('builderModal').hidden   = true;
    document.getElementById('builderOverlay').hidden = true;
    document.getElementById('cb-name').value = '';
    if (this._previewChart) { this._previewChart.destroy(); this._previewChart = null; }
  },

  _populateBuilderFilters() {
    const addOpts = (id, vals) => {
      const el = document.getElementById(id); if (!el || el.options.length > 1) return;
      vals.forEach(v => { const o=document.createElement('option'); o.value=v; o.textContent=v.replace(/_/g,' '); el.appendChild(o); });
    };
    addOpts('cb-filter-source', State.sources.length ? State.sources : []);
    addOpts('cb-filter-intent', State.intents);
    addOpts('cb-filter-cat',    State.categories);

    if (!State.sources.length) {
      API.get('/api/charts/data?x=source&y=count').then(d => {
        State.sources = d.labels;
        addOpts('cb-filter-source', d.labels);
      }).catch(()=>{});
    }
  },

  async preview() {
    const x      = document.getElementById('cb-x')?.value     || 'source';
    const y      = document.getElementById('cb-y')?.value     || 'count';
    const type   = document.getElementById('cb-type')?.value  || 'bar';
    const src    = document.getElementById('cb-filter-source')?.value || '';
    const intent = document.getElementById('cb-filter-intent')?.value || '';
    const cat    = document.getElementById('cb-filter-cat')?.value   || '';
    const from   = document.getElementById('cb-date-from')?.value    || '';
    const to     = document.getElementById('cb-date-to')?.value      || '';

    const params = new URLSearchParams({x,y});
    if (src)    params.set('source',    src);
    if (intent) params.set('intent',    intent);
    if (cat)    params.set('category',  cat);
    if (from)   params.set('date_from', from);
    if (to)     params.set('date_to',   to);

    try {
      const data = await API.get(`/api/charts/data?${params}`);
      const hint = document.getElementById('previewHint');
      if (hint) hint.textContent = `${data.labels.length} groups · ${data.values.reduce((s,v)=>s+v,0)} total`;

      const ctx = document.getElementById('builderPreviewCanvas');
      if (!ctx) return;
      if (this._previewChart) { this._previewChart.destroy(); this._previewChart = null; }

      const palette = ['#f97316','#a78bfa','#22d3ee','#10b981','#ec4899','#f59e0b','#3b82f6','#14b8a6'];
      const isRound = type === 'doughnut' || type === 'pie' || type === 'polarArea';
      const actualType = type === 'horizontalBar' ? 'bar' : type;
      const isHBar = type === 'horizontalBar';

      this._previewChart = new Chart(ctx, {
        type: actualType,
        data: { labels: data.labels, datasets: [{
          label: y.replace(/_/g,' '),
          data:  data.values,
          backgroundColor: isRound ? palette : palette.map(c=>c+'33'),
          borderColor:     isRound ? palette.map(()=>'#111422') : palette,
          borderWidth: 1.5,
          borderRadius: isRound ? 0 : 4,
          hoverOffset: isRound ? 8 : 0,
        }] },
        options: {
          indexAxis: isHBar ? 'y' : 'x',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false },
            tooltip: { backgroundColor:'#1f2338', borderColor:'#2e3450', borderWidth:1, titleColor:'#e2e8f0', bodyColor:'#94a3b8', padding:10 } },
          scales: isRound ? {} : {
            x: { grid:{color:'rgba(255,255,255,0.03)'}, ticks:{color:'#475569',font:{size:10},maxRotation:40} },
            y: { grid:{color:'rgba(255,255,255,0.03)'}, ticks:{color:'#475569',font:{size:10}} },
          },
          animation: { duration: 500 },
        },
      });
    } catch (e) {
      const hint = document.getElementById('previewHint');
      if (hint) hint.textContent = `Error: ${e.message}`;
    }
  },

  async save() {
    const name = document.getElementById('cb-name')?.value?.trim();
    if (!name) { alert('Please enter a chart name.'); return; }

    const body = {
      name,
      chart_type: document.getElementById('cb-type')?.value     || 'bar',
      x_axis:     document.getElementById('cb-x')?.value        || 'source',
      y_axis:     document.getElementById('cb-y')?.value        || 'count',
      filters: {
        source:    document.getElementById('cb-filter-source')?.value || '',
        intent:    document.getElementById('cb-filter-intent')?.value || '',
        category:  document.getElementById('cb-filter-cat')?.value   || '',
        date_from: document.getElementById('cb-date-from')?.value    || '',
        date_to:   document.getElementById('cb-date-to')?.value      || '',
      }
    };

    try {
      const btn = document.getElementById('saveChartBtn');
      if (btn) btn.disabled = true;
      await API.post('/api/charts/configs', body);
      this.close();
      await this.loadSaved();
      Tooltip.flash(`✓ Chart "${name}" saved`);
    } catch (e) {
      alert(`Save failed: ${e.message}`);
    } finally {
      const btn = document.getElementById('saveChartBtn');
      if (btn) btn.disabled = false;
    }
  },

  async loadSaved() {
    try {
      const configs = await API.get('/api/charts/configs');
      const grid    = document.getElementById('customChartsGrid');
      const noMsg   = document.getElementById('noChartsMsg');
      if (!grid) return;

      if (!configs.length) {
        if (noMsg) noMsg.style.display = 'flex';
        return;
      }
      if (noMsg) noMsg.style.display = 'none';

      // Destroy old instances
      Object.values(this._savedCharts).forEach(c => c.destroy());
      this._savedCharts = {};

      grid.innerHTML = configs.map(cfg => `
        <div class="custom-chart-card" id="cc-${cfg.id}">
          <div class="custom-chart-header">
            <div>
              <div class="custom-chart-title">${cfg.name}</div>
              <div class="custom-chart-meta">${cfg.chart_type} · ${cfg.x_axis} → ${cfg.y_axis}</div>
            </div>
            <button class="delete-chart-btn" onclick="ChartBuilder.deleteChart(${cfg.id},'${cfg.name.replace(/'/g,"\\\'")}')" title="Delete chart">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            </button>
          </div>
          <div style="position:relative;height:180px"><canvas id="cc-canvas-${cfg.id}"></canvas></div>
        </div>`).join('');

      // Render each saved chart
      for (const cfg of configs) {
        const params = new URLSearchParams({ x: cfg.x_axis, y: cfg.y_axis });
        const f = cfg.filters || {};
        if (f.source)    params.set('source',    f.source);
        if (f.intent)    params.set('intent',    f.intent);
        if (f.category)  params.set('category',  f.category);
        if (f.date_from) params.set('date_from', f.date_from);
        if (f.date_to)   params.set('date_to',   f.date_to);

        API.get(`/api/charts/data?${params}`).then(data => {
          const ctx = document.getElementById(`cc-canvas-${cfg.id}`);
          if (!ctx) return;
          const palette = ['#f97316','#a78bfa','#22d3ee','#10b981','#ec4899','#f59e0b'];
          const isRound = ['doughnut','pie','polarArea'].includes(cfg.chart_type);
          const actualType = cfg.chart_type === 'horizontalBar' ? 'bar' : cfg.chart_type;
          const isHBar  = cfg.chart_type === 'horizontalBar';
          this._savedCharts[cfg.id] = new Chart(ctx, {
            type: actualType,
            data: { labels: data.labels, datasets: [{
              data: data.values,
              backgroundColor: isRound ? palette : palette.map(c=>c+'33'),
              borderColor:     isRound ? palette.map(()=>'#111422') : palette,
              borderWidth:1.5, borderRadius: isRound?0:4, hoverOffset: isRound?8:0,
            }] },
            options: { indexAxis: isHBar?'y':'x', responsive:true, maintainAspectRatio:false,
              plugins:{ legend:{display:false} },
              scales: isRound ? {} : {
                x:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#475569',font:{size:9},maxRotation:40}},
                y:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#475569',font:{size:9}}},
              },
              animation:{duration:500} }
          });
        }).catch(()=>{});
      }
    } catch (e) { console.warn('loadSaved charts failed:', e); }
  },

  async deleteChart(id, name) {
    if (!confirm(`Delete chart "${name}"?`)) return;
    await API.del(`/api/charts/configs/${id}`);
    if (this._savedCharts[id]) { this._savedCharts[id].destroy(); delete this._savedCharts[id]; }
    await this.loadSaved();
    Tooltip.flash(`✓ Chart "${name}" deleted`);
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   DRILL-DOWN MATRIX  —  3-level tree (static structure from AI insights)
   ════════════════════════════════════════════════════════════════════════════ */
const DrillDownMatrix = {
  initialized: false,
  _expanded: new Set(),
  TREE: [],

  async init() {
    this.initialized = true;
    try {
      const data = await API.get('/api/matrix');
      if (data && data.categories && data.categories.length) {
        this.TREE = data.categories.map(cat => ({
          id: cat.id,
          name: cat.name,
          icon: this._getIcon(cat.id),
          mentions: cat.mentions,
          gap_severity: cat.gap_severity,
          business_impact: cat.business_impact,
          neg_pct: cat.neg_pct || 0,
          trend: 0,
          sentiment: cat.sentiment || { positive: 0, neutral: 0, negative: 0 },
          children: (cat.quotes || []).map((q, i) => ({
            id: `${cat.id}-quote-${i}`,
            name: `Evidence ${i + 1}`,
            mentions: 1,
            gap_severity: 'Low',
            business_impact: 'Low',
            neg_pct: 0,
            leaves: [
              { type: 'quote', text: q.text, source: q.source, sentiment: q.sentiment },
            ],
          })),
        }));
      }
    } catch (e) {
      console.warn('Matrix API failed, using empty tree:', e);
    }
    this._render();
  },

  _getIcon(id) {
    const icons = {
      groceries: '🥦', snacks: '🍿', beverages: '🥤', personal_care: '💆',
      baby_products: '🍼', pet_supplies: '🐾', household: '🏠', packaged_food: '🥫',
      dairy: '🥛', cleaning: '🧹', electronics: '📱', general: '📦',
    };
    return icons[id] || '📦';
  },

  _score(gap, impact, trend) {
    const g={High:40,Medium:25,Low:10,Critical:50}, i={High:40,Medium:25,Low:10};
    return Math.min(99, (g[gap]||0) + (i[impact]||0) + Math.abs(trend||0)*0.5);
  },
  _psClass(s) { return s>=80?'ps-critical':s>=60?'ps-high':s>=40?'ps-medium':'ps-low'; },
  _trend(t)   { return t>0?`<span class="trend-pill trend-up">▲ +${t}%</span>`:t<0?`<span class="trend-pill trend-down">▼ ${t}%</span>`:`<span class="trend-pill trend-flat">→ Flat</span>`; },
  _gap(g, pct) {
    const M={High:'badge-high',Medium:'badge-medium',Low:'badge-low',Critical:'badge-critical'};
    const pctStr = (pct !== undefined && pct !== null) ? ` <span style="font-weight:400;font-size:10px;opacity:0.7">${pct}% neg</span>` : '';
    return `<span class="badge ${M[g]||'badge-low'}">${g}${pctStr}</span>`;
  },

  _render() {
    const tbody = document.getElementById('matrixBody'); if (!tbody) return;
    tbody.innerHTML = this.TREE.map(cat => this._rowsForCat(cat)).join('');
  },

  _rowsForCat(cat) {
    const key=cat.id, open=this._expanded.has(key);
    const ps=Math.round(this._score(cat.gap_severity,cat.business_impact,cat.trend));
    let html=`<tr class="mrow-l0 ${open?'mrow-expanded':''}" id="mrow-${key}" onclick="DrillDownMatrix.toggle('${key}',event)">
      <td><div class="matrix-name-cell matrix-indent-0">
        <svg class="matrix-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        <span class="matrix-icon">${cat.icon||'📁'}</span>
        <div><div class="matrix-label-main">${cat.name}</div><div class="matrix-label-meta">${(cat.children||[]).length} sub-categories</div></div>
      </div></td>
      <td style="text-align:right;font-weight:700;color:var(--accent)">${cat.mentions.toLocaleString('en-IN')}</td>
      <td>${this._gap(cat.gap_severity, cat.neg_pct)}</td><td>${this._gap(cat.business_impact)}</td>
      <td>${this._trend(cat.trend)}</td>
      <td style="text-align:center"><div class="priority-score ${this._psClass(ps)}">${ps}</div></td>
    </tr>`;
    (cat.children||[]).forEach(sub => { html += this._rowsForSub(sub, key, open); });
    return html;
  },

  _rowsForSub(sub, parentKey, parentOpen) {
    const key=`${parentKey}__${sub.id}`, open=this._expanded.has(key);
    const hidden=parentOpen?'':'mrow-hidden';
    const ps=Math.round(this._score(sub.gap_severity,sub.business_impact,0));
    let html=`<tr class="mrow-l1 ${hidden} ${open?'mrow-expanded':''}" id="mrow-${key}" onclick="DrillDownMatrix.toggle('${key}',event)">
      <td><div class="matrix-name-cell matrix-indent-1">
        <svg class="matrix-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        <div><div class="matrix-label-sub">${sub.name}</div><div class="matrix-label-meta">${(sub.leaves||[]).length} evidence items</div></div>
      </div></td>
      <td style="text-align:right;color:var(--text-secondary)">${sub.mentions}</td>
      <td>${this._gap(sub.gap_severity)}</td><td>${this._gap(sub.business_impact)}</td>
      <td><span style="color:var(--text-muted);font-size:11px">—</span></td>
      <td style="text-align:center"><div class="priority-score ${this._psClass(ps)}">${ps}</div></td>
    </tr>`;
    (sub.leaves||[]).forEach(leaf => { html += this._rowForLeaf(leaf, key, open && parentOpen); });
    return html;
  },

  _rowForLeaf(leaf, parentKey, show) {
    const hidden=show?'':'mrow-hidden';
    const sc={positive:'var(--positive)',negative:'var(--negative)',neutral:'var(--warning)'};
    if (leaf.type==='quote') return `<tr class="mrow-leaf ${hidden}">
      <td colspan="5"><div class="matrix-indent-2" style="padding:2px 0">
        <div class="leaf-quote">${leaf.text}</div>
        <div class="leaf-source">📍 <span>${leaf.source}</span> &nbsp;·&nbsp; <span style="color:${sc[leaf.sentiment]||'var(--text-muted)'};font-weight:600">${leaf.sentiment||'neutral'}</span></div>
      </div></td><td></td></tr>`;
    if (leaf.type==='blocker') return `<tr class="mrow-leaf ${hidden}">
      <td colspan="5"><div class="matrix-indent-2" style="padding:2px 0"><div class="leaf-blocker">${leaf.text}</div></div></td>
      <td style="text-align:center">${this._gap(leaf.severity)}</td></tr>`;
    return '';
  },

  toggle(key, event) {
    if (event) event.stopPropagation();
    if (this._expanded.has(key)) {
      [...this._expanded].forEach(k => { if (k===key||k.startsWith(key+'__')) this._expanded.delete(k); });
    } else { this._expanded.add(key); }
    this._render();
  },

  expandAll() {
    this.TREE.forEach(cat => {
      this._expanded.add(cat.id);
      (cat.children||[]).forEach(sub => this._expanded.add(`${cat.id}__${sub.id}`));
    });
    this._render();
  },

  collapseAll() { this._expanded.clear(); this._render(); },
};

/* ════════════════════════════════════════════════════════════════════════════
   SURVEY FORM  —  in-dashboard modal → POST /api/survey/submit → PostgreSQL
   ════════════════════════════════════════════════════════════════════════════ */
const SurveyForm = {
  open() {
    document.getElementById('surveyModal').hidden   = false;
    document.getElementById('surveyOverlay').hidden = false;
    document.getElementById('surveyError').hidden   = true;
    document.getElementById('surveySuccess').hidden = true;
    document.getElementById('submitSurveyBtn').disabled = false;
  },

  close() {
    document.getElementById('surveyModal').hidden   = true;
    document.getElementById('surveyOverlay').hidden = true;
  },

  _checks(containerId) {
    return [...document.querySelectorAll(`#${containerId} input[type=checkbox]:checked`)].map(c=>c.value);
  },

  async submit() {
    const err  = document.getElementById('surveyError');
    const succ = document.getElementById('surveySuccess');
    const btn  = document.getElementById('submitSurveyBtn');
    err.hidden = true; succ.hidden = true;

    const body = {
      respondent_name:  document.getElementById('sf-name')?.value?.trim()  || '',
      email:            document.getElementById('sf-email')?.value?.trim()  || '',
      city:             document.getElementById('sf-city')?.value           || '',
      age_group:        document.getElementById('sf-age')?.value            || '',
      order_frequency:  document.getElementById('sf-freq')?.value           || '',
      categories:       this._checks('sf-cats'),
      blockers:         this._checks('sf-blockers'),
      suggestion:       document.getElementById('sf-suggest')?.value?.trim() || '',
    };

    // Client-side validation
    const required = [
      [body.respondent_name, 'Full Name'],
      [body.email,           'Email'],
      [body.city,            'City'],
      [body.age_group,       'Age Group'],
      [body.order_frequency, 'Order Frequency'],
    ];
    for (const [val, label] of required) {
      if (!val) {
        err.textContent = `Please fill in: ${label}`;
        err.hidden = false;
        return;
      }
    }

    btn.disabled = true;
    try {
      const res = await API.post('/api/survey/submit', body);
      if (res.error) { err.textContent = res.error; err.hidden = false; return; }
      succ.hidden = false;
      // Reset form
      ['sf-name','sf-email','sf-suggest'].forEach(id => { const el=document.getElementById(id); if(el) el.value=''; });
      ['sf-city','sf-age','sf-freq'].forEach(id => { const el=document.getElementById(id); if(el) el.selectedIndex=0; });
      document.querySelectorAll('#sf-cats input, #sf-blockers input').forEach(c=>c.checked=false);
      // Refresh tracker and KPIs
      await KPIStrip.load();
      await OpenTracker.refresh();
      setTimeout(() => this.close(), 2000);
    } catch (e) {
      err.textContent = `Submit failed: ${e.message}`;
      err.hidden = false;
    } finally {
      btn.disabled = false;
    }
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   OPEN DATA TRACKER  —  live table from /api/survey/responses
   ════════════════════════════════════════════════════════════════════════════ */
const OpenTracker = {
  initialized: false,
  _data: [],

  async init() {
    this.initialized = true;
    await this.refresh();
  },

  async refresh() {
    try {
      const d = await API.get('/api/survey/responses');
      this._data = d.responses || [];
      this._renderStats(d);
      this._renderTable(d.responses);
      // Update research tab badge
      const badge = document.getElementById('badge-research');
      if (badge) badge.textContent = d.total;
    } catch (e) {
      document.getElementById('trackerBody').innerHTML =
        `<tr><td colspan="11" style="text-align:center;padding:24px;color:var(--negative)">Error: ${e.message}</td></tr>`;
    }
  },

  _renderStats(d) {
    const el = document.getElementById('researchStats'); if (!el) return;
    const responses = d.responses || [];
    const total     = d.total || 0;
    const avg       = total ? Math.round(responses.reduce((s,r)=>s+r.quality_score,0)/responses.length) : 0;

    const cats = {};
    responses.forEach(r => (r.categories||[]).forEach(c => { cats[c]=(cats[c]||0)+1; }));
    const topCat = Object.entries(cats).sort((a,b)=>b[1]-a[1])[0]?.[0]?.replace(/_/g,' ') || '—';

    const items = [
      { v: total,       l: 'Total Responses' },
      { v: avg + '%',   l: 'Avg Quality Score' },
      { v: topCat,      l: 'Top Category' },
      { v: responses.filter(r=>r.quality_score>=80).length, l: 'High Quality' },
    ];
    el.innerHTML = items.map(i => `
      <div class="stat-card">
        <span class="stat-val">${i.v}</span>
        <div class="stat-lbl">${i.l}</div>
      </div>`).join('');
  },

  _renderTable(responses) {
    const tbody = document.getElementById('trackerBody'); if (!tbody) return;
    if (!responses.length) {
      tbody.innerHTML = `<tr><td colspan="11">
        <div class="tracker-empty">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:var(--text-muted)"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
          <p>No survey responses yet.<br>Click <strong>New Respondent</strong> to add the first one.</p>
        </div>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = responses.map((r, i) => {
      const sc    = r.quality_score >= 80 ? 'score-hi' : r.quality_score >= 60 ? 'score-md' : 'score-lo';
      const cats  = (r.categories||[]).map(c=>`<span class="cat-tag">${c.replace(/_/g,' ')}</span>`).join('');
      const blk   = (r.blockers||[]).join(', ').replace(/_/g,' ').slice(0,50) || '—';
      const sugg  = (r.suggestion||'—').slice(0,60) + (r.suggestion?.length>60?'…':'');
      const date  = r.created_at ? new Date(r.created_at).toLocaleDateString('en-IN') : '—';
      return `<tr>
        <td style="color:var(--text-muted)">${i+1}</td>
        <td style="font-weight:600;color:var(--text-primary)">${r.respondent_name}</td>
        <td>${r.email}</td>
        <td>${r.city}</td>
        <td>${r.age_group}</td>
        <td>${r.order_frequency}</td>
        <td>${cats||'—'}</td>
        <td style="font-size:10px;color:var(--text-muted)">${blk}</td>
        <td style="font-size:11px;color:var(--text-secondary)" title="${r.suggestion||''}">${sugg}</td>
        <td><span class="score-badge ${sc}">${r.quality_score}</span></td>
        <td style="color:var(--text-muted)">${date}</td>
      </tr>`;
    }).join('');
  },

  exportCSV() {
    if (!this._data.length) { alert('No data to export yet.'); return; }
    const headers = ['#','Name','Email','City','Age Group','Order Freq','Categories','Blockers','Suggestion','Quality Score','Date'];
    const rows    = this._data.map((r,i) => [
      i+1, r.respondent_name, r.email, r.city, r.age_group, r.order_frequency,
      (r.categories||[]).join(';'), (r.blockers||[]).join(';'), r.suggestion||'',
      r.quality_score, r.created_at||''
    ]);
    const csv = [headers, ...rows].map(row => row.map(v=>JSON.stringify(v)).join(',')).join('\
');
    const blob = new Blob([csv], { type:'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `instamart_survey_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   TOOLTIP
   ════════════════════════════════════════════════════════════════════════════ */
const Tooltip = {
  _el: null, _mv: null,
  init() { this._el = document.getElementById('globalTooltip'); },
  show(event, html) {
    if (!this._el) return;
    this._el.innerHTML = html;
    this._el.setAttribute('aria-hidden','false');
    this._el.classList.add('visible');
    this._pos(event.clientX, event.clientY);
    this._mv = e => this._pos(e.clientX, e.clientY);
    document.addEventListener('mousemove', this._mv, { passive:true });
  },
  _pos(x, y) {
    if (!this._el) return;
    const w=this._el.offsetWidth||240, h=this._el.offsetHeight||60, vw=window.innerWidth, vh=window.innerHeight;
    let l=x+16, t=y+16;
    if (l+w>vw-8) l=x-w-16; if (t+h>vh-8) t=y-h-16;
    if (l<8) l=8; if (t<8) t=8;
    this._el.style.left=l+'px'; this._el.style.top=t+'px';
  },
  hide() {
    if (!this._el) return;
    this._el.classList.remove('visible');
    this._el.setAttribute('aria-hidden','true');
    if (this._mv) { document.removeEventListener('mousemove', this._mv); this._mv=null; }
  },
  flash(msg) {
    if (!this._el) return;
    this._el.innerHTML = msg;
    this._el.style.cssText = 'left:50%;top:76px;transform:translateX(-50%)';
    this._el.classList.add('visible');
    setTimeout(() => {
      this._el.classList.remove('visible');
      this._el.style.cssText = '';
    }, 2800);
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   AI SEARCH  —  natural language query → Groq AI → answer from data
   ════════════════════════════════════════════════════════════════════════════ */
const AISearch = {
  initialized: false,
  _history: [],

  init() {
    this.initialized = true;
    const input = document.getElementById('aisearchInput');
    if (input) {
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter') this.search();
      });
    }
  },

  askPreset(btn) {
    const input = document.getElementById('aisearchInput');
    if (input && btn.textContent) {
      input.value = btn.textContent.trim();
      this.search();
    }
  },

  async search() {
    const input = document.getElementById('aisearchInput');
    const results = document.getElementById('aisearchResults');
    const empty = document.getElementById('aisearchEmpty');
    const btn = document.getElementById('aisearchBtn');
    if (!input || !results) return;

    const query = input.value.trim();
    if (!query) return;

    if (empty) empty.style.display = 'none';

    const userMsg = document.createElement('div');
    userMsg.className = 'aisearch-msg aisearch-user';
    userMsg.textContent = query;
    results.appendChild(userMsg);

    const loading = document.createElement('div');
    loading.className = 'aisearch-msg aisearch-loading';
    loading.innerHTML = '<div class="aisearch-spinner"></div><span>Analyzing data…</span>';
    results.appendChild(loading);

    if (btn) btn.disabled = true;
    input.value = '';
    results.scrollTop = results.scrollHeight;

    try {
      const data = await API.post('/api/search', { query });
      loading.remove();

      if (data.error) {
        const errDiv = document.createElement('div');
        errDiv.className = 'aisearch-msg aisearch-error';
        errDiv.textContent = data.error;
        results.appendChild(errDiv);
      } else {
        const aiMsg = document.createElement('div');
        aiMsg.className = 'aisearch-msg aisearch-ai';

        const answerDiv = document.createElement('div');
        answerDiv.className = 'aisearch-answer';
        answerDiv.innerHTML = this._formatAnswer(data.answer);
        aiMsg.appendChild(answerDiv);

        if (data.sources && data.sources.length) {
          const srcDiv = document.createElement('div');
          srcDiv.className = 'aisearch-sources';
          srcDiv.textContent = 'Sources: ' + data.sources.join(', ');
          aiMsg.appendChild(srcDiv);
        }
        results.appendChild(aiMsg);
      }
    } catch (e) {
      loading.remove();
      const errDiv = document.createElement('div');
      errDiv.className = 'aisearch-msg aisearch-error';
      errDiv.textContent = 'Network error — is the API server running?';
      results.appendChild(errDiv);
    }

    if (btn) btn.disabled = false;
    results.scrollTop = results.scrollHeight;
  },

  _formatAnswer(text) {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/^### (.*$)/gm, '<h4>$1</h4>')
      .replace(/^## (.*$)/gm, '<h4>$1</h4>')
      .replace(/^# (.*$)/gm, '<h4>$1</h4>')
      .replace(/^- (.*$)/gm, '<li>$1</li>')
      .replace(/^(\d+)\. (.*$)/gm, '<li>$2</li>')
      .replace(/\n{2,}/g, '</p><p>')
      .replace(/\n/g, '<br>');
    return `<p>${html}</p>`;
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   BOOT
   ════════════════════════════════════════════════════════════════════════════ */
async function init() {
  Tooltip.init();
  TabManager.init();

  // Load KPIs + insights in parallel
  const [, insightsData] = await Promise.all([
    KPIStrip.load(),
    API.get('/api/insights').catch(() => null),
  ]);

  State.insights = insightsData;

  // Init live data table (always visible on tab 1)
  LiveData.init();

  // If user opened directly to another tab via hash
  if (TabManager.active === 'insights')
    Charts.init(insightsData);
  if (TabManager.active === 'matrix')
    DrillDownMatrix.init();
  if (TabManager.active === 'research')
    OpenTracker.init();
}

document.addEventListener('DOMContentLoaded', init);
