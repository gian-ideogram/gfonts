"""Interactive font curation manager.

Serves a local web UI for moving fonts between allowed, script-tagged,
and blacklisted tiers.  Changes save directly to the JSON files.
"""

from __future__ import annotations

import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _load_fonts(data_dir: Path) -> list[dict]:
    allow = json.loads((data_dir / "allowlist.json").read_text())
    blacklist = json.loads((data_dir / "blacklist.json").read_text())
    script_path = data_dir / "script_fonts.json"
    script_fonts = json.loads(script_path.read_text()) if script_path.exists() else []

    all_fonts: list[dict] = []
    for f in allow:
        all_fonts.append({
            "family": f["family"], "category": f["category"],
            "variants": f.get("variants", []), "tags": f.get("tags", []),
            "status": "allowed",
            "script": "latin", "script_group": "latin",
            "reason": None, "reason_description": None,
        })
    for f in script_fonts:
        all_fonts.append({
            "family": f["family"], "category": f["category"],
            "variants": f.get("variants", []), "tags": f.get("tags", []),
            "status": "script",
            "script": f["script"], "script_group": f["script_group"],
            "reason": None, "reason_description": None,
        })
    for e in blacklist:
        fam = e["family"]
        all_fonts.append({
            "family": fam, "category": "Unknown",
            "variants": [], "tags": [],
            "status": "blacklisted", "script": None, "script_group": None,
            "reason": e.get("reason"), "reason_description": e.get("reason_description"),
        })
    all_fonts.sort(key=lambda f: f["family"].lower())
    return all_fonts


def _google_fonts_links(families: list[str], chunk: int = 80) -> str:
    lines = []
    for i in range(0, len(families), chunk):
        batch = families[i : i + chunk]
        parts = [f"family={fam.replace(' ', '+')}:wght@400" for fam in batch]
        url = "https://fonts.googleapis.com/css2?" + "&".join(parts) + "&display=swap"
        lines.append(f'<link href="{url}" rel="stylesheet">')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_SCRIPT_GROUP_META = {
    "latin":           {"label": "Latin",          "color": "#27ae60"},
    "cjk":             {"label": "CJK",            "color": "#2980b9"},
    "indic":           {"label": "Indic",           "color": "#8e44ad"},
    "southeast_asian": {"label": "SE Asian",        "color": "#16a085"},
    "middle_eastern":  {"label": "Middle Eastern",  "color": "#d35400"},
    "european":        {"label": "European",        "color": "#2c3e50"},
    "african":         {"label": "African",         "color": "#c0392b"},
    "caucasian":       {"label": "Caucasian",       "color": "#7f8c8d"},
    "historical_rare": {"label": "Historical/Rare", "color": "#95a5a6"},
    "tibetan":         {"label": "Tibetan",         "color": "#e67e22"},
    "vietnamese":      {"label": "Vietnamese",      "color": "#1abc9c"},
}


