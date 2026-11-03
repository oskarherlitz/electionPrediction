"""Generate a single self-contained interactive HTML dashboard (no server, no CDN)
for the Model Citizens 2026 entry. Open outputs/report.html in any browser.

Operate/Read-mode data dashboard: precision and restraint. Carries a Senate
tile-grid map, a House seat spectrum, an EV-vs-price scatter, animated chamber
bars, and a per-race reward-curve explorer.
"""
from __future__ import annotations

import base64
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forecast.build import read_template_order, read_odds, build_candidates  # noqa: E402
from forecast.scoring import reward, is_valid_price  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")


def load_q_latest():
    p = os.path.join(DATA, "q_snapshot.csv")
    d = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            if r.get("q_price") not in (None, ""):
                try:
                    d[r["market_ticker"]] = float(r["q_price"])
                except ValueError:
                    pass
    return d


def b64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode()


def build_race_data():
    q_latest = load_q_latest()
    order = read_template_order(os.path.join(DATA, "templates", "full_congress_template.csv"))
    odds = read_odds(os.path.join(DATA, "reconstructed_odds_full.csv"))
    audit = {r["race_id"]: r for r in csv.DictReader(open(os.path.join(OUT, "picks_audit_full.csv")))}
    races = []
    for rid, chamber in order.items():
        a = audit.get(rid, {})
        cands = build_candidates(odds.get(rid, []), q_latest=q_latest)
        cand_js = []
        for c in cands:
            if not (c.priced and is_valid_price(c.p)):
                continue
            cand_js.append({"name": c.name, "party": c.party,
                            "p": round(c.p, 4), "q": round(c.q, 4),
                            "reward": round(reward(c.p), 3),
                            "ev": round(c.q * reward(c.p), 4)})
        cand_js.sort(key=lambda x: -x["q"])
        dwin = next((c["q"] for c in cand_js if c["party"] == "D"), 0.0)
        races.append({
            "id": rid, "chamber": chamber, "state": rid.split("-")[0],
            "pick": a.get("rec_candidate", ""), "pick_party": a.get("rec_party", ""),
            "pick_q": a.get("rec_q", ""), "pick_p": a.get("rec_p", ""),
            "pick_reward": a.get("rec_reward", ""), "pick_ev": a.get("rec_expected_points", ""),
            "likely": a.get("ml_candidate", ""), "likely_party": a.get("ml_party", ""),
            "type": a.get("pick_type", ""), "note": a.get("note", ""),
            "dwin": round(dwin, 4), "candidates": cand_js,
        })
    return races


def _counts():
    return {"D": 0, "R": 0, "I": 0}


def chamber_control(races):
    out = {"House": {"likely": _counts(), "picks": _counts()},
           "Senate": {"likely": _counts(), "picks": _counts()}}
    for r in races:
        ch = out[r["chamber"]]
        for key, party in (("likely", r["likely_party"]), ("picks", r["pick_party"])):
            p = party if party in ("D", "R", "I") else "I"
            ch[key][p] += 1
    return out


def summary(races):
    priced = [r for r in races if r["candidates"]]
    fav = sum(1 for r in races if r["type"] == "favorite" and "FALLBACK" not in r["note"])
    und = sum(1 for r in races if r["type"] == "underdog")
    fb = sum(1 for r in races if "FALLBACK" in r["note"])
    evsum = sum(float(r["pick_ev"]) for r in races if r["pick_ev"])
    cc = chamber_control(races)
    return {"n": len(races), "priced": len(priced), "fav": fav, "und": und,
            "fb": fb, "evsum": round(evsum, 1),
            "house": cc["House"]["likely"], "sen": cc["Senate"]["likely"]}


HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Model Citizens 2026 — Forecast Dashboard</title>
<style>
:root{
  --bg:#0e1118;--canvas:#141924;--panel:#1a2130;--ink:#eef2f8;--mut:#9aa7bd;--faint:#6b7689;
  --d:#4b8fe3;--d2:#3a6fb0;--r:#e05a4e;--r2:#b0463c;--i:#6cc18a;--acc:#f0b93e;
  --line:#28303f;--line2:#333d4f;
}
*{box-sizing:border-box}
html{scrollbar-color:#37425a var(--bg)}
body{margin:0;background:
    radial-gradient(1200px 600px at 70% -10%, #19202e 0%, var(--bg) 60%) fixed;
  color:var(--ink);font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-feature-settings:"ss01","cv01";-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:40px 22px 96px}
h1{font-size:clamp(24px,5.2vw,40px);line-height:1.08;letter-spacing:-.035em;margin:0 0 8px;text-wrap:balance;overflow-wrap:break-word;font-weight:800}
h2{font-size:22px;letter-spacing:-.02em;margin:48px 0 6px;font-weight:700;text-wrap:balance}
h3{letter-spacing:-.015em}
p{text-wrap:pretty}
.lede{color:var(--mut);max-width:70ch;margin:0 0 6px;font-size:16px}
.sub{color:var(--mut);max-width:72ch;margin:4px 0 18px}
.rule{height:1px;background:linear-gradient(90deg,var(--line2),transparent);margin:6px 0 0}
.tnum{font-variant-numeric:tabular-nums lining-nums}
::selection{background:rgba(240,185,62,.28);color:#fff}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px;border-radius:6px}
::-webkit-scrollbar{width:11px;height:11px}
::-webkit-scrollbar-thumb{background:#37425a;border-radius:8px;border:2px solid var(--bg)}
::-webkit-scrollbar-track{background:transparent}
/* metrics */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(142px,1fr));gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:22px 0}
.card{background:var(--canvas);padding:15px 17px;overflow-wrap:anywhere}
.card .big{font-size:clamp(20px,4.5vw,25px);font-weight:750;letter-spacing:-.02em}
.card .lbl{color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-top:3px}
/* callout — no colored left-border; filled block with a bold lead */
.note{background:#1b2438;border:1px solid var(--line2);padding:14px 17px;border-radius:12px;margin:16px 0;color:#dde6f5}
.note b{color:var(--acc)}
img.fig{width:100%;border-radius:12px;border:1px solid var(--line);background:#fff;margin:6px 0;display:block}
/* segmented toggle */
.seg{display:inline-flex;background:var(--panel);border:1px solid var(--line2);border-radius:10px;overflow:hidden}
.seg button{background:transparent;color:var(--mut);border:0;padding:8px 15px;font:inherit;font-size:14px;cursor:pointer;transition:background .18s,color .18s}
.seg button:hover{color:var(--ink)}
.seg button[aria-pressed=true]{background:var(--acc);color:#1a1200;font-weight:700}
/* panels */
.panel{background:var(--canvas);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:12px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid2>*{min-width:0}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
@media(max-width:480px){.wrap{padding:28px 15px 72px}.cards{grid-template-columns:1fr 1fr}.map{max-width:100%}}
.panel h3{margin:0 0 2px;font-size:17px} .panel .meta{color:var(--mut);font-size:13px;margin-bottom:14px}
/* chamber seat bars */
.seatbar{position:relative;height:34px;border-radius:9px;overflow:hidden;display:flex;background:#0b0f17;border:1px solid var(--line)}
.seatbar span{height:100%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;
  color:#0b0f17;width:0;transition:width 1.1s cubic-bezier(.16,1,.3,1);white-space:nowrap;overflow:hidden}
.seatbar .sD{background:var(--d)} .seatbar .sR{background:var(--r)} .seatbar .sI{background:var(--i)}
.majline{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--ink)}
.majline b{position:absolute;top:-16px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--mut);font-weight:600;white-space:nowrap}
.legend{display:flex;gap:16px;margin-top:11px;font-size:13px;color:var(--mut);flex-wrap:wrap}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.win{font-weight:700} .win.D{color:#8fc0f7} .win.R{color:#f2a199} .win.tie{color:var(--mut)}
/* tile map + spectrum */
.map{display:grid;grid-template-columns:repeat(11,1fr);gap:4px;max-width:560px}
.tile{aspect-ratio:1;border-radius:6px;display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;color:#0b0f17;background:#222a38;cursor:default;position:relative;
  animation:fade .5s ease both}
.tile.off{color:var(--faint);background:#1a2130;font-weight:600}
.tile[data-p=D]{background:var(--d)} .tile[data-p=R]{background:var(--r)} .tile[data-p=I]{background:var(--i)}
.tile.flip::after{content:"";position:absolute;inset:3px;border:2px solid var(--acc);border-radius:4px}
.spectrum{display:grid;grid-auto-flow:column;grid-template-rows:repeat(5,1fr);gap:3px;overflow-x:auto;padding-bottom:6px}
.cell{width:13px;height:13px;border-radius:3px;background:#222a38;position:relative}
.cell[data-p=D]{background:var(--d)} .cell[data-p=R]{background:var(--r)} .cell[data-p=I]{background:var(--i)}
.cell.flip{box-shadow:0 0 0 2px var(--acc)}
.tip{position:fixed;pointer-events:none;background:#0b0f17;border:1px solid var(--line2);border-radius:8px;
  padding:7px 10px;font-size:12.5px;color:var(--ink);opacity:0;transition:opacity .12s;z-index:50;max-width:240px;
  box-shadow:0 8px 24px -8px rgba(0,0,0,.6)}
/* table */
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line)}
td.tnum,th.tnum{font-variant-numeric:tabular-nums}
th{color:var(--mut);font-weight:600;user-select:none;position:sticky;top:0;background:var(--canvas);z-index:2}
th[role=button]{cursor:pointer} th[role=button]:hover{color:var(--ink)}
th[aria-sort=ascending]::after{content:" ↑";color:var(--acc)} th[aria-sort=descending]::after{content:" ↓";color:var(--acc)}
tr.race{cursor:pointer} tr.race:hover{background:#1b2333}
.pill{display:inline-block;min-width:20px;text-align:center;padding:1px 7px;border-radius:20px;font-size:12px;font-weight:700}
.pill.D{background:rgba(75,143,227,.2);color:#9fc8f8} .pill.R{background:rgba(224,90,78,.2);color:#f3a89f}
.pill.I{background:rgba(108,193,138,.2);color:#a9dcbb}
.fav{color:var(--i)} .dog{color:var(--acc)}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
input,select{background:var(--panel);color:var(--ink);border:1px solid var(--line2);border-radius:9px;padding:8px 11px;font:inherit;font-size:14px}
input::placeholder{color:var(--faint)}
.tablewrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:12px}
#detail{background:var(--canvas);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-top:14px;display:none}
.barwrap{background:#0b0f17;border-radius:5px;overflow:hidden;border:1px solid var(--line)}
.bar{height:15px;border-radius:4px}
.crow{display:grid;grid-template-columns:168px 1fr 1fr;gap:12px;align-items:center;margin:7px 0}
.mini{display:flex;gap:7px;align-items:center;font-variant-numeric:tabular-nums}
small{color:var(--mut)} a{color:#9fc8f8}
/* chart primitives */
.chart{background:#0b0f17;border:1px solid var(--line);border-radius:12px;margin-top:10px;display:block;width:100%}
.chart .axis{stroke:var(--line2);stroke-width:1} .chart .grid{stroke:#192132;stroke-width:1}
.chart .lbl{fill:var(--mut);font-size:11px;font-variant-numeric:tabular-nums}
.rc .curve{fill:none;stroke:var(--acc);stroke-width:2.5;stroke-linecap:round;stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.3s cubic-bezier(.16,1,.3,1) forwards}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:scale(1)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){
  .rc .curve{animation:none;stroke-dashoffset:0}.seatbar span{transition:none}
  .tile,[style*=pop]{animation:none!important;opacity:1!important}}
</style></head><body><div class="wrap">
<header>
<h1>Who wins Congress — and where we bet against the market</h1>
<p class="lede">A market-anchored forecast for all 470 2026 Congressional races, scored by expected points.
Prices reconstructed from Kalshi, November 1 (unverified). <span class="tnum">__DATE__</span>.</p>
<div class="rule"></div>
</header>

<div class="cards tnum" id="cards"></div>

<h2>Projected control</h2>
<p class="sub">Seats by winning party. Toggle the <b>most-likely winner</b> in each race against <b>our contest picks</b>,
which bet underdogs in genuine tossups. House elects all 435 seats; Senate shows the 35 seats up in 2026.</p>
<div class="controls"><span class="seg" role="group" aria-label="View">
  <button id="seg-likely" aria-pressed="true" onclick="setView('likely')">Most-likely winners</button>
  <button id="seg-picks" aria-pressed="false" onclick="setView('picks')">Our picks</button></span></div>
<div id="chambers" class="grid2"></div>

<h2>The map of our picks</h2>
<p class="sub">Senate as a tile grid (one square per state; states not up in 2026 are muted). House as a seat
spectrum, each cell one district ordered safe-Republican → safe-Democratic. A <span style="color:var(--acc)">gold ring</span>
marks the 63 House + 10 Senate seats where our contest pick is the underdog, not the favorite.</p>
<div class="grid2">
  <div class="panel"><h3>Senate — 35 seats up</h3><div class="meta">colored by our pick's party</div><div class="map" id="senmap"></div>
    <div class="legend"><span><i style="background:var(--d)"></i>Dem pick</span><span><i style="background:var(--r)"></i>Rep pick</span><span><i style="background:var(--i)"></i>Ind pick</span><span><i style="background:#1a2130"></i>not up</span></div></div>
  <div class="panel"><h3>House — 435 districts</h3><div class="meta">ordered safe-R (left) → safe-D (right)</div><div class="spectrum" id="housespec"></div>
    <div class="legend"><span><i style="background:var(--r)"></i>R win</span><span><i style="background:var(--d)"></i>D win</span><span><i style="box-shadow:inset 0 0 0 2px var(--acc);background:transparent"></i>underdog pick</span></div></div>
</div>

<h2>Why the picks look like this</h2>
<p class="sub">Every pick maximizes expected points, <code>q·reward(p)</code>, with <code>reward(p)=-log2(max(0.01,p))</code>.
Each dot is one race: its Nov-1 price <code>p</code> against the expected points we book. Cheap races (left) pay more —
but only if the pick wins, which is why we don't chase the deepest longshots.</p>
<svg id="scatter" class="chart" viewBox="0 0 900 420" role="img" aria-label="Expected points versus November-1 price for every priced race"></svg>

<h2>The trap we avoided</h2>
<p class="sub">Read literally, "maximize expected points" bets the underdog everywhere. On FiveThirtyEight's 2018
final forecasts under this exact rule, that realized <b>23</b> points versus <b>41</b> for favorites — deep longshots
barely hit. So our picks cap longshot bets at a forecast floor of <code>q ≥ 0.15</code>.</p>
<img class="fig" src="__FIG_STRAT__" alt="Left: 2018 realized points — favorites 41, underdog-threshold 24-33, all-underdog 23. Right: underdog picks won far fewer races than their probabilities predicted, especially below 10%.">

<h2>Explore every race</h2>
<p class="sub">Click a row for the reward curve and the per-candidate expected-points breakdown. Sort any column;
filter by chamber or pick type; search a race or candidate.</p>
<div class="controls">
  <input id="q" placeholder="Search a race id or candidate…" aria-label="Search races" oninput="render()">
  <select id="chamber" aria-label="Filter chamber" onchange="render()"><option value="">All chambers</option><option>Senate</option><option>House</option></select>
  <select id="type" aria-label="Filter pick type" onchange="render()"><option value="">All picks</option><option value="favorite">Favorite picks</option><option value="underdog">Underdog picks</option><option value="fallback">Fallbacks</option></select>
</div>
<div class="tablewrap"><table aria-label="All races"><thead><tr>
  <th role="button" tabindex="0" data-k="id">Race</th><th role="button" tabindex="0" data-k="chamber">Chamber</th>
  <th role="button" tabindex="0" data-k="pick">Our pick</th><th role="button" tabindex="0" data-k="pick_party">Party</th>
  <th role="button" tabindex="0" class="tnum" data-k="pick_q">q</th><th role="button" tabindex="0" class="tnum" data-k="pick_p">p</th>
  <th role="button" tabindex="0" class="tnum" data-k="pick_reward">reward</th><th role="button" tabindex="0" class="tnum" data-k="pick_ev">exp. pts</th>
  <th role="button" tabindex="0" data-k="likely">Most likely</th><th role="button" tabindex="0" data-k="type">Type</th>
</tr></thead><tbody id="rows"></tbody></table></div>
<div id="detail" aria-live="polite"></div>

<h2>Strategy comparison</h2>
<p class="sub">Realized-points proxy (538, 2018) and a correlated Monte-Carlo on the 2026 entry under three assumptions
about how calibrated Kalshi's long-tail prices are. "P(best)" = share of simulated elections a strategy tops.</p>
<div id="strattable"></div>

<h2>Method &amp; caveats</h2>
<ul class="sub" style="max-width:76ch">
<li><b style="color:var(--ink)">p</b> — Kalshi yes-bid/ask midpoint, last hourly candle ≤ Nov-1 23:59 ET. Reconstructed, not the organizers' official pull.</li>
<li><b style="color:var(--ink)">q</b> — normalized latest pre-election Kalshi price (more informed; distinct from p).</li>
<li><b style="color:var(--ink)">Selection</b> — argmax <code>q·reward(p)</code> with a 0.15 underdog floor; same rule both tracks.</li>
<li><b style="color:var(--ink)">Coverage</b> — 460/470 priced; 10 flagged fallbacks (KY-SEN + 9 CA same-party seats).</li>
<li><b style="color:var(--ink)">Caveat</b> — the floor is tuned on one low-upset cycle; no fundamentals blend (disclosed).</li>
</ul>
<p><small>Generated offline from cached data. Nothing here is auto-submitted.</small></p>

<div class="tip" id="tip"></div>
<script>
const RACES = __RACES__;
const SUMMARY = __SUMMARY__;
const CHAMBER = __CHAMBER__;
const STRAT = __STRAT__;
const RW=p=>-Math.log2(Math.max(0.01,p));
const partyColor=p=>p==='D'?'#4b8fe3':p==='R'?'#e05a4e':'#6cc18a';
let sortK="id", sortDir=1, chamberView="likely";

/* ---------- metric cards ---------- */
function cards(){
  const s=SUMMARY,h=s.house,se=s.sen;
  document.getElementById('cards').innerHTML=[
    ['Races',s.n+' <span style="color:var(--faint);font-size:14px">· '+s.priced+' priced</span>'],
    ['Favorite picks',s.fav],['Underdog picks',s.und],['Fallbacks',s.fb],
    ['Exp. points (priced)',s.evsum],
    ['Projected House','<span class="win '+(h.D>h.R?'D':'R')+'">D '+h.D+' · R '+h.R+'</span>'],
  ].map(([l,v])=>'<div class="card"><div class="big">'+v+'</div><div class="lbl">'+l+'</div></div>').join('');
}
/* ---------- chamber bars ---------- */
const CH_META={House:{total:435,maj:218,note:"all 435 seats elected in 2026"},
  Senate:{total:35,maj:null,note:"35 of 100 seats up (control also needs ~65 holdovers)"}};
function setView(v){chamberView=v;
  document.getElementById('seg-likely').setAttribute('aria-pressed',v==='likely');
  document.getElementById('seg-picks').setAttribute('aria-pressed',v==='picks');
  renderChambers();}
function renderChambers(){
  const el=document.getElementById('chambers');el.innerHTML='';
  for(const name of ['House','Senate']){
    const c=CHAMBER[name][chamberView],m=CH_META[name],tot=c.D+c.R+c.I||1;
    const lead=c.D>c.R?'D':c.R>c.D?'R':'tie';
    const head=name==='House'?(m.maj?(c.D>=m.maj?'Democratic majority':c.R>=m.maj?'Republican majority':'no majority'):''):('D '+c.D+' · R '+c.R+(c.I?(' · I '+c.I):''));
    const div=document.createElement('div');div.className='panel';
    div.innerHTML='<h3>'+name+' &nbsp;<span class="win '+lead+' tnum">'+head+'</span></h3>'+
      '<div class="meta">'+m.note+'</div><div class="seatbar tnum" role="img" aria-label="'+name+' seats: D '+c.D+', R '+c.R+(c.I?', I '+c.I:'')+'">'+
      '<span class="sD">D '+c.D+'</span><span class="sI">'+(c.I?('I '+c.I):'')+'</span><span class="sR">R '+c.R+'</span>'+
      (m.maj?('<div class="majline" style="left:'+(100*m.maj/m.total).toFixed(1)+'%"><b>'+m.maj+' = majority</b></div>'):'')+'</div>'+
      '<div class="legend"><span><i style="background:var(--d)"></i>Democratic</span>'+(c.I?'<span><i style="background:var(--i)"></i>Independent</span>':'')+'<span><i style="background:var(--r)"></i>Republican</span></div>';
    el.appendChild(div);
    const sp=div.querySelectorAll('.seatbar span');
    requestAnimationFrame(()=>{sp[0].style.width=(100*c.D/tot)+'%';sp[1].style.width=(100*c.I/tot)+'%';sp[2].style.width=(100*c.R/tot)+'%';});
  }
}
/* ---------- Senate tile map ---------- */
const GRID={AK:[0,0],ME:[0,10],VT:[1,9],NH:[1,10],WA:[2,0],ID:[2,1],MT:[2,2],ND:[2,3],MN:[2,4],IL:[2,5],WI:[2,6],MI:[2,7],NY:[2,9],MA:[2,10],OR:[3,0],NV:[3,1],WY:[3,2],SD:[3,3],IA:[3,4],IN:[3,5],OH:[3,6],PA:[3,7],NJ:[3,8],CT:[3,9],RI:[3,10],CA:[4,0],UT:[4,1],CO:[4,2],NE:[4,3],MO:[4,4],KY:[4,5],WV:[4,6],VA:[4,7],MD:[4,8],DE:[4,9],AZ:[5,1],NM:[5,2],KS:[5,3],AR:[5,4],TN:[5,5],NC:[5,6],SC:[5,7],OK:[6,3],LA:[6,4],MS:[6,5],AL:[6,6],GA:[6,7],HI:[7,0],TX:[7,3],FL:[7,8]};
function renderMap(){
  const sen={}; RACES.filter(r=>r.chamber==='Senate').forEach(r=>sen[r.state]=r);
  const el=document.getElementById('senmap');el.innerHTML='';
  Object.keys(GRID).forEach((st,i)=>{
    const [row,col]=GRID[st],r=sen[st];
    const d=document.createElement('div');
    d.className='tile'+(r?'':' off')+(r&&r.pick!==r.likely?' flip':'');
    d.style.gridRow=row+1;d.style.gridColumn=col+1;d.style.animationDelay=(i*8)+'ms';
    if(r)d.setAttribute('data-p',r.pick_party);
    d.textContent=st;
    if(r)bindTip(d,'<b>'+r.id+'</b> — pick '+r.pick+' ('+r.pick_party+')<br>most-likely '+r.likely+' ('+r.likely_party+')');
    else bindTip(d,st+' — not up in 2026');
    el.appendChild(d);
  });
}
/* ---------- House spectrum ---------- */
function renderSpectrum(){
  const h=RACES.filter(r=>r.chamber==='House'&&r.candidates.length).slice().sort((a,b)=>a.dwin-b.dwin);
  const el=document.getElementById('housespec');el.innerHTML='';
  h.forEach(r=>{const c=document.createElement('div');
    c.className='cell'+(r.pick!==r.likely?' flip':'');
    c.setAttribute('data-p',r.likely_party||'R');
    bindTip(c,'<b>'+r.id+'</b> — likely '+r.likely+' ('+r.likely_party+')<br>our pick '+r.pick+' ('+r.pick_party+'), p='+(r.pick_p||'—'));
    el.appendChild(c);});
}
/* ---------- tooltip ---------- */
const tip=document.getElementById('tip');
function bindTip(node,html){
  node.addEventListener('mouseenter',()=>{tip.innerHTML=html;tip.style.opacity=1;});
  node.addEventListener('mousemove',e=>{tip.style.left=Math.min(e.clientX+14,innerWidth-250)+'px';tip.style.top=(e.clientY+16)+'px';});
  node.addEventListener('mouseleave',()=>{tip.style.opacity=0;});
}
/* ---------- EV vs price scatter ---------- */
function renderScatter(){
  const W=900,H=420,L=56,Rm=16,T=16,B=44,pw=W-L-Rm,ph=H-T-B,MAXY=1.7;
  const X=p=>(L+p*pw).toFixed(1),Y=v=>(T+(1-v/MAXY)*ph).toFixed(1);
  let s='';
  [0,.25,.5,.75,1].forEach(p=>{const x=X(p);s+='<line class="grid" x1="'+x+'" y1="'+T+'" x2="'+x+'" y2="'+(T+ph)+'"/><text class="lbl" x="'+x+'" y="'+(H-24)+'" text-anchor="middle">'+p+'</text>';});
  [0,0.5,1,1.5].forEach(v=>{const y=Y(v);s+='<line class="grid" x1="'+L+'" y1="'+y+'" x2="'+(L+pw)+'" y2="'+y+'"/><text class="lbl" x="'+(L-8)+'" y="'+(+y+4)+'" text-anchor="end">'+v.toFixed(1)+'</text>';});
  s+='<line class="axis" x1="'+L+'" y1="'+(T+ph)+'" x2="'+(L+pw)+'" y2="'+(T+ph)+'"/><line class="axis" x1="'+L+'" y1="'+T+'" x2="'+L+'" y2="'+(T+ph)+'"/>';
  // threshold guide at p where favorite flips — informational vertical band q<0.15 region is race-specific; annotate longshot zone
  s+='<text class="lbl" x="'+(L+pw/2)+'" y="'+(H-6)+'" text-anchor="middle">November-1 price p of our pick</text>';
  s+='<text class="lbl" transform="translate(16 '+(T+ph/2)+') rotate(-90)" text-anchor="middle">expected points  q · reward(p)</text>';
  const pts=RACES.filter(r=>r.pick_ev&&r.pick_p);
  pts.forEach((r,i)=>{const x=X(+r.pick_p),y=Y(Math.min(MAXY,+r.pick_ev));const col=partyColor(r.pick_party);
    const dog=r.type==='underdog';
    s+='<circle cx="'+x+'" cy="'+y+'" r="'+(dog?4.2:3.2)+'" fill="'+(dog?col:'none')+'" stroke="'+col+'" stroke-width="1.4" opacity="'+(dog?.92:.72)+'"><title>'+r.id+': pick '+r.pick+', p='+r.pick_p+', EV='+r.pick_ev+'</title></circle>';});
  s+='<text class="lbl" x="'+(L+10)+'" y="'+(T+16)+'" fill="#f0b93e">● filled = underdog bet   ○ hollow = favorite</text>';
  document.getElementById('scatter').innerHTML=s;
}
/* ---------- race table ---------- */
function pill(p){return '<span class="pill '+(p||'')+'">'+(p||'?')+'</span>';}
function render(){
  const q=document.getElementById('q').value.toLowerCase(),ch=document.getElementById('chamber').value,tp=document.getElementById('type').value;
  let rows=RACES.filter(r=>{
    if(ch&&r.chamber!==ch)return false;
    if(tp==='fallback'&&!r.note.includes('FALLBACK'))return false;
    if(tp&&tp!=='fallback'&&r.type!==tp)return false;
    if(q&&!(r.id.toLowerCase().includes(q)||(r.pick||'').toLowerCase().includes(q)||(r.likely||'').toLowerCase().includes(q)))return false;
    return true;});
  rows.sort((a,b)=>{let x=a[sortK],y=b[sortK];const nx=parseFloat(x),ny=parseFloat(y);if(!isNaN(nx)&&!isNaN(ny)){x=nx;y=ny;}return(x>y?1:x<y?-1:0)*sortDir;});
  document.getElementById('rows').innerHTML=rows.map(r=>{const diff=r.pick!==r.likely;
    return '<tr class="race" tabindex="0" onclick="detail('+RACES.indexOf(r)+')" onkeydown="if(event.key===\'Enter\')detail('+RACES.indexOf(r)+')">'+
      '<td><b>'+r.id+'</b></td><td>'+r.chamber+'</td><td>'+(r.pick||'')+(diff?' <span class="dog" title="underdog pick">◆</span>':'')+'</td><td>'+pill(r.pick_party)+'</td>'+
      '<td class="tnum">'+r.pick_q+'</td><td class="tnum">'+(r.pick_p||'—')+'</td><td class="tnum">'+(r.pick_reward||'—')+'</td><td class="tnum">'+(r.pick_ev||'—')+'</td>'+
      '<td><small>'+(r.likely||'')+'</small></td><td class="'+(r.type==='favorite'?'fav':'dog')+'">'+(r.note.includes('FALLBACK')?'fallback':r.type)+'</td></tr>';}).join('');
}
function bar(frac,color){return '<div class="barwrap"><div class="bar" style="width:'+Math.max(2,Math.min(100,frac*100)).toFixed(1)+'%;background:'+color+'"></div></div>';}
function rewardCurve(r){
  const W=600,H=250,L=48,Rm=14,T=14,B=38,pw=W-L-Rm,ph=H-T-B,MAXR=6.644;
  const X=p=>(L+p*pw).toFixed(1),Y=v=>(T+(1-v/MAXR)*ph).toFixed(1);
  const line=(c,x1,y1,x2,y2)=>'<line class="'+c+'" x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" />';
  const txt=(x,y,a,s,ex)=>'<text class="lbl" x="'+x+'" y="'+y+'" text-anchor="'+a+'"'+(ex||'')+'>'+s+'</text>';
  let path='';for(let i=0;i<=100;i++){const p=Math.max(0.0001,i/100);path+=(i?'L':'M')+X(p)+' '+Y(RW(p))+' ';}
  let g='';[0,.25,.5,.75,1].forEach(p=>{const x=X(p);g+=line('grid',x,T,x,T+ph)+txt(x,H-20,'middle',p);});
  [0,2,4,6].forEach(v=>{const y=Y(v);g+=line('grid',L,y,L+pw,y)+txt(L-6,(+y+3).toFixed(1),'end',v);});
  let dots='';r.candidates.filter(c=>c.p>=0.01).forEach((c,i)=>{const x=X(c.p),y=Y(RW(c.p)),isPick=c.name===r.pick,col=partyColor(c.party);
    dots+='<g style="animation:pop .4s ease '+(0.6+i*0.15)+'s both">'+(isPick?'<circle cx="'+x+'" cy="'+y+'" r="9" fill="none" stroke="#f0b93e" stroke-width="2" />':'')+
      '<circle cx="'+x+'" cy="'+y+'" r="5.5" fill="'+col+'" />'+txt(x,(+y-12).toFixed(1),'middle',c.name.split(' ').slice(-1)[0],' fill="#eef2f8" font-weight="700"')+txt(x,(+y+17).toFixed(1),'middle','p='+c.p)+'</g>';});
  return '<svg class="chart rc" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Reward curve for '+r.id+'">'+g+line('axis',L,T+ph,L+pw,T+ph)+line('axis',L,T,L,T+ph)+
    '<path class="curve" d="'+path+'" pathLength="1" />'+dots+txt(L+pw/2,H-4,'middle','Nov-1 price  p  (cheaper = higher reward)')+
    '<text class="lbl" transform="translate(13 '+(T+ph/2)+') rotate(-90)" text-anchor="middle">reward = -log2(max(.01,p))</text></svg>';
}
function detail(idx){
  const r=RACES[idx],d=document.getElementById('detail'),cs=r.candidates.filter(c=>c.p>=0.01);
  const rowsh=cs.map(c=>{const col=partyColor(c.party),isPick=c.name===r.pick;
    return '<div class="crow"><div>'+(isPick?'➤ ':'')+'<b>'+c.name+'</b> '+pill(c.party)+'</div><div class="mini">q='+c.q+' '+bar(c.q,col)+'</div><div class="mini">EV='+c.ev+' '+bar(c.ev/1.5,isPick?'#f0b93e':'#55617a')+'</div></div>';}).join('');
  d.style.display='block';
  d.innerHTML='<h3 style="margin:0 0 4px">'+r.id+' — '+r.chamber+'</h3><p class="sub" style="margin-bottom:10px">Contest pick <b>'+r.pick+'</b> '+pill(r.pick_party)+
    ' · most-likely winner <b>'+r.likely+'</b> '+pill(r.likely_party)+(r.pick!==r.likely?' <span class="dog">— betting the underdog\'s higher reward</span>':' <span class="fav">— same</span>')+(r.note?(' · <small>'+r.note+'</small>'):'')+'</p>'+
    (cs.length?rewardCurve(r)+'<div style="display:grid;grid-template-columns:168px 1fr 1fr;gap:12px;color:var(--faint);font-size:12px;margin-top:12px"><div>Candidate</div><div>Forecast q</div><div>Expected points = q·reward(p)</div></div>'+rowsh:'<p class="sub">No market for this race (documented fallback).</p>');
  d.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function strattable(){
  const cols=['strategy','mean','median','p10','p90','beats_fav','p_best'];
  let h='<div class="tablewrap"><table><thead><tr>'+cols.map(c=>'<th class="'+(c!=='strategy'&&c!=='p_best'&&c!=='beats_fav'?'tnum':'')+'">'+c+'</th>').join('')+'</tr></thead><tbody>';
  for(const row of STRAT)h+='<tr'+(row.strategy.includes('ours')?' style="background:#1b2438"':'')+'>'+cols.map(c=>'<td class="'+(['mean','median','p10','p90'].includes(c)?'tnum':'')+'">'+row[c]+'</td>').join('')+'</tr>';
  document.getElementById('strattable').innerHTML=h+'</tbody></table></div>';
}
document.querySelectorAll('th[data-k]').forEach(th=>{const go=()=>{const k=th.dataset.k;if(sortK===k)sortDir*=-1;else{sortK=k;sortDir=1;}
  document.querySelectorAll('th[data-k]').forEach(t=>t.removeAttribute('aria-sort'));th.setAttribute('aria-sort',sortDir>0?'ascending':'descending');render();};
  th.onclick=go;th.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}};});
cards();renderChambers();renderMap();renderSpectrum();renderScatter();render();strattable();
</script>
</div></body></html>"""


def main():
    import datetime
    races = build_race_data()
    summ = summary(races)
    strat = [
        {"strategy": "favorite", "mean": 44.5, "median": 44.6, "p10": 41.3, "p90": 47.7, "beats_fav": "—", "p_best": "calib .00 · mild .25 · strong .48"},
        {"strategy": "threshold@0.15 (ours)", "mean": 56.9, "median": 56.6, "p10": 47.9, "p90": 66.5, "beats_fav": ".92", "p_best": "calib .00 · mild .27 · strong .10"},
        {"strategy": "threshold@0.25", "mean": 49.8, "median": 49.6, "p10": 43.9, "p90": 55.8, "beats_fav": ".78", "p_best": "calib .00 · mild .16 · strong .16"},
        {"strategy": "all-underdog (pure EV)", "mean": 97.5, "median": 96.4, "p10": 74.1, "p90": 121.9, "beats_fav": "1.0", "p_best": "calib 1.0 · mild .17 · strong .01"},
    ]
    html = (HTML
            .replace("__RACES__", json.dumps(races))
            .replace("__SUMMARY__", json.dumps(summ))
            .replace("__CHAMBER__", json.dumps(chamber_control(races)))
            .replace("__STRAT__", json.dumps(strat))
            .replace("__FIG_STRAT__", b64(os.path.join(OUT, "figure_strategy_evidence.png")))
            .replace("__DATE__", "Generated " + datetime.date.today().isoformat()))
    out = os.path.join(OUT, "report.html")
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(html)
    os.replace(tmp, out)
    print(f"wrote {out} ({os.path.getsize(out)//1024} KB, {len(races)} races)")


if __name__ == "__main__":
    main()
