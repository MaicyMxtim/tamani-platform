"""Generate tools/labeler.html — the golden-set labelling page.

Samples venues, embeds them with their current tags preselected (you
correct rather than start from scratch), and produces a single HTML file
with no server dependency. Progress persists in the browser; Export
downloads golden_set.json.

    python3 evals/make_labeler.py
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
venues = json.load(open(ROOT / "apps/api/data/venues.static.json"))

# AI suggestions for the previously-untagged venues, if the backfill ran
suggestions = {}
backfill = ROOT / "evals/backfill_results.json"
if backfill.exists():
    for r in json.load(open(backfill)):
        suggestions[r["venue_id"]] = r["vibes"]

untagged = [v for v in venues if not v.get("tags")]
tagged = [v for v in venues if v.get("tags")]
random.seed(42)
sample = random.sample(tagged, 110) + untagged

items = []
for v in sample:
    items.append({
        "id": v["id"],
        "name": v["name"],
        "meta": " · ".join(str(x) for x in [
            v.get("type_label"), v.get("area"), v.get("band_label"),
            f"{v.get('rating')}★ ({v.get('rating_count')})"] if x),
        "maps": v.get("maps_uri") or "",
        "pre": v.get("tags") or suggestions.get(v["id"], []),
    })
random.shuffle(items)

TAGS = ["special-occasion", "sit-down", "drinks", "groups", "late-night",
        "coffee", "quick", "work-friendly", "brunch", "solo-friendly"]

html = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tamani golden set labeller</title>
<style>
:root { --bg:#101418; --card:#1a2129; --text:#e8edf2; --dim:#8b98a5;
        --on:#2f6f4f; --onb:#57c78e; --accent:#d78a3d; }
@media (prefers-color-scheme: light) {
  :root { --bg:#f4f2ee; --card:#ffffff; --text:#22282e; --dim:#6b7680;
          --on:#d9efe3; --onb:#1e7a4d; }
}
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--text);
       font:16px/1.5 -apple-system, system-ui, sans-serif;
       display:flex; justify-content:center; padding:24px 12px; }
main { width:100%; max-width:560px; }
.progress { height:6px; background:var(--card); border-radius:3px; margin-bottom:16px; }
.progress div { height:100%; background:var(--accent); border-radius:3px; }
.card { background:var(--card); border-radius:14px; padding:22px; }
h1 { font-size:1.35rem; margin-bottom:4px; }
.meta { color:var(--dim); font-size:.9rem; margin-bottom:6px; }
.meta a { color:var(--accent); }
.count { color:var(--dim); font-size:.85rem; margin-bottom:14px; }
.tags { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:14px 0 20px; }
button.tag { padding:12px 10px; border-radius:10px; border:2px solid transparent;
  background:var(--bg); color:var(--text); font-size:.95rem; cursor:pointer; text-align:left; }
button.tag.on { background:var(--on); border-color:var(--onb); font-weight:600; }
button.tag small { color:var(--dim); }
.nav { display:flex; gap:10px; }
.nav button { flex:1; padding:12px; border-radius:10px; border:0; cursor:pointer;
  font-size:1rem; background:var(--bg); color:var(--text); }
.nav button.primary { background:var(--accent); color:#171310; font-weight:700; }
.footer { margin-top:14px; display:flex; justify-content:space-between;
  color:var(--dim); font-size:.85rem; }
.footer button { background:none; border:0; color:var(--accent); cursor:pointer; font-size:.85rem; }
kbd { background:var(--card); padding:1px 5px; border-radius:4px; border:1px solid var(--dim); }
</style>
<main>
  <div class="progress"><div id="bar"></div></div>
  <div class="card">
    <h1 id="name"></h1>
    <div class="meta" id="meta"></div>
    <div class="count" id="count"></div>
    <div class="tags" id="tags"></div>
    <div class="nav">
      <button onclick="move(-1)">&larr; Back</button>
      <button onclick="skip()" title="don't know this venue">Skip</button>
      <button class="primary" onclick="move(1)">Save &amp; next &rarr;</button>
    </div>
    <div class="footer">
      <span>Keys: <kbd>1</kbd>–<kbd>0</kbd> toggle · <kbd>&crarr;</kbd> next</span>
      <button onclick="exportSet()">Export golden_set.json</button>
    </div>
  </div>
</main>
<script>
const TAGS = __TAGS__;
const ITEMS = __ITEMS__;
let labels = JSON.parse(localStorage.getItem("golden") || "{}");
let i = Number(localStorage.getItem("golden_i") || 0);

function current() { return ITEMS[i]; }
function selected() {
  const v = current();
  if (labels[v.id]) return new Set(labels[v.id].tags);
  return new Set(v.pre);
}
function render() {
  const v = current(); const sel = selected();
  document.getElementById("name").textContent = v.name;
  document.getElementById("meta").innerHTML =
    v.meta + (v.maps ? ' · <a href="' + v.maps + '" target="_blank">map</a>' : "");
  const done = Object.keys(labels).length;
  document.getElementById("count").textContent =
    "Venue " + (i+1) + " of " + ITEMS.length + " — " + done + " labelled";
  document.getElementById("bar").style.width = (100 * done / ITEMS.length) + "%";
  const box = document.getElementById("tags"); box.innerHTML = "";
  TAGS.forEach((t, n) => {
    const b = document.createElement("button");
    b.className = "tag" + (sel.has(t) ? " on" : "");
    b.innerHTML = "<small>" + ((n+1) % 10) + "</small> " + t;
    b.onclick = () => { toggle(t); };
    box.appendChild(b);
  });
}
function toggle(t) {
  const v = current(); const sel = selected();
  sel.has(t) ? sel.delete(t) : sel.add(t);
  labels[v.id] = { tags: [...sel], skipped: false };
  persist(); render();
}
function save() {
  const v = current();
  if (!labels[v.id]) labels[v.id] = { tags: [...selected()], skipped: false };
}
function skip() {
  labels[current().id] = { tags: [], skipped: true };
  persist(); move(1, true);
}
function move(d, noSave) {
  if (d > 0 && !noSave) save();
  i = Math.min(Math.max(i + d, 0), ITEMS.length - 1);
  persist(); render();
  if (d > 0 && Object.keys(labels).length >= ITEMS.length) exportSet();
}
function persist() {
  localStorage.setItem("golden", JSON.stringify(labels));
  localStorage.setItem("golden_i", i);
}
function exportSet() {
  const out = ITEMS.filter(v => labels[v.id] && !labels[v.id].skipped)
    .map(v => ({ venue_id: v.id, name: v.name,
                 description: v.name + ". " + v.meta, tags: labels[v.id].tags }));
  const blob = new Blob([out.map(o => JSON.stringify(o)).join("\\n")],
                        { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "golden_set.jsonl";
  a.click();
}
document.addEventListener("keydown", e => {
  if (e.key === "Enter") move(1);
  else if (e.key === "ArrowLeft") move(-1);
  else if (e.key === "ArrowRight") move(1);
  else if (/^[0-9]$/.test(e.key)) toggle(TAGS[(Number(e.key) + 9) % 10]);
});
render();
</script>
"""

out = ROOT / "tools/labeler.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html.replace("__TAGS__", json.dumps(TAGS))
                   .replace("__ITEMS__", json.dumps(items)))
print(f"wrote {out} with {len(items)} venues "
      f"({len(untagged)} previously untagged, AI-prefilled)")