def _build_page(fonts: list[dict]) -> str:
    families = [f["family"] for f in fonts]
    link_tags = _google_fonts_links(families)

    groups_used = sorted(
        {f["script_group"] for f in fonts if f["status"] == "script" and f["script_group"]}
    )
    script_group_btns = "".join(
        f'<button class="filter-btn script-group-btn" data-script-group="{g}">'
        f'{_SCRIPT_GROUP_META.get(g, {}).get("label", g)}</button>'
        for g in groups_used
    )

    all_tags = sorted({t for f in fonts for t in f.get("tags", [])})
    tag_btns = "".join(
        f'<button class="filter-btn tag-btn" data-tag="{t}">{t}</button>'
        for t in all_tags
    )

    fonts_json = json.dumps(fonts)
    group_meta_json = json.dumps(_SCRIPT_GROUP_META)

    return (
        "<!DOCTYPE html>\n<html>\n<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Font Curation Manager</title>\n"
        + link_tags
        + """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, -apple-system, sans-serif; background: #f5f6f8; color: #333; }
.topbar { position: sticky; top: 0; z-index: 100; background: #fff; border-bottom: 1px solid #ddd; padding: 10px 20px; display: flex; flex-direction: column; gap: 8px; }
.topbar-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.topbar h1 { font-size: 18px; white-space: nowrap; }
.search { flex: 1; min-width: 200px; padding: 7px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; outline: none; }
.search:focus { border-color: #3498db; box-shadow: 0 0 0 2px rgba(52,152,219,0.15); }
.filters { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.filter-btn { padding: 4px 8px; font-size: 11px; border: 1px solid #ddd; background: #fff; border-radius: 4px; cursor: pointer; font-weight: 500; white-space: nowrap; }
.filter-btn.active { background: #333; color: #fff; border-color: #333; }
.filter-btn:hover { background: #eee; }
.filter-btn.active:hover { background: #555; }
.filter-sep { width: 1px; height: 20px; background: #ddd; margin: 0 2px; }
.filter-label { font-size: 10px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.stats { font-size: 12px; color: #888; white-space: nowrap; }
.save-btn { padding: 6px 14px; font-size: 13px; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; background: #27ae60; color: #fff; white-space: nowrap; }
.save-btn:hover { background: #219a52; }
.save-btn.pending { background: #e67e22; }
.save-btn.saving { background: #95a5a6; pointer-events: none; }
.save-btn.saved { background: #27ae60; }
.container { padding: 12px 20px; }
.font-row { display: flex; align-items: center; padding: 5px 10px; background: #fff; margin-bottom: 2px; border-radius: 4px; border-left: 4px solid transparent; }
.font-row.allowed { border-left-color: #27ae60; }
.font-row.script { border-left-color: #3498db; }
.font-row.blacklisted { border-left-color: #e74c3c; opacity: 0.65; }
.font-row.blacklisted .font-sample { text-decoration: line-through; text-decoration-color: #e74c3c55; }
.font-row:hover { box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.font-row.hidden { display: none; }
.status-btn { display: flex; gap: 2px; flex-shrink: 0; }
.status-btn button { width: 22px; height: 22px; border-radius: 4px; border: 1px solid #ddd; cursor: pointer; font-size: 10px; line-height: 20px; text-align: center; background: #f5f5f5; color: #999; transition: all 0.15s; }
.status-btn button:hover { border-color: #aaa; }
.status-btn button.active-allow { background: #27ae60; color: #fff; border-color: #27ae60; }
.status-btn button.active-script { background: #3498db; color: #fff; border-color: #3498db; }
.status-btn button.active-block { background: #e74c3c; color: #fff; border-color: #e74c3c; }
.font-name { width: 200px; min-width: 200px; font-size: 11px; color: #888; margin-left: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.font-sample { font-size: 22px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.font-cat { width: 80px; font-size: 10px; color: #aaa; text-align: center; }
.font-tag { min-width: 100px; font-size: 10px; text-align: right; padding: 2px 6px; border-radius: 3px; white-space: nowrap; }
.font-tag.tag-script { background: #ebf5fb; color: #2980b9; }
.font-tag.tag-reason { background: #fdedec; color: #c0392b; }
.font-tags { display: flex; gap: 3px; flex-wrap: wrap; min-width: 180px; justify-content: flex-end; }
.font-tags .tag-pill { font-size: 9px; padding: 1px 5px; border-radius: 3px; background: #eef2f7; color: #555; white-space: nowrap; }
.font-tags .tag-pill.aesthetic { background: #f0e6ff; color: #6c3fa0; }
.font-tags .tag-pill.usecase { background: #e6f7ee; color: #1a7a42; }
.toast { position: fixed; bottom: 24px; right: 24px; padding: 10px 20px; border-radius: 6px; color: #fff; font-size: 13px; font-weight: 500; opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 200; }
.toast.show { opacity: 1; }
.toast.success { background: #27ae60; }
.toast.error { background: #e74c3c; }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-row">
    <h1>Font Curation</h1>
    <input class="search" type="text" placeholder="Search fonts..." id="search">
    <span class="stats" id="stats"></span>
    <button class="save-btn" id="saveBtn" onclick="saveChanges()">Save Changes</button>
  </div>
  <div class="topbar-row">
    <span class="filter-label">Status</span>
    <div class="filters" id="statusFilters">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="allowed">Allowed</button>
      <button class="filter-btn" data-filter="script">Script</button>
      <button class="filter-btn" data-filter="blacklisted">Blacklisted</button>
    </div>
    <div class="filter-sep"></div>
    <span class="filter-label">Category</span>
    <div class="filters" id="catFilters">
      <button class="filter-btn" data-cat="Sans Serif">Sans</button>
      <button class="filter-btn" data-cat="Serif">Serif</button>
      <button class="filter-btn" data-cat="Display">Display</button>
      <button class="filter-btn" data-cat="Handwriting">Hand</button>
      <button class="filter-btn" data-cat="Monospace">Mono</button>
    </div>
    <div class="filter-sep"></div>
    <span class="filter-label">Script</span>
    <div class="filters" id="scriptFilters">
      """
        + script_group_btns
        + """
    </div>
  </div>
  <div class="topbar-row">
    <span class="filter-label">Tags</span>
    <div class="filters" id="tagFilters">
      """
        + tag_btns
        + """
    </div>
  </div>
</div>

<div class="container" id="container"></div>
<div class="toast" id="toast"></div>

<script>
const FONTS = """
        + fonts_json
        + """;
const GROUP_META = """
        + group_meta_json
        + """;
let dirty = false;
let activeStatus = 'all';
let activeCat = null;
let activeScriptGroup = null;
let activeTag = null;
const USECASE_TAGS = new Set(['heading','body','logo','caption','editorial','UI','signage','branding']);

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(function() { t.className = 'toast'; }, 2500);
}

function render() {
  const q = document.getElementById('search').value.toLowerCase();
  let shown = 0, nAllowed = 0, nScript = 0, nBlocked = 0;
  FONTS.forEach(function(f) {
    if (f.status === 'allowed') nAllowed++;
    else if (f.status === 'script') nScript++;
    else nBlocked++;
  });
  const rows = document.querySelectorAll('.font-row');
  rows.forEach(function(row, i) {
    const f = FONTS[i];
    const matchQ = !q || f.family.toLowerCase().includes(q) || (f.script && f.script.includes(q)) || (f.tags && f.tags.some(function(t) { return t.includes(q); }));
    const matchStatus = activeStatus === 'all' || f.status === activeStatus;
    const matchCat = !activeCat || f.category === activeCat;
    const matchScript = !activeScriptGroup || f.script_group === activeScriptGroup;
    const matchTag = !activeTag || (f.tags && f.tags.includes(activeTag));
    row.classList.toggle('hidden', !(matchQ && matchStatus && matchCat && matchScript && matchTag));
    if (matchQ && matchStatus && matchCat && matchScript && matchTag) shown++;
  });
  document.getElementById('stats').textContent =
    shown + ' shown \\u00b7 ' + nAllowed + ' allowed \\u00b7 ' + nScript + ' script \\u00b7 ' + nBlocked + ' blocked';
  const btn = document.getElementById('saveBtn');
  btn.classList.toggle('pending', dirty);
  btn.textContent = dirty ? 'Save Changes *' : 'Save Changes';
}

function setStatus(idx, newStatus) {
  const f = FONTS[idx];
  if (f.status === newStatus) return;
  f.status = newStatus;
  if (newStatus === 'blacklisted') {
    f.reason = f.reason || 'manual';
    f.reason_description = f.reason_description || 'Manually blacklisted';
  }
  if (newStatus === 'script' && !f.script) {
    f.script = 'other';
    f.script_group = 'historical_rare';
  }
  const row = document.querySelectorAll('.font-row')[idx];
  row.className = 'font-row ' + newStatus;
  const btns = row.querySelectorAll('.status-btn button');
  btns[0].className = newStatus === 'allowed' ? 'active-allow' : '';
  btns[1].className = newStatus === 'script' ? 'active-script' : '';
  btns[2].className = newStatus === 'blacklisted' ? 'active-block' : '';
  const tag = row.querySelector('.font-tag');
  if (newStatus === 'script') {
    tag.className = 'font-tag tag-script';
    tag.textContent = f.script;
  } else if (newStatus === 'blacklisted') {
    tag.className = 'font-tag tag-reason';
    tag.textContent = f.reason || 'manual';
  } else {
    tag.className = 'font-tag';
    tag.textContent = '';
  }
  dirty = true;
  render();
}

function buildRows() {
  var c = document.getElementById('container');
  var html = [];
  for (var i = 0; i < FONTS.length; i++) {
    var f = FONTS[i];
    var safe = f.family.replace(/'/g, "\\\\'");
    var cls = f.status;
    var allowCls = f.status === 'allowed' ? 'active-allow' : '';
    var scriptCls = f.status === 'script' ? 'active-script' : '';
    var blockCls = f.status === 'blacklisted' ? 'active-block' : '';
    var tagHtml;
    if (f.status === 'script') {
      tagHtml = '<span class="font-tag tag-script">' + (f.script || '') + '</span>';
    } else if (f.status === 'blacklisted') {
      tagHtml = '<span class="font-tag tag-reason">' + (f.reason || '') + '</span>';
    } else {
      tagHtml = '<span class="font-tag"></span>';
    }
    var tagsHtml = '<span class="font-tags">';
    if (f.tags) {
      for (var j = 0; j < f.tags.length; j++) {
        var pillCls = USECASE_TAGS.has(f.tags[j]) ? 'tag-pill usecase' : 'tag-pill aesthetic';
        tagsHtml += '<span class="' + pillCls + '">' + f.tags[j] + '</span>';
      }
    }
    tagsHtml += '</span>';
    html.push(
      '<div class="font-row ' + cls + '">' +
      '<div class="status-btn">' +
      '<button class="' + allowCls + '" data-idx="' + i + '" data-s="allowed" title="Allowed">&#10003;</button>' +
      '<button class="' + scriptCls + '" data-idx="' + i + '" data-s="script" title="Script font">S</button>' +
      '<button class="' + blockCls + '" data-idx="' + i + '" data-s="blacklisted" title="Blacklisted">&#10007;</button>' +
      '</div>' +
      '<span class="font-name">' + f.family + '</span>' +
      "<span class=\\"font-sample\\" style=\\"font-family:'" + safe + "',sans-serif\\">Handgloves & Skyz</span>" +
      '<span class="font-cat">' + f.category + '</span>' +
      tagsHtml +
      tagHtml +
      '</div>'
    );
  }
  c.innerHTML = html.join('');
}

document.getElementById('container').addEventListener('click', function(e) {
  var btn = e.target.closest('.status-btn button');
  if (!btn) return;
  setStatus(parseInt(btn.dataset.idx), btn.dataset.s);
});

function saveChanges() {
  var saveBtn = document.getElementById('saveBtn');
  saveBtn.classList.add('saving');
  saveBtn.textContent = 'Saving...';
  var payload = {
    allowlist: FONTS.filter(function(f) { return f.status === 'allowed'; }).map(function(f) {
      return { family: f.family, category: f.category, variants: f.variants, subsets: [], tags: f.tags || [] };
    }),
    script_fonts: FONTS.filter(function(f) { return f.status === 'script'; }).map(function(f) {
      return { family: f.family, script: f.script, script_group: f.script_group, category: f.category, variants: f.variants, subsets: [], tags: f.tags || [] };
    }),
    blacklist: FONTS.filter(function(f) { return f.status === 'blacklisted'; }).map(function(f) {
      return { family: f.family, reason: f.reason || 'manual', reason_description: f.reason_description || 'Manually blacklisted' };
    })
  };
  fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    saveBtn.classList.remove('saving');
    if (data.ok) {
      dirty = false;
      render();
      showToast('Saved ' + payload.allowlist.length + ' allowed, ' + payload.script_fonts.length + ' script, ' + payload.blacklist.length + ' blacklisted', 'success');
    } else {
      showToast('Save failed: ' + (data.error || 'unknown'), 'error');
    }
  })
  .catch(function(err) {
    saveBtn.classList.remove('saving');
    showToast('Save failed: ' + err, 'error');
  });
}

document.querySelectorAll('#statusFilters .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('#statusFilters .filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    activeStatus = btn.dataset.filter;
    render();
  });
});
document.querySelectorAll('#catFilters .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    if (btn.classList.contains('active')) { btn.classList.remove('active'); activeCat = null; }
    else { document.querySelectorAll('#catFilters .filter-btn').forEach(function(b) { b.classList.remove('active'); }); btn.classList.add('active'); activeCat = btn.dataset.cat; }
    render();
  });
});
document.querySelectorAll('#scriptFilters .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    if (btn.classList.contains('active')) { btn.classList.remove('active'); activeScriptGroup = null; }
    else { document.querySelectorAll('#scriptFilters .filter-btn').forEach(function(b) { b.classList.remove('active'); }); btn.classList.add('active'); activeScriptGroup = btn.dataset.scriptGroup; }
    render();
  });
});
document.querySelectorAll('#tagFilters .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    if (btn.classList.contains('active')) { btn.classList.remove('active'); activeTag = null; }
    else { document.querySelectorAll('#tagFilters .filter-btn').forEach(function(b) { b.classList.remove('active'); }); btn.classList.add('active'); activeTag = btn.dataset.tag; }
    render();
  });
});
document.getElementById('search').addEventListener('input', render);

buildRows();
render();
</script>
</body>
</html>"""
    )


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------


