// Ruolo C - Frontend: chiama GET /api/search (contratto 3) e mostra i risultati.
// Lo stato (q, config, page, compare) sta nell'URL: i link si possono condividere e il tasto "indietro" funziona.

const K = 10;
const CONFIGS = ["base", "it", "it_boost", "it_boost_fuzzy"];

const form = document.getElementById("search-form");
const qInput = document.getElementById("q");
const configSel = document.getElementById("config");
const compareBox = document.getElementById("compare");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const pagerEl = document.getElementById("pager");

// --- sicurezza: tutto il testo viene "escapato"; nello snippet si ripristinano SOLO <mark> e </mark>
function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function safeSnippet(s) {
  return escapeHtml(s).replace(/&lt;(\/?)mark&gt;/g, "<$1mark>");
}
function safeUrl(u) {
  return /^https?:\/\//i.test(u || "") ? u : "#";
}
function formatDate(d) {
  if (!d) return "data non disponibile";
  const [y, m, day] = d.split("-");
  return day && m ? `${day}/${m}/${y}` : d;
}

async function callApi(q, config, page) {
  const params = new URLSearchParams({ q, config, k: K, page });
  const resp = await fetch(`/api/search?${params}`);
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.error || `Errore HTTP ${resp.status}`);
  return body;
}

// --- vista normale: una configurazione, con paginazione
async function searchSingle(q, config, page) {
  statusEl.textContent = "Ricerca in corso…";
  const data = await callApi(q, config, page);
  const totalPages = Math.min(Math.ceil(data.total / K), Math.floor(1000 / K));

  if (data.total === 0) {
    statusEl.textContent = `Nessun risultato per "${data.query}" (${data.took_ms} ms, config ${data.config}).`;
  } else {
    const from = (page - 1) * K + 1;
    const to = from + data.results.length - 1;
    statusEl.textContent =
      `${data.total.toLocaleString("it-IT")} risultati in ${data.took_ms} ms — ` +
      `mostrati ${from}-${to} — config ${data.config}`;
  }

  resultsEl.innerHTML = data.results.map(r => `
    <article class="result">
      <h3><a href="${escapeHtml(safeUrl(r.url))}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a></h3>
      <div class="meta">
        #${r.rank} · ${escapeHtml(formatDate(r.date))} ·
        <a href="${escapeHtml(safeUrl(r.url))}" target="_blank" rel="noopener">fonte: it.wikinews.org</a> ·
        score ${Number(r.score).toFixed(2)}
      </div>
      <p class="snippet">${safeSnippet(r.snippet)}</p>
    </article>`).join("");

  renderPager(page, totalPages);
}

function renderPager(page, totalPages) {
  pagerEl.innerHTML = "";
  if (totalPages <= 1) return;
  const addBtn = (label, target, opts = {}) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.disabled = !!opts.disabled;
    if (opts.current) b.className = "current";
    b.addEventListener("click", () => go({ page: target }));
    pagerEl.appendChild(b);
  };
  addBtn("« Precedente", page - 1, { disabled: page <= 1 });
  const start = Math.max(1, page - 3);
  const end = Math.min(totalPages, start + 6);
  for (let p = start; p <= end; p++) addBtn(String(p), p, { current: p === page });
  addBtn("Successiva »", page + 1, { disabled: page >= totalPages });
}

// --- vista confronto: le 4 configurazioni affiancate (utile nella demo)
async function searchCompare(q) {
  statusEl.textContent = "Confronto in corso…";
  pagerEl.innerHTML = "";
  const all = await Promise.all(CONFIGS.map(c =>
    callApi(q, c, 1).catch(e => ({ config: c, error: e.message }))));
  statusEl.textContent = `Confronto delle 4 configurazioni per "${q}" (primi ${K} risultati).`;
  resultsEl.innerHTML = `<div class="compare-grid">${all.map(d => `
    <section class="compare-col">
      <h2>${escapeHtml(d.config)}</h2>
      ${d.error
        ? `<div class="info">Errore: ${escapeHtml(d.error)}</div>`
        : `<div class="info">${d.total.toLocaleString("it-IT")} risultati · ${d.took_ms} ms</div>
           <ol>${d.results.map(r => `
             <li><a href="${escapeHtml(safeUrl(r.url))}" target="_blank" rel="noopener"
                    title="${escapeHtml(r.snippet.replace(/<\/?mark>/g, ""))}">${escapeHtml(r.title)}</a></li>`).join("")}
           </ol>`}
    </section>`).join("")}</div>`;
}

// --- stato nell'URL
function readState() {
  const p = new URLSearchParams(location.search);
  return {
    q: p.get("q") || "",
    config: CONFIGS.includes(p.get("config")) ? p.get("config") : "it_boost",
    page: Math.max(1, parseInt(p.get("page"), 10) || 1),
    compare: p.get("compare") === "1",
  };
}

function go(changes) {
  const s = { ...readState(), ...changes };
  const p = new URLSearchParams({ q: s.q, config: s.config, page: s.page });
  if (s.compare) p.set("compare", "1");
  history.pushState(null, "", `?${p}`);
  run();
}

async function run() {
  const s = readState();
  qInput.value = s.q;
  configSel.value = s.config;
  compareBox.checked = s.compare;
  configSel.disabled = s.compare;
  statusEl.classList.remove("error");
  if (!s.q.trim()) {
    statusEl.textContent = "";
    resultsEl.innerHTML = "";
    pagerEl.innerHTML = "";
    return;
  }
  try {
    if (s.compare) await searchCompare(s.q.trim());
    else await searchSingle(s.q.trim(), s.config, s.page);
    window.scrollTo(0, 0);
  } catch (e) {
    statusEl.classList.add("error");
    statusEl.textContent = e.message;
    resultsEl.innerHTML = "";
    pagerEl.innerHTML = "";
  }
}

form.addEventListener("submit", ev => {
  ev.preventDefault();
  const q = qInput.value.trim();
  if (!q) {
    statusEl.classList.add("error");
    statusEl.textContent = "Scrivi almeno una parola da cercare.";
    return;
  }
  go({ q, config: configSel.value, page: 1, compare: compareBox.checked });
});
configSel.addEventListener("change", () => { if (qInput.value.trim()) go({ q: qInput.value.trim(), config: configSel.value, page: 1 }); });
compareBox.addEventListener("change", () => {
  configSel.disabled = compareBox.checked;
  if (qInput.value.trim()) go({ q: qInput.value.trim(), page: 1, compare: compareBox.checked });
});
window.addEventListener("popstate", run);
run();