def _make_handler(data_dir: Path) -> type:
    """Create a request handler class bound to a specific data directory."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                fonts = _load_fonts(data_dir)
                html = _build_page(fonts)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/api/save":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                try:
                    data_dir.mkdir(parents=True, exist_ok=True)
                    (data_dir / "allowlist.json").write_text(
                        json.dumps(body["allowlist"], indent=2)
                    )
                    (data_dir / "script_fonts.json").write_text(
                        json.dumps(body["script_fonts"], indent=2)
                    )
                    (data_dir / "blacklist.json").write_text(
                        json.dumps(body["blacklist"], indent=2)
                    )
                    n = (
                        len(body["allowlist"]),
                        len(body["script_fonts"]),
                        len(body["blacklist"]),
                    )
                    print(
                        f"  Saved: {n[0]} allowed, {n[1]} script, {n[2]} blacklisted"
                    )
                    self._json_response({"ok": True})
                except Exception as exc:
                    self._json_response({"ok": False, "error": str(exc)}, code=500)
            else:
                self.send_error(404)

        def _json_response(self, data: dict, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, fmt, *args):
            first = str(args[0]) if args else ""
            if "/api/" in first:
                super().log_message(fmt, *args)

    return _Handler


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_curate_server(
    *,
    port: int = 8250,
    no_open: bool = False,
    data_dir: str | None = None,
) -> None:
    """Launch the font curation web UI."""
    resolved_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
    handler_cls = _make_handler(resolved_dir)

    url = f"http://localhost:{port}"
    server = HTTPServer(("", port), handler_cls)
    print(f"Font Manager running at {url}")
    print(f"Data directory: {resolved_dir}")
    print("Press Ctrl+C to stop.\n")

    if not no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
