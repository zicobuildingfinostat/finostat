"""Server-rendered product pages: the /dashboard terminal (and friends).

Each page is a self-contained HTML document in the same visual language as
index.html (indigo desk, gold/cyan accents, IBM Plex Mono). The server injects
a snapshot seed so the first paint shows data instantly; after that the page
rides the same SSE streams the homepage uses.
"""
from __future__ import annotations

import html
import json


def _seed(snapshot: dict) -> str:
    payload = {
        "rows": snapshot.get("sheet", {}).get("rows", []),
        "quotes": snapshot.get("quotes", []),
        "mini": snapshot.get("mini", []),
        "atm": snapshot.get("atm"),
        "straddle": snapshot.get("straddle"),
        "symbol": snapshot.get("symbol", "NIFTY"),
        "live": bool(snapshot.get("live")),
    }
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Finostat Terminal</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0c0626">
<link rel="icon" href="/og.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0c0626;--panel:#120a33;--panel-hd:#1c1052;--violet:#6a35f0;
  --line:#2c1c66;--line-strong:#4a34a0;--gold:#f5c842;--gold-2:#ffe27a;
  --cyan:#7fe0f0;--pink:#ff6ec7;--up:#3dd68c;--down:#ff5c6c;
  --text:#f1edff;--muted:#a89ccf;--faint:#6d609e;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --body:"IBM Plex Sans",system-ui,sans-serif;
  --display:"Barlow Condensed",Impact,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{min-height:100%}
html{background:var(--bg)}
body{color:var(--text);font-family:var(--mono);font-size:12.5px;line-height:1.45;
  display:flex;flex-direction:column;min-height:100vh;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,rgba(200,180,255,.03) 0 1px,transparent 1px 3px)}
a{color:inherit;text-decoration:none}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer;background:none;border:0}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}

/* top bar */
.top{display:flex;align-items:center;gap:14px;height:44px;padding:0 14px;flex-shrink:0;
  background:rgba(12,6,38,.95);border-bottom:1px solid var(--line-strong);position:relative;z-index:2}
.top .logo{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:.14em;text-transform:uppercase;
  background:linear-gradient(180deg,#fff 20%,var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
.top .logo b{color:var(--gold);-webkit-text-fill-color:var(--gold)}
.top .sym{color:var(--cyan);font-size:11.5px;letter-spacing:.08em}
.top .r{margin-left:auto;display:flex;gap:16px;align-items:center;font-size:11px;color:var(--faint);letter-spacing:.06em}
.top .r a:hover{color:var(--gold)}
.live{color:var(--up);display:inline-flex;align-items:center;gap:6px}
.live::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--up);box-shadow:0 0 8px var(--up);animation:pulse 1.6s infinite}
.live.off{color:var(--down)}.live.off::before{background:var(--down);box-shadow:none;animation:none}
@keyframes pulse{50%{opacity:.35}}
.mkt{color:var(--up)}.mkt.closed{color:var(--down)}

/* tape */
.tape{background:#06031a;border-bottom:1px solid var(--line);overflow:hidden;font-size:11.5px;position:relative;z-index:1;white-space:nowrap;flex-shrink:0}
.tape-inner{display:inline-flex;width:max-content;animation:tape 60s linear infinite}
.tape:hover .tape-inner{animation-play-state:paused}
.tape span{padding:6px 18px;border-right:1px solid var(--line);display:inline-flex;gap:9px}
.tape b{color:var(--cyan);font-weight:500}
.tape em{font-style:normal}
@keyframes tape{to{transform:translateX(-50%)}}
.up{color:var(--up)}.down{color:var(--down)}

/* grid */
.desk{flex:1;display:grid;gap:10px;padding:10px;position:relative;z-index:1;
  grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);
  grid-auto-rows:minmax(220px,auto);grid-auto-flow:dense;
  max-width:1500px;margin:0 auto;width:100%}
[hidden]{display:none!important}
.a-sheet{grid-row:span 2;min-height:340px}
.a-side{grid-row:span 2;display:flex;flex-direction:column;gap:10px;min-height:0}
.a-wire{min-height:260px}
.a-chart{grid-column:span 2;min-height:480px}
.br-body{padding:8px 10px;font-size:11.5px;flex:1;display:flex;flex-direction:column;gap:8px}
.br-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.br-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:1px;background:var(--line)}
.br-kpi div{background:var(--panel);padding:6px 10px}.br-kpi small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.br-kpi b{font-family:var(--display);font-size:19px;font-weight:600}
.br-table{width:100%;border-collapse:collapse;font-size:10.5px}.br-table th{text-align:right;font-weight:500;color:var(--faint);font-size:9.5px;letter-spacing:.08em;padding:3px 6px;border-bottom:1px solid var(--line-strong)}.br-table td{padding:3px 6px;text-align:right;white-space:nowrap;border-bottom:1px solid rgba(190,150,255,.07)}
.br-table th:first-child,.br-table td:first-child{text-align:left}.br-table td:first-child{color:var(--cyan)}
.br-h{font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin:4px 0 2px}
.br-btn{font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:5px 10px;border:1px solid var(--line-strong);color:var(--muted);cursor:pointer;background:none;text-decoration:none;display:inline-block}
.br-btn:hover{border-color:var(--gold);color:var(--gold)}.br-btn.primary{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.br-empty{color:var(--faint);line-height:1.5}
.br-msg{font-size:10.5px;color:var(--faint)}.br-msg.bad{color:var(--down)}.br-msg.ok{color:var(--up)}
/* trade ticket */
.tk{position:fixed;inset:0;z-index:950;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(6,3,20,.7)}
.tk[hidden]{display:none}
.tk .card{width:100%;max-width:520px;background:var(--panel);border:1px solid var(--gold);box-shadow:0 30px 80px rgba(0,0,0,.6);font-family:var(--mono)}
.tk .hd{display:flex;gap:10px;padding:8px 12px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.08em;text-transform:uppercase}.tk .hd .k{color:var(--gold);font-weight:600}.tk .hd .x{margin-left:auto;background:none;border:0;color:var(--muted);cursor:pointer;font-size:16px}
.tk .bd{padding:12px 14px;font-size:11.5px}
.tk table{width:100%;border-collapse:collapse;margin:0 0 10px}.tk td,.tk th{padding:4px 6px;text-align:right;border-bottom:1px solid rgba(190,150,255,.08)}.tk th{color:var(--faint);font-weight:500;font-size:9.5px;letter-spacing:.08em}.tk td:first-child,.tk th:first-child{text-align:left}
.tk .opts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 10px}.tk label{display:block;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.tk select,.tk input{width:100%;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:12px;padding:5px 6px}
.tk .warn{font-size:10.5px;color:var(--muted);line-height:1.5;margin:0 0 10px;padding:8px 10px;border-left:3px solid var(--down);background:rgba(255,92,108,.06)}
.tk .warn input{width:auto;margin-right:6px}
.tk .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tk .res{font-size:10.5px;margin-top:8px;line-height:1.5}.tk .res .ok{color:var(--up)}.tk .res .bad{color:var(--down)}
.a-chart .ch-body{flex:1;min-height:420px;background:#06031a}
.a-chart .ch-body>div{height:100%}
.ch-note{color:var(--faint);font-weight:400;letter-spacing:.04em}
.ch-sym{cursor:pointer}
@media (max-width:980px){.a-chart{grid-column:auto;min-height:380px}.a-chart .ch-body{min-height:340px}}
/* layout menu */
.layout{position:relative}
.layout summary{list-style:none;cursor:pointer;letter-spacing:.06em}
.layout summary::-webkit-details-marker{display:none}
.layout summary:hover{color:var(--gold)}
.layout-menu{position:absolute;right:0;top:22px;background:var(--panel);border:1px solid var(--line-strong);
  padding:8px 10px;display:grid;gap:6px;min-width:150px;z-index:20;box-shadow:0 14px 40px rgba(0,0,0,.5)}
.layout-menu label{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:11px;letter-spacing:.06em;cursor:pointer}
.layout-menu input{accent-color:#f5c842}
#who form{display:inline}
#who button{color:var(--faint);letter-spacing:.06em;font-size:11px}
#who button:hover{color:var(--down)}
#who .me{color:var(--cyan);margin-right:8px}
/* watchlist */
.watch{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:1px;background:var(--line);flex:1;align-content:start}
.watch .w{background:var(--panel);padding:10px 12px;position:relative;cursor:pointer}
.watch .w .sym{font-size:10.5px;letter-spacing:.1em;color:var(--cyan)}
.watch .w .px{font-family:var(--display);font-size:26px;line-height:1;margin:4px 0 2px;letter-spacing:.02em}
.watch .w .ch{font-size:11px}
.watch .w button{position:absolute;top:6px;right:8px;color:var(--faint);font-size:11px}
.watch .w button:hover{color:var(--down)}
.watch-add{display:flex;gap:6px;padding:8px 10px;border-top:1px solid var(--line)}
.watch-add select{flex:1;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font-size:11px;padding:5px 6px;min-width:0}
.watch-add button{background:var(--gold);color:#2a1a02;font-weight:600;font-size:10.5px;letter-spacing:.08em;padding:5px 10px}
.watch-empty{padding:12px;color:var(--faint);font-size:11px}
.watch .w .nm{font-size:9.5px;color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.watch .w .fo{font-size:8.5px;letter-spacing:.1em;color:#2a1a02;background:var(--gold);padding:1px 4px;margin-left:5px;vertical-align:middle}
.srch{position:relative;flex:1;min-width:0}
.srch input{width:100%;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font-size:11px;padding:5px 7px;text-transform:uppercase}
.srch input::placeholder{text-transform:none;color:var(--faint)}
.srch-list{position:absolute;left:0;right:0;bottom:100%;margin-bottom:2px;background:var(--panel);border:1px solid var(--line-strong);z-index:15;max-height:220px;overflow-y:auto;box-shadow:0 -10px 30px rgba(0,0,0,.5)}
.srch-list li{display:grid;grid-template-columns:auto 1fr auto;gap:8px;padding:6px 8px;font-size:11px;cursor:pointer;border-bottom:1px solid rgba(190,150,255,.08);align-items:center}
.srch-list li:hover,.srch-list li.sel{background:rgba(106,53,240,.3)}
.srch-list b{color:var(--cyan);font-weight:500}
.srch-list small{color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.srch-list em{font-style:normal;color:var(--gold);font-size:9px;letter-spacing:.1em}
.al-form .srch input{padding:5px 6px}
.n50 tr{cursor:pointer}
.n50 tr:hover td{background:rgba(106,53,240,.18)}
.n50 td:first-child{color:var(--text)}
.n50 td:first-child small{display:block;color:var(--faint);font-size:9.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px}
.n50 td.w{color:var(--gold)}
/* builder */
.bl-top{display:grid;grid-template-columns:1fr auto;gap:6px;padding:8px 10px;border-bottom:1px solid var(--line)}
.bl-top select{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font-size:11px;padding:5px 6px}
.bl-presets{display:flex;flex-wrap:wrap;gap:5px;padding:7px 10px;border-bottom:1px solid var(--line)}
.bl-presets button{font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:4px 8px;border:1px solid var(--line-strong);color:var(--muted)}
.bl-presets button:hover{border-color:var(--gold);color:var(--gold)}
.bl-presets button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
/* Wide tables scroll inside their own box; the page never scrolls sideways. */
.bl-scroll{overflow-x:auto;max-width:100%;scrollbar-width:thin;scrollbar-color:var(--line-strong) transparent}
.bl-legs{min-width:420px}
.bl-legs td,.bl-legs th{padding:4px 8px;white-space:nowrap}
.bl-legs select,.bl-legs input{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font-size:11px;padding:3px 5px;width:100%;min-width:0}
.bl-legs input[type=number]{width:52px}
.bl-legs td.side-b{color:var(--up);font-weight:600}.bl-legs td.side-s{color:var(--down);font-weight:600}
.bl-legs button{color:var(--faint)}.bl-legs button:hover{color:var(--down)}
.bl-tools{display:flex;gap:10px;align-items:center;padding:6px 10px;border-bottom:1px solid var(--line);font-size:10.5px;color:var(--faint)}
.bl-tools button{font-size:10px;letter-spacing:.08em;padding:3px 8px;border:1px solid var(--line-strong);color:var(--muted)}
.bl-tools button:hover{border-color:var(--gold);color:var(--gold)}
.bl-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.bl-metrics div{background:var(--panel);padding:7px 10px}
.bl-metrics small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}
.bl-metrics b{font-family:var(--display);font-size:20px;font-weight:600;letter-spacing:.02em}
.bl-tools button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.bl-oi{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.bl-oi div{background:var(--panel);padding:6px 10px}.bl-oi small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.bl-oi b{font-family:var(--display);font-size:19px;font-weight:600}
.bl-chain{border-bottom:1px solid var(--line)}.bl-chain table{border-collapse:collapse;width:100%;font-size:10.5px;min-width:560px}
.bl-chain th{font-size:9.5px;letter-spacing:.08em;color:var(--faint);font-weight:500;padding:4px 6px;text-align:right;border-bottom:1px solid var(--line-strong)}
.bl-chain td{padding:3px 6px;text-align:right;white-space:nowrap;border-bottom:1px solid rgba(190,150,255,.07);position:relative}
.bl-chain td.k{text-align:center;color:var(--gold);font-weight:600;background:rgba(106,53,240,.12)}.bl-chain tr.atm td{background:rgba(106,53,240,.28)}
.bl-chain td.oi i{position:absolute;top:2px;bottom:2px;z-index:0;opacity:.28}.bl-chain td.ce.oi i{right:0;background:var(--down)}.bl-chain td.pe.oi i{left:0;background:var(--up)}
.bl-chain td.oi span{position:relative;z-index:1}.bl-chain td.px{color:var(--text);cursor:pointer}.bl-chain td.px:hover{color:var(--gold)}
.bl-chain td.wall{box-shadow:inset 0 0 0 1px var(--gold)}.bl-chain .ch{color:var(--muted);font-size:9.5px}
.bl-chain .note{padding:5px 10px;font-size:9.5px;color:var(--faint);letter-spacing:.04em}
.bl-chart{padding:8px 10px 4px}
.bl-chart svg{width:100%;height:130px;display:block}
.bl-axis{display:flex;justify-content:space-between;font-size:9.5px;color:var(--faint);letter-spacing:.06em;margin-top:2px}
.bl-lock{padding:18px 14px;text-align:center}
.bl-lock b{font-family:var(--display);font-size:22px;letter-spacing:.04em;text-transform:uppercase;color:var(--gold)}
.bl-lock p{color:var(--muted);font-family:var(--body);font-size:13px;margin:6px auto 12px;max-width:44ch}
.bl-lock button{background:var(--gold);color:#2a1a02;font-weight:600;font-size:11px;letter-spacing:.1em;padding:8px 14px}
.bl-lock small{display:block;color:var(--faint);margin-top:8px;font-size:10.5px}
.bl-empty{padding:14px 12px;color:var(--faint);font-size:11.5px;line-height:1.5}
.panel{background:var(--panel);border:1px solid var(--line-strong);display:flex;flex-direction:column;min-width:0;min-height:0;box-shadow:0 14px 40px rgba(0,0,0,.35)}
.panel-hd{display:flex;align-items:center;gap:12px;padding:6px 11px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.06em;flex-shrink:0}
.panel-hd .k{color:var(--gold);font-weight:600}
.panel-hd .s{color:var(--cyan)}
.panel-hd .r{margin-left:auto;color:var(--faint);display:flex;gap:10px;align-items:center}
.scroll{overflow-y:auto;flex:1;min-height:0;scrollbar-width:thin;scrollbar-color:var(--line-strong) transparent}

/* tables */
table{width:100%;border-collapse:collapse}
th{font-weight:500;color:var(--cyan);text-align:right;padding:6px 11px;border-bottom:1px solid var(--line);font-size:10.5px;letter-spacing:.08em;position:sticky;top:0;background:var(--panel);z-index:1}
th:first-child,td:first-child{text-align:left}
td{padding:5px 11px;text-align:right;border-bottom:1px solid rgba(190,150,255,.08);font-variant-numeric:tabular-nums;transition:background .4s,color .4s}
td:first-child{color:var(--gold)}
tr.atm td{background:rgba(106,53,240,.25)}
tr.atm td:first-child::after{content:" ATM";color:var(--faint);font-size:9.5px}
td.flash-up{background:rgba(61,214,140,.2);color:var(--up)}
td.flash-down{background:rgba(255,92,108,.2);color:var(--down)}

/* straddle chart */
.chart{padding:8px 10px 4px;flex:1;display:flex;flex-direction:column;min-height:96px}
.chart svg{width:100%;flex:1;min-height:0}
.chart .legend{display:flex;justify-content:space-between;font-size:10px;color:var(--faint);letter-spacing:.06em;margin-top:2px}
.chart .legend b{color:var(--gold);font-weight:500}

/* alerts */
.al-form{display:grid;grid-template-columns:1.2fr .9fr .55fr .8fr auto auto;gap:6px;padding:9px 10px;border-bottom:1px solid var(--line);align-items:center}
.al-mail{display:flex;align-items:center;gap:4px;color:var(--muted);font-size:12px;cursor:pointer;white-space:nowrap}
.al-mail input{accent-color:#f5c842}
.al-list small.fv{color:var(--gold)}
.al-form select,.al-form input{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font-size:11px;padding:5px 6px;min-width:0}
.al-form button{background:var(--gold);color:#2a1a02;font-weight:600;font-size:10.5px;letter-spacing:.08em;padding:5px 10px}
.al-form button:hover{filter:brightness(1.1)}
.al-list li{display:grid;grid-template-columns:1fr auto auto;gap:8px;padding:7px 10px;border-bottom:1px solid rgba(190,150,255,.08);align-items:center;font-size:11.5px}
.al-list b{color:var(--text);font-weight:500}
.al-list small{color:var(--faint);display:block;font-size:10px;margin-top:1px}
.al-list .tag{font-size:9.5px;letter-spacing:.08em;padding:2px 6px;border:1px solid var(--line-strong);color:var(--muted);white-space:nowrap}
.al-list .tag.hot{color:var(--up);border-color:var(--up)}
.al-list .tag.fired{color:var(--gold);border-color:var(--gold);animation:pulse 1.2s infinite}
.al-list button{color:var(--faint);font-size:10px;letter-spacing:.06em}
.al-list button:hover{color:var(--down)}
.al-list button.rearm:hover{color:var(--gold)}
.al-log{border-top:1px solid var(--line)}
.al-log li{padding:5px 10px;border-bottom:1px solid rgba(190,150,255,.06);font-size:10.5px;color:var(--muted);display:flex;gap:8px}
.al-log time{color:var(--faint)}
.al-empty{padding:12px 10px;color:var(--faint);font-size:11px}
.al-tools{display:flex;gap:8px;padding:6px 10px;border-top:1px solid var(--line)}
.al-tools button{font-size:10px;letter-spacing:.08em;color:var(--muted);border:1px solid var(--line-strong);padding:3px 8px}
.al-tools button:hover{color:var(--gold);border-color:var(--gold)}
.al-tools button.on{color:var(--up);border-color:var(--up)}

/* wire */
.wire-list li{display:grid;grid-template-columns:42px 1fr;gap:9px;padding:7px 11px;border-bottom:1px solid rgba(190,150,255,.08);align-items:baseline}
.wire-list li:hover{background:rgba(106,53,240,.15)}
.wire-list li.new{animation:wire-in .9s ease-out}
@keyframes wire-in{from{background:rgba(245,200,66,.25)}}
.wire-list time{color:var(--faint);font-variant-numeric:tabular-nums;font-size:10.5px}
.wire-list a{font-family:var(--body);font-size:12.5px;color:var(--text);line-height:1.35;display:block}
.wire-list a:hover{color:var(--gold)}
.wire-list .meta{display:flex;gap:8px;margin-top:2px;font-size:9.5px;letter-spacing:.08em;color:var(--faint)}
.wire-list .meta .tag{color:var(--cyan)}
.wire-list .meta .tag.fin{color:var(--gold)}
.wire-list li.hot .meta::before{content:"BREAKING";color:var(--pink);font-weight:600}

@media (max-width:560px){
  .bl-top{grid-template-columns:1fr}
  .bl-legs td,.bl-legs th{padding:4px 5px}
  .bl-legs input[type=number]{width:46px}
  .top{flex-wrap:wrap;height:auto;min-height:44px;padding:6px 10px;row-gap:2px;gap:10px}
  .top .sym{display:none}
  .top .r{gap:10px;flex-wrap:wrap}
}
@media (max-width:980px){
  .desk{grid-template-columns:1fr;grid-auto-flow:row}
  .a-sheet,.a-side{grid-row:auto}
  .al-form{grid-template-columns:1fr 1fr;grid-auto-rows:auto}
  .al-form button{grid-column:1/-1}
}
@media (prefers-reduced-motion:reduce){.tape-inner{animation:none}.live::before{animation:none}}
</style>
</head>
<body>

<header class="top">
  <a class="logo" href="/">FINO<b>·</b>TERMINAL</a>
  <span class="sym" id="t-sym">NIFTY · NEAREST EXPIRY</span>
  <div class="r">
    <span class="live off" id="conn">CONNECTING</span>
    <span id="clock">--:--:-- IST</span>
    <span class="mkt" id="mkt">NSE —</span>
    <details class="layout"><summary>LAYOUT</summary>
      <div class="layout-menu" id="layout-menu"></div>
    </details>
    <span id="who"><a href="/login">SIGN IN</a></span>
    <a href="/">← SITE</a>
  </div>
</header>

<div class="tape" aria-label="Market ticker"><div class="tape-inner" id="tape"></div></div>

<main class="desk">
<div class="tk" id="tk" hidden role="dialog" aria-label="Order ticket"><div class="card"><div class="hd"><span class="k">TICKET</span><span id="tk-title">ORDER</span><button class="x" type="button" id="tk-x" aria-label="Close">×</button></div>
  <div class="bd"><table><thead><tr><th>LEG</th><th>SIDE</th><th>QTY/LOT</th><th>LTP</th><th>LIMIT</th></tr></thead><tbody id="tk-legs"></tbody></table>
  <div class="opts"><div><label>Lots</label><input id="tk-lots" type="number" min="1" max="50" value="1"></div><div><label>Product</label><select id="tk-product"><option value="D">NRML (carry)</option><option value="I">Intraday</option></select></div><div><label>Order type</label><select id="tk-type"><option>LIMIT</option></select></div></div>
  <div class="br-msg" style="margin:-4px 0 8px">Upstox accepts only limit orders over the API (SEBI rule since Apr 2026). Prices are prefilled at the last traded price — edit them before sending.</div>
  <div class="warn"><label style="display:flex;align-items:center;gap:6px;text-transform:none;letter-spacing:0;font-size:11px;color:var(--text)"><input type="checkbox" id="tk-confirm"> I am sending these orders to my own broker account. Finostat transmits them exactly as shown; my broker executes them and its margins and charges apply.</label></div>
  <div class="row"><button type="button" class="br-btn primary" id="tk-send">SEND TO BROKER</button><button type="button" class="br-btn" id="tk-cancel">Cancel</button><span class="br-msg" id="tk-msg"></span></div>
  <div class="res" id="tk-res"></div></div></div></div>

  <section class="panel a-sheet" id="p-sheet" aria-label="Butterfly sheet">
    <div class="panel-hd"><span class="k">BFLY</span><span class="s" id="sheet-sym">NIFTY</span><span>1:2:1</span>
      <span class="r"><span id="sheet-note">seeded</span></span></div>
    <div class="scroll"><table>
      <thead><tr><th>STRIKE</th><th>CE</th><th>PE</th><th>BFLY</th><th>NET</th></tr></thead>
      <tbody id="rows"></tbody>
    </table></div>
  </section>

  <div class="a-side">
    <section class="panel" style="flex:1" id="p-straddle" aria-label="ATM straddle">
      <div class="panel-hd"><span class="k">STRD</span><span class="s">ATM STRADDLE</span>
        <span class="r"><b id="strd-last" style="color:var(--gold)">—</b></span></div>
      <div class="chart">
        <svg viewBox="0 0 300 110" preserveAspectRatio="none" aria-hidden="true">
          <path id="strd-area" fill="rgba(245,200,66,.12)"></path>
          <path id="strd-line" fill="none" stroke="var(--gold)" stroke-width="1.6"></path>
        </svg>
        <div class="legend"><span id="strd-min">—</span><span>session</span><span id="strd-max">—</span></div>
      </div>
    </section>

    <section class="panel" style="flex:1.25" id="p-alerts" aria-label="Alerts">
      <div class="panel-hd"><span class="k">ALRT</span><span class="s" id="al-mode">MY ALERTS · LOCAL</span>
        <span class="r"><span id="al-count">0 ARMED</span></span></div>
      <form class="al-form" id="al-form">
        <select id="al-metric"></select>
        <div class="al-slot"><select id="al-strike" disabled><option value="">strike…</option></select><div class="srch" id="al-stock-wrap" hidden><input id="al-stock-q" placeholder="stock…" aria-label="Search stock"><ul class="srch-list" id="al-stock-res" hidden></ul></div></div>
        <select id="al-cmp"><option value=">=">≥</option><option value="<=">≤</option></select>
        <input id="al-value" type="number" step="any" placeholder="value" required>
        <label class="al-mail" id="al-mail-wrap" hidden title="Email me when this fires"><input type="checkbox" id="al-email" checked> ✉</label>
        <button type="submit">ARM</button>
      </form>
      <ul class="al-list scroll" id="al-list" style="flex:1.2"></ul>
      <ul class="al-log scroll" id="al-log" style="flex:1;max-height:110px"></ul>
      <div class="al-tools">
        <button type="button" id="al-notif">ENABLE DESKTOP ALERTS</button>
        <button type="button" id="al-sound">SOUND: ON</button>
      </div>
    </section>
  </div>

  <section class="panel a-chart" id="p-chart" aria-label="Chart">
    <div class="panel-hd"><span class="k">CHRT</span><span class="s" id="ch-sym">NSE:NIFTY</span><span class="ch-note" id="ch-note">click any symbol on the desk to chart it · TradingView</span>
      <span class="r"><a href="https://www.tradingview.com/" target="_blank" rel="noopener" style="color:var(--faint)">tradingview.com</a></span></div>
    <div class="ch-body"><div id="tv-chart"></div></div>
  </section>
  <section class="panel" id="p-watch" aria-label="Watchlist">
    <div class="panel-hd"><span class="k">WATCH</span><span class="s">MY WATCHLIST</span>
      <span class="r"><span id="watch-sync">local</span></span></div>
    <div class="watch scroll" id="watch"></div>
    <form class="watch-add" id="watch-add" autocomplete="off"><div class="srch"><input id="watch-q" placeholder="search NSE stock or index…" aria-label="Search symbols"><ul class="srch-list" id="watch-res" hidden></ul></div><button type="submit">ADD</button></form>
  </section>

  <section class="panel" id="p-builder" aria-label="Strategy builder">
    <div class="panel-hd"><span class="k">BLDR</span><span class="s" id="bl-title">STRATEGY BUILDER</span>
      <span class="r"><span id="bl-status">pick an underlying</span></span></div>
    <div class="bl-top">
      <div class="srch"><input id="bl-u" placeholder="underlying: NIFTY 50, BANKNIFTY, RELIANCE…" aria-label="Underlying"><ul class="srch-list" id="bl-u-res" hidden></ul></div>
      <select id="bl-exp" aria-label="Expiry" disabled><option>expiry…</option></select>
    </div>
    <div class="bl-presets" id="bl-presets"></div>
    <div class="bl-body" id="bl-body" hidden>
      <div class="bl-scroll"><table class="bl-legs"><thead><tr><th>SIDE</th><th>QTY</th><th>TYPE</th><th>STRIKE</th><th>LTP</th><th>IV</th><th>Δ</th><th></th></tr></thead>
        <tbody id="bl-legs"></tbody></table></div>
      <div class="bl-tools"><button type="button" id="bl-add">+ LEG</button><button type="button" id="bl-chain-btn" title="Option chain with open interest">CHAIN</button><button type="button" id="bl-trade" title="Send these legs to your connected broker">TRADE</button><span id="bl-lot"></span></div>
      <div class="bl-oi" id="bl-oi" hidden></div>
      <div class="bl-chain" id="bl-chain" hidden><div class="bl-scroll"><table><thead><tr><th>OI</th><th>ΔOI</th><th>IV</th><th>CE</th><th>STRIKE</th><th>PE</th><th>IV</th><th>ΔOI</th><th>OI</th></tr></thead><tbody id="bl-chain-rows"></tbody></table></div><div class="note" id="bl-chain-note"></div></div>
      <div class="bl-metrics" id="bl-metrics"></div>
      <div class="bl-chart"><svg id="bl-payoff" viewBox="0 0 320 130" preserveAspectRatio="none" aria-label="Payoff at expiry"></svg>
        <div class="bl-axis" id="bl-axis"></div></div>
    </div>
    <div class="bl-lock" id="bl-lock" hidden>
      <b id="bl-lock-title">Desk plan</b><p id="bl-lock-text"></p>
      <button type="button" id="bl-lock-btn">REQUEST UPGRADE</button>
      <small id="bl-lock-note"></small>
    </div>
    <div class="bl-empty" id="bl-empty">Search an index or any F&amp;O stock above, pick a preset, then edit the legs. Prices, IV and greeks are live from the chain.</div>
  </section>

  <section class="panel" id="p-broker" aria-label="Broker">
    <div class="panel-hd"><span class="k">BRKR</span><span class="s" id="br-title">BROKER</span><span class="r"><span id="br-status">—</span></span></div>
    <div class="br-body" id="br-body"><div class="br-empty">loading…</div></div>
  </section>
  <section class="panel" id="p-n50" aria-label="Nifty 50 constituents">
    <div class="panel-hd"><span class="k">N50</span><span class="s">NIFTY 50 · CONSTITUENTS</span>
      <span class="r"><span id="n50-note">—</span></span></div>
    <div class="scroll"><table class="n50"><thead><tr><th>SYMBOL</th><th>LTP</th><th>CHG</th></tr></thead>
      <tbody id="n50-rows"><tr><td colspan="3" style="color:var(--faint)">loading constituents…</td></tr></tbody></table></div>
  </section>

  <section class="panel a-wire" id="p-wire" aria-label="News wire">
    <div class="panel-hd"><span class="k">WIRE</span><span class="s">FIN · GEO</span>
      <span class="r"><span class="live off" id="wire-live">RSS</span></span></div>
    <ul class="wire-list scroll" id="wire-list"></ul>
  </section>

  <section class="panel" id="p-mini" aria-label="Mini sheet">
    <div class="panel-hd"><span class="k">MINI</span><span class="s" id="mini-sym">BANKNIFTY · BUY/SELL</span></div>
    <div class="scroll"><table>
      <thead><tr><th>STRIKE</th><th>BUY</th><th>SELL</th><th>Δ</th></tr></thead>
      <tbody id="mini-rows"></tbody>
    </table></div>
  </section>

</main>

<script>window.SEED=__SEED__;</script>
<script>
(function(){
"use strict";
var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
var fmt = function(n,d){ return n.toLocaleString('en-IN',{minimumFractionDigits:d==null?2:d,maximumFractionDigits:d==null?2:d}); };

/* ---------- state ---------- */
var state = { rows:[], quotes:[], mini:[], atm:null, straddle:null, symbol:'NIFTY', live:false, lastEvent:0 };

/* ---------- tape ---------- */
var tapeEl = document.getElementById('tape');
function renderTape(qs){
  if(!qs || !qs.length) return;
  var b = qs.map(function(x){
    return '<span><b>'+x.symbol+'</b>'+fmt(x.price)+'<em class="'+(x.change>=0?'up':'down')+'">'+(x.change>=0?'▲':'▼')+' '+Math.abs(x.change).toFixed(2)+'%</em></span>';
  }).join('');
  tapeEl.innerHTML = b + b;
}

/* ---------- sheet ---------- */
var rowsEl = document.getElementById('rows');
var cellIndex = {};
function renderSheet(rows, atm){
  rowsEl.innerHTML = rows.map(function(r){
    var atmCls = (r[0]===atm) ? ' class="atm"' : '';
    var net = r[4];
    return '<tr'+atmCls+' data-k="'+r[0]+'"><td>'+r[0]+'</td>'
      + [1,2,3].map(function(j){ return '<td data-c="'+j+'">'+r[j].toFixed(1)+'</td>'; }).join('')
      + '<td data-c="4" class="'+(net>0?'up':net<0?'down':'')+'">'+net.toFixed(1)+'</td></tr>';
  }).join('');
  cellIndex = {};
  Array.prototype.forEach.call(rowsEl.querySelectorAll('tr'), function(tr){
    var k = tr.getAttribute('data-k');
    Array.prototype.forEach.call(tr.querySelectorAll('td[data-c]'), function(td){
      cellIndex[k+':'+td.getAttribute('data-c')] = td;
    });
  });
}
function applySheet(rows, atm){
  var sameShape = state.rows.length===rows.length && state.rows.every(function(r,i){ return r[0]===rows[i][0]; });
  if(!sameShape || state.atm!==atm){ renderSheet(rows, atm); state.rows=rows; state.atm=atm; return; }
  rows.forEach(function(r,i){
    for(var j=1;j<=4;j++){
      var nv=r[j], ov=state.rows[i][j];
      if(nv===ov) continue;
      var cell=cellIndex[r[0]+':'+j];
      if(!cell) continue;
      cell.textContent=nv.toFixed(1);
      if(j===4){ cell.classList.toggle('up',nv>0); cell.classList.toggle('down',nv<0); }
      if(!reduce){
        cell.classList.remove('flash-up','flash-down'); void cell.offsetWidth;
        cell.classList.add(nv>=ov?'flash-up':'flash-down');
        (function(c){ setTimeout(function(){ c.classList.remove('flash-up','flash-down'); },500); })(cell);
      }
    }
  });
  state.rows=rows;
}

/* ---------- mini ---------- */
var miniEl = document.getElementById('mini-rows');
function renderMini(mini){
  if(!mini || !mini.length){ miniEl.innerHTML='<tr><td colspan="4" style="color:var(--faint)">waiting for feed…</td></tr>'; return; }
  miniEl.innerHTML = mini.map(function(r){
    var d = r[1]+r[2];
    return '<tr><td>'+r[0]+'</td><td>'+r[1].toFixed(1)+'</td><td class="down">'+r[2].toFixed(1)+'</td><td class="'+(d>=0?'up':'down')+'">'+d.toFixed(1)+'</td></tr>';
  }).join('');
}

/* ---------- straddle chart ---------- */
var pts=[], lineEl=document.getElementById('strd-line'), areaEl=document.getElementById('strd-area');
var lastEl=document.getElementById('strd-last'), minEl=document.getElementById('strd-min'), maxEl=document.getElementById('strd-max');
function pushStraddle(v){
  if(v==null) return;
  if(pts.length && Math.abs(pts[pts.length-1]-v)<1e-9) return;
  pts.push(v); if(pts.length>300) pts.shift();
  drawStraddle();
}
function drawStraddle(){
  if(pts.length<2){ if(pts.length===1) lastEl.textContent='₹'+pts[0].toFixed(1); return; }
  var min=Math.min.apply(null,pts), max=Math.max.apply(null,pts), span=(max-min)||1;
  var X=function(i){ return (i/(pts.length-1))*300; }, Y=function(p){ return 104-((p-min)/span)*94; };
  var d=pts.map(function(p,i){ return (i?'L':'M')+X(i).toFixed(1)+' '+Y(p).toFixed(1); }).join(' ');
  lineEl.setAttribute('d',d);
  areaEl.setAttribute('d',d+' L300 108 L0 108 Z');
  lastEl.textContent='₹'+pts[pts.length-1].toFixed(1);
  minEl.textContent='low ₹'+min.toFixed(1); maxEl.textContent='high ₹'+max.toFixed(1);
}

/* ---------- alerts ---------- */
var LS_KEY='fino_alerts_v1';
var alerts=[]; try{ alerts=JSON.parse(localStorage.getItem(LS_KEY)||'[]')||[]; }catch(e){}
var soundOn=true; try{ soundOn=localStorage.getItem('fino_alert_sound')!=='off'; }catch(e){}
var alForm=document.getElementById('al-form'), alMetric=document.getElementById('al-metric'),
    alStrike=document.getElementById('al-strike'), alCmp=document.getElementById('al-cmp'),
    alValue=document.getElementById('al-value'), alList=document.getElementById('al-list'),
    alLog=document.getElementById('al-log'), alCount=document.getElementById('al-count'),
    alNotif=document.getElementById('al-notif'), alSound=document.getElementById('al-sound');

var METRICS=[
  {id:'spot:NIFTY 50', label:'NIFTY spot', strike:false},
  {id:'spot:BANKNIFTY', label:'BANKNIFTY spot', strike:false},
  {id:'spot:SENSEX', label:'SENSEX spot', strike:false},
  {id:'spot:INDIA VIX', label:'INDIA VIX', strike:false},
  {id:'straddle', label:'ATM straddle', strike:false},
  {id:'bfly', label:'BFLY @ strike', strike:true},
  {id:'net', label:'NET @ strike', strike:true},
  {id:'stock', label:'Stock spot (search)', strike:false, stock:true}
];
alMetric.innerHTML=METRICS.map(function(m){ return '<option value="'+m.id+'">'+m.label+'</option>'; }).join('');
var alStockWrap=document.getElementById('al-stock-wrap');
alMetric.addEventListener('change',function(){
  var m=METRICS.filter(function(x){ return x.id===alMetric.value; })[0];
  alStrike.disabled=!m.strike;
  alStrike.hidden=!!m.stock; alStockWrap.hidden=!m.stock;
});
function refreshStrikes(){
  var cur=alStrike.value;
  alStrike.innerHTML='<option value="">strike…</option>'+state.rows.map(function(r){
    return '<option value="'+r[0]+'"'+(String(r[0])===cur?' selected':'')+'>'+r[0]+'</option>';
  }).join('');
}
var stockQuotes={};
function metricValue(id, strike){
  if(id.indexOf('spot:')===0){
    var sym=id.slice(5);
    var q=(state.quotes||[]).filter(function(x){ return x.symbol===sym; })[0];
    if(q) return q.price;
    return stockQuotes[sym]?stockQuotes[sym].price:null;
  }
  if(id==='straddle') return state.straddle;
  var row=(state.rows||[]).filter(function(r){ return r[0]===Number(strike); })[0];
  if(!row) return null;
  return id==='bfly'?row[3]:id==='net'?row[4]:null;
}
function metricLabel(a){
  if(a.metric.indexOf('spot:')===0) return a.metric.slice(5)+' spot';
  var m=METRICS.filter(function(x){ return x.id===a.metric; })[0];
  return (m?m.label.replace(' @ strike',''):a.metric)+(a.strike?' '+a.strike:'');
}
function saveAlerts(){ try{ localStorage.setItem(LS_KEY,JSON.stringify(alerts)); }catch(e){} }
function renderAlerts(){
  var armed=alerts.filter(function(a){ return a.state==='armed'; }).length;
  alCount.textContent=armed+' ARMED';
  if(!alerts.length){ alList.innerHTML='<li class="al-empty">No alerts. Arm one above — it fires the moment the live feed crosses your level.</li>'; return; }
  alList.innerHTML=alerts.map(function(a,i){
    var cur=metricValue(a.metric,a.strike);
    var tag=a.state==='fired'?'<span class="tag fired">FIRED</span>':'<span class="tag hot">ARMED</span>';
    var act=a.state==='fired'?'<button class="rearm" data-i="'+i+'" data-act="rearm">RE-ARM</button>':'';
    return '<li><div><b>'+metricLabel(a)+' '+(a.cmp==='>='?'≥':'≤')+' '+a.value+'</b>'
      +'<small>now '+(cur==null?'—':cur.toFixed(2))+'</small></div>'+tag
      +'<span>'+act+' <button data-i="'+i+'" data-act="del">✕</button></span></li>';
  }).join('');
}
alList.addEventListener('click',function(e){
  var b=e.target.closest('button'); if(!b) return;
  if(serverAlerts){
    var id=b.getAttribute('data-id'); if(!id) return;
    srvPost('/api/alerts/'+id+'/'+b.getAttribute('data-act')).then(loadServerAlerts);
    return;
  }
  var i=Number(b.getAttribute('data-i'));
  if(b.getAttribute('data-act')==='del') alerts.splice(i,1);
  else if(b.getAttribute('data-act')==='rearm') alerts[i].state='armed';
  saveAlerts(); renderAlerts();
});
var alStockSearch=searchWidget(document.getElementById('al-stock-q'), document.getElementById('al-stock-res'), null);
alForm.addEventListener('submit',function(e){
  e.preventDefault();
  var m=METRICS.filter(function(x){ return x.id===alMetric.value; })[0];
  if(m.strike && !alStrike.value){ alStrike.focus(); return; }
  var v=parseFloat(alValue.value); if(isNaN(v)) return;
  var metricId=alMetric.value;
  if(m.stock){
    var hit=alStockSearch.picked()||alStockSearch.first();
    if(!hit){ document.getElementById('al-stock-q').focus(); return; }
    metricId='spot:'+hit.key;
  }
  if(serverAlerts){
    srvPost('/api/alerts',{metric:metricId,strike:m.strike?Number(alStrike.value):null,cmp:alCmp.value,value:v,email:alEmail.checked})
      .then(function(r){ if(r&&r.error){ logAlert('Not armed: '+r.error); } alValue.value=''; if(m.stock) alStockSearch.clear(); loadServerAlerts(); pollStocks(); });
    return;
  }
  alerts.push({metric:metricId,strike:m.strike?Number(alStrike.value):null,cmp:alCmp.value,value:v,state:'armed',created:Date.now()});
  alValue.value=''; if(m.stock) alStockSearch.clear(); saveAlerts(); renderAlerts(); pollStocks();
});
function beep(){
  if(!soundOn) return;
  try{
    var ctx=beep.ctx||(beep.ctx=new (window.AudioContext||window.webkitAudioContext)());
    var o=ctx.createOscillator(), g=ctx.createGain();
    o.frequency.value=880; o.type='sine'; g.gain.value=0.06;
    o.connect(g); g.connect(ctx.destination); o.start();
    g.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+0.35);
    o.stop(ctx.currentTime+0.4);
  }catch(e){}
}
function logAlert(msg, ts){
  var li=document.createElement('li');
  var t=new Date(ts?ts*1000:Date.now()).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false});
  li.innerHTML='<time>'+t+'</time><span>'+msg+'</span>';
  alLog.prepend(li);
  while(alLog.children.length>40) alLog.lastElementChild.remove();
}
function evalAlerts(){
  if(serverAlerts){ return; }
  var fired=false;
  alerts.forEach(function(a){
    if(a.state!=='armed') return;
    var cur=metricValue(a.metric,a.strike);
    if(cur==null) return;
    var hit=a.cmp==='>=' ? cur>=a.value : cur<=a.value;
    if(!hit) return;
    a.state='fired'; fired=true;
    var msg=metricLabel(a)+' crossed '+a.value+' (now '+cur.toFixed(2)+')';
    logAlert(msg); beep();
    if('Notification' in window && Notification.permission==='granted'){
      try{ new Notification('Finostat alert',{body:msg,icon:'/og.jpg'}); }catch(e){}
    }
  });
  if(fired){ saveAlerts(); renderAlerts(); }
}
alNotif.addEventListener('click',function(){
  if(!('Notification' in window)){ alNotif.textContent='NOT SUPPORTED'; return; }
  Notification.requestPermission().then(function(p){
    alNotif.textContent = p==='granted' ? 'DESKTOP ALERTS ON' : 'DESKTOP ALERTS BLOCKED';
    alNotif.classList.toggle('on', p==='granted');
  });
});
if('Notification' in window && Notification.permission==='granted'){
  alNotif.textContent='DESKTOP ALERTS ON'; alNotif.classList.add('on');
}
alSound.addEventListener('click',function(){
  soundOn=!soundOn;
  alSound.textContent='SOUND: '+(soundOn?'ON':'OFF');
  try{ localStorage.setItem('fino_alert_sound',soundOn?'on':'off'); }catch(e){}
});
alSound.textContent='SOUND: '+(soundOn?'ON':'OFF');

/* ---------- wire ---------- */
var wireList=document.getElementById('wire-list'), wireLive=document.getElementById('wire-live');
function hhmm(ts){ return new Date(ts*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false}); }
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function ingestNews(items){
  items.sort(function(a,b){ return a.ts-b.ts; }).forEach(function(n){
    if(wireList.querySelector('a[href="'+CSS.escape(n.url)+'"]')) return;
    var li=document.createElement('li');
    li.className=(n.hot?'hot ':'')+'new';
    li.innerHTML='<time>'+hhmm(n.ts)+'</time><div><a href="'+esc(n.url)+'" target="_blank" rel="noopener">'+esc(n.text)+'</a>'
      +'<div class="meta"><span class="tag '+esc(n.category.toLowerCase())+'">'+esc(n.category)+'</span><span>'+esc(n.handle)+'</span></div></div>';
    wireList.prepend(li);
  });
  while(wireList.children.length>80) wireList.lastElementChild.remove();
}

/* ---------- symbol search widget ---------- */
function searchWidget(input, list, onPick){
  var timer=null, items=[], sel=-1, picked=null;
  function render(){
    if(!items.length){ list.hidden=true; list.innerHTML=''; return; }
    list.innerHTML=items.map(function(x,i){
      return '<li data-i="'+i+'"'+(i===sel?' class="sel"':'')+'><b>'+esc(x.key)+'</b><small>'+esc(x.name||'')+'</small>'+(x.fo&&x.exchange!=='INDEX'?'<em>F&amp;O</em>':'')+'</li>';
    }).join('');
    list.hidden=false;
  }
  function choose(i){ if(i<0||i>=items.length) return; picked=items[i]; input.value=picked.key; items=[]; render(); if(onPick) onPick(picked); }
  input.addEventListener('input',function(){
    picked=null; clearTimeout(timer);
    var q=input.value.trim(); if(!q){ items=[]; render(); return; }
    timer=setTimeout(function(){
      fetch('/api/symbols?q='+encodeURIComponent(q)+'&limit=8').then(function(r){ return r.json(); })
        .then(function(res){ items=res||[]; sel=items.length?0:-1; render(); }).catch(function(){});
    },150);
  });
  input.addEventListener('keydown',function(e){
    if(list.hidden) return;
    if(e.key==='ArrowDown'){ sel=Math.min(items.length-1,sel+1); render(); e.preventDefault(); }
    else if(e.key==='ArrowUp'){ sel=Math.max(0,sel-1); render(); e.preventDefault(); }
    else if(e.key==='Enter'){ choose(sel); e.preventDefault(); }
    else if(e.key==='Escape'){ items=[]; render(); }
  });
  list.addEventListener('mousedown',function(e){ var li=e.target.closest('li[data-i]'); if(li){ choose(Number(li.getAttribute('data-i'))); e.preventDefault(); } });
  input.addEventListener('blur',function(){ setTimeout(function(){ items=[]; render(); },120); });
  return { picked:function(){ return picked; }, first:function(){ return items[0]||null; }, clear:function(){ picked=null; input.value=''; items=[]; render(); } };
}

/* ---------- account, prefs, watchlist, layout ---------- */
var PANELS=[['sheet','BFLY sheet'],['chart','Chart'],['straddle','Straddle chart'],['alerts','Alerts'],['watch','Watchlist'],['builder','Strategy builder'],['broker','Broker'],['n50','Nifty 50'],['wire','News wire'],['mini','Mini sheet']];
/* ---------- broker panel ---------- */
var brBody=document.getElementById('br-body'), brStatus=document.getElementById('br-status'), brTitle=document.getElementById('br-title');
var brState={data:null,timer:null};
function money(v){ return v==null?'—':(v<0?'-':'')+'₹'+fmt(Math.abs(v),0); }
function renderBroker(d){
  brState.data=d;
  var up=(d.brokers||[]).filter(function(b){ return b.id==='upstox'; })[0]||{};
  if(!d.configured){ brBody.innerHTML='<div class="br-empty">Broker connections are not switched on yet.</div>'; brStatus.textContent='off'; return; }
  if(!up.connected){ brStatus.textContent='not connected'; brTitle.textContent='BROKER';
    brBody.innerHTML='<div class="br-empty">Connect your Upstox account to see funds and positions here and to send builder strategies as orders. You log in on Upstox\'s own page; Finostat never sees your password. Zerodha Kite is next.</div><div class="br-row"><a class="br-btn primary" href="/broker/upstox/connect">CONNECT UPSTOX →</a></div>'; return; }
  if(up.expired||(d.upstox&&d.upstox.expired)){ brStatus.textContent='session expired'; brTitle.textContent='UPSTOX · '+esc(up.user||'');
    brBody.innerHTML='<div class="br-empty">Upstox sessions end at 03:30 every day. Reconnect to continue.</div><div class="br-row"><a class="br-btn primary" href="/broker/upstox/connect">RECONNECT →</a><button type="button" class="br-btn" data-act="disconnect">Remove</button></div>'; return; }
  var u=d.upstox||{}, f=u.funds||{};
  brTitle.textContent='UPSTOX · '+esc(up.user||''); brStatus.textContent='connected';
  var h='<div class="br-kpi"><div><small>available margin</small><b>'+money(f.available)+'</b></div><div><small>used</small><b>'+money(f.used)+'</b></div><div><small>open positions</small><b>'+((u.positions||[]).length)+'</b></div><div><small>day P&L</small><b class="'+(((u.positions||[]).reduce(function(a,p){ return a+(p.pnl||0); },0))>=0?'up':'down')+'">'+money((u.positions||[]).reduce(function(a,p){ return a+(p.pnl||0); },0))+'</b></div></div>';
  if(u.funds_error) h+='<div class="br-msg bad">'+esc(u.funds_error)+'</div>';
  h+='<div class="br-h">Positions</div>';
  h+=(u.positions&&u.positions.length)?'<div class="bl-scroll"><table class="br-table"><thead><tr><th>SYMBOL</th><th>QTY</th><th>AVG</th><th>LTP</th><th>P&L</th></tr></thead><tbody>'+u.positions.map(function(p){ return '<tr><td>'+esc(p.symbol)+' <small style="color:var(--faint)">'+esc(p.product||'')+'</small></td><td>'+p.qty+'</td><td>'+(p.avg!=null?fmt(p.avg):'—')+'</td><td>'+(p.ltp!=null?fmt(p.ltp):'—')+'</td><td class="'+((p.pnl||0)>=0?'up':'down')+'">'+money(p.pnl)+'</td></tr>'; }).join('')+'</tbody></table></div>':'<div class="br-msg">no open positions'+(u.positions_error?' · '+esc(u.positions_error):'')+'</div>';
  var open=(u.orders||[]).filter(function(o){ return /open|pending|trigger|validation|put order/i.test(o.status||''); });
  h+='<div class="br-h">Orders today</div>';
  h+=(u.orders&&u.orders.length)?'<div class="bl-scroll"><table class="br-table"><thead><tr><th>SYMBOL</th><th>SIDE</th><th>QTY</th><th>TYPE</th><th>STATUS</th><th></th></tr></thead><tbody>'+u.orders.slice(0,12).map(function(o){ var isOpen=open.indexOf(o)>=0; return '<tr><td>'+esc(o.symbol)+'</td><td class="'+(o.side==='BUY'?'up':'down')+'">'+esc(o.side||'')+'</td><td>'+(o.filled||0)+'/'+(o.qty||0)+'</td><td>'+esc(o.type||'')+(o.type==='LIMIT'&&o.price?' '+fmt(o.price):'')+'</td><td title="'+esc(o.message||'')+'">'+esc(o.status||'')+'</td><td>'+(isOpen?'<button type="button" class="br-btn" data-cancel="'+esc(o.order_id)+'">cancel</button>':'')+'</td></tr>'; }).join('')+'</tbody></table></div>':'<div class="br-msg">no orders today'+(u.orders_error?' · '+esc(u.orders_error):'')+'</div>';
  h+='<div class="br-row" style="margin-top:auto"><span class="br-msg">token ends 03:30 IST · every order is confirmed on a ticket first</span><button type="button" class="br-btn" data-act="disconnect" style="margin-left:auto">Disconnect</button></div>';
  brBody.innerHTML=h;
}
function pollBroker(){
  if(window.FINO_LOCKED||document.getElementById('p-broker').hidden) return;
  fetch('/api/broker',{credentials:'same-origin'}).then(function(r){ return r.json().then(function(d){ d._st=r.status; return d; }); }).then(function(d){
    if(d._st===401){ brStatus.textContent='sign in'; brBody.innerHTML='<div class="br-empty">Sign in to connect a broker.</div>'; return; }
    if(d._st===402){ brStatus.textContent='desk plan'; brBody.innerHTML='<div class="br-empty">Broker connections are part of Desk.</div>'; return; }
    renderBroker(d);
  }).catch(function(){ brStatus.textContent='offline'; });
}
brBody.addEventListener('click',function(e){
  var b=e.target.closest('button[data-act=disconnect]'); if(b){ if(!confirm('Remove the Upstox connection from Finostat?')) return; srvPost('/api/broker/disconnect',{broker:'upstox'}).then(pollBroker); return; }
  var c=e.target.closest('button[data-cancel]'); if(c){ c.disabled=true; srvPost('/api/broker/cancel',{order_id:c.getAttribute('data-cancel')}).then(function(r){ if(r.error) alert(r.error); setTimeout(pollBroker,800); }); }
});
setInterval(pollBroker,10000); setTimeout(pollBroker,900);
if(/[?&]broker=(connected|failed)/.test(location.search)){ var m=location.search.match(/broker=(\w+)/)[1]; setTimeout(function(){ brStatus.textContent=m==='connected'?'connected ✓':'connection failed'; },1200); }
window.finoBrokerReady=function(){ var d=brState.data; var up=d&&(d.brokers||[]).filter(function(b){ return b.id==='upstox'; })[0]; return !!(up&&up.connected&&!up.expired); };
window.finoBrokerPoll=pollBroker;
/* ---------- TradingView chart: follows whatever symbol you click ---------- */
var chart={sym:null,ready:false,loading:false,pending:'NIFTY 50'};
var chSym=document.getElementById('ch-sym'), chNote=document.getElementById('ch-note'), chPanel=document.getElementById('p-chart');
function tvSymbol(key){
  var k=String(key||'').trim().toUpperCase();
  var idx={'NIFTY 50':'NSE:NIFTY','NIFTY':'NSE:NIFTY','BANKNIFTY':'NSE:BANKNIFTY','NIFTY BANK':'NSE:BANKNIFTY','FINNIFTY':'NSE:CNXFINANCE','NIFTY FIN SERVICE':'NSE:CNXFINANCE','SENSEX':'BSE:SENSEX','INDIA VIX':'NSE:INDIAVIX','MIDCPNIFTY':'NSE:NIFTY_MID_SELECT'};
  if(idx[k]) return idx[k];
  var ex='NSE', s=k; if(k.indexOf('BSE:')===0){ ex='BSE'; s=k.slice(4); } else if(k.indexOf('NSE:')===0){ s=k.slice(4); }
  return ex+':'+s.replace(/[&\-\s]+/g,'_').replace(/[^A-Z0-9_]/g,'');
}
function drawChart(){
  if(!chart.pending||!chart.ready||!window.TradingView) return;
  var tv=tvSymbol(chart.pending); chart.sym=chart.pending; chart.pending=null;
  var host=document.getElementById('tv-chart'); host.innerHTML='';
  chSym.textContent=tv; chNote.textContent=chart.sym+' · click any symbol on the desk to chart it';
  new TradingView.widget({container_id:'tv-chart',autosize:true,symbol:tv,interval:'5',timezone:'Asia/Kolkata',theme:'dark',style:'1',locale:'en',
    toolbar_bg:'#120a33',enable_publishing:false,hide_side_toolbar:false,allow_symbol_change:true,withdateranges:true,save_image:false,
    backgroundColor:'#0c0626',gridColor:'rgba(74,52,160,0.22)',hide_top_toolbar:false,studies:[],details:false});
}
function loadTV(){
  if(chart.ready||chart.loading||window.FINO_LOCKED||chPanel.hidden) return;
  chart.loading=true; var s=document.createElement('script'); s.src='https://s3.tradingview.com/tv.js'; s.async=true;
  s.onload=function(){ chart.ready=true; chart.loading=false; drawChart(); }; s.onerror=function(){ chart.loading=false; chNote.textContent='chart unavailable (tradingview.com blocked?)'; };
  document.head.appendChild(s);
}
function chartTo(key){ if(!key) return; if(chart.sym===key&&!chart.pending) return; chart.pending=key; if(chPanel.hidden) return; chart.ready?drawChart():loadTV(); }
window.finoChartTo=chartTo;            /* the builder lives in its own scope below */
var prefs={watchlist:['NIFTY 50','BANKNIFTY','INDIA VIX'],layout:{hide:[]}};
try{ var lp=JSON.parse(localStorage.getItem('fino_prefs_v1')||'null'); if(lp&&lp.watchlist) prefs=lp; }catch(e){}
var signedIn=false, saveTimer=null;
var whoEl=document.getElementById('who'), syncEl=document.getElementById('watch-sync');

function savePrefs(){
  try{ localStorage.setItem('fino_prefs_v1',JSON.stringify(prefs)); }catch(e){}
  if(!signedIn) return;
  clearTimeout(saveTimer);
  saveTimer=setTimeout(function(){
    syncEl.textContent='saving…';
    fetch('/api/me/prefs',{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},
      body:JSON.stringify(prefs)})
    .then(function(r){ syncEl.textContent=r.ok?'synced':'sync failed'; })
    .catch(function(){ syncEl.textContent='sync failed'; });
  },400);
}
function renderWho(user){
  if(user){
    whoEl.innerHTML='<span class="me">'+esc(user.email)+'</span><form method="post" action="/auth/logout"><button type="submit">SIGN OUT</button></form>';
  } else {
    whoEl.innerHTML='<a href="/login">SIGN IN</a>';
  }
}
fetch('/api/me',{credentials:'same-origin'}).then(function(r){ return r.ok?r.json():null; }).then(function(me){
  if(me&&me.email){
    signedIn=true; renderWho(me); enableServerAlerts(); loadUnderlyings();
    if(me.prefs&&me.prefs.watchlist){ prefs=me.prefs; if(!prefs.layout) prefs.layout={hide:[]}; }
    syncEl.textContent='synced';
    try{ localStorage.setItem('fino_prefs_v1',JSON.stringify(prefs)); }catch(e){}
    applyLayout(); renderWatch();
  } else { renderWho(null); syncEl.textContent='local · sign in to sync'; }
}).catch(function(){ renderWho(null); });

/* layout */
var menu=document.getElementById('layout-menu');
menu.innerHTML=PANELS.map(function(p){ return '<label><input type="checkbox" data-p="'+p[0]+'"> '+p[1]+'</label>'; }).join('');
function applyLayout(){
  var hide=(prefs.layout&&prefs.layout.hide)||[];
  PANELS.forEach(function(p){
    var el=document.getElementById('p-'+p[0]); if(el) el.hidden=hide.indexOf(p[0])>=0;
    var cb=menu.querySelector('input[data-p="'+p[0]+'"]'); if(cb) cb.checked=hide.indexOf(p[0])<0;
  });
  var side=document.querySelector('.a-side');
  if(side) side.hidden=(hide.indexOf('straddle')>=0&&hide.indexOf('alerts')>=0);
  if(!chPanel.hidden){ if(chart.sym&&chart.ready){ /* keep */ } else { chart.pending=chart.pending||chart.sym||'NIFTY 50'; chart.sym=null; chart.ready?drawChart():loadTV(); } }
}
menu.addEventListener('change',function(e){
  var cb=e.target; if(!cb.matches('input[data-p]')) return;
  var id=cb.getAttribute('data-p'); var hide=(prefs.layout=prefs.layout||{hide:[]}).hide=prefs.layout.hide||[];
  var i=hide.indexOf(id);
  if(cb.checked&&i>=0) hide.splice(i,1); else if(!cb.checked&&i<0) hide.push(id);
  applyLayout(); savePrefs();
});
applyLayout();

/* watchlist */
var watchEl=document.getElementById('watch');
var watchSearch=searchWidget(document.getElementById('watch-q'), document.getElementById('watch-res'), null);
function quoteFor(sym){
  var q=(state.quotes||[]).filter(function(x){ return x.symbol===sym; })[0];
  if(q) return {price:q.price, change:q.change, name:'', fo:true, index:true};
  return stockQuotes[sym]||null;
}
function renderWatch(){
  var list=prefs.watchlist||[];
  if(!list.length){ watchEl.innerHTML='<div class="watch-empty">Nothing watched yet. Search any NSE stock or index below.</div>'; return; }
  watchEl.innerHTML=list.map(function(sym){
    var q=quoteFor(sym);
    var px=q&&q.price!=null?fmt(q.price):'—', ch=q&&q.change!=null?((q.change>=0?'▲ ':'▼ ')+Math.abs(q.change).toFixed(2)+'%'):'waiting';
    var fo=q&&q.fo&&!q.index?'<span class="fo">F&amp;O</span>':'';
    var nm=q&&q.name?'<div class="nm">'+esc(q.name)+'</div>':'';
    return '<div class="w"><div class="sym">'+esc(sym)+fo+'</div><div class="px">'+px+'</div><div class="ch '+(q&&q.change<0?'down':'up')+'">'+ch+'</div>'+nm+'<button data-sym="'+esc(sym)+'" title="remove">✕</button></div>';
  }).join('');
}
/* stock quotes are polled, never pushed: the 8 Hz stream stays index-only */
function stockKeysNeeded(){
  var keys={};
  (prefs.watchlist||[]).forEach(function(s){ if(!(state.quotes||[]).some(function(q){ return q.symbol===s; })) keys[s]=1; });
  (serverAlerts?srvAlerts:alerts).forEach(function(a){ if(a.metric.indexOf('spot:')===0){ var s=a.metric.slice(5); if(!(state.quotes||[]).some(function(q){ return q.symbol===s; })) keys[s]=1; } });
  return Object.keys(keys);
}
function pollStocks(){
  var keys=stockKeysNeeded(); if(!keys.length) return;
  fetch('/api/quote?s='+encodeURIComponent(keys.join(','))).then(function(r){ return r.json(); }).then(function(res){
    Object.keys(res||{}).forEach(function(k){ stockQuotes[k]=res[k]; });
    renderWatch();
    if(serverAlerts) renderServerAlerts(); else { evalAlerts(); renderAlerts(); }
  }).catch(function(){});
}
setInterval(pollStocks, 2000);

/* ---------- strategy builder ---------- */
var bl={u:null,expiry:null,legs:[],preset:null,strikes:[],timer:null,plan:'starter',signedIn:false,unders:[]};
var blU=document.getElementById('bl-u'), blRes=document.getElementById('bl-u-res'), blExp=document.getElementById('bl-exp'),
    blPresets=document.getElementById('bl-presets'), blBody=document.getElementById('bl-body'), blLegs=document.getElementById('bl-legs'),
    blMetrics=document.getElementById('bl-metrics'), blPayoff=document.getElementById('bl-payoff'), blAxis=document.getElementById('bl-axis'),
    blLock=document.getElementById('bl-lock'), blEmpty=document.getElementById('bl-empty'), blStatus=document.getElementById('bl-status'),
    blTitle=document.getElementById('bl-title'), blLot=document.getElementById('bl-lot');
var PRESET_NAMES=[['short-straddle','Short straddle'],['long-straddle','Long straddle'],['short-strangle','Short strangle'],['long-strangle','Long strangle'],['iron-condor','Iron condor'],['iron-fly','Iron fly'],['bull-call-spread','Bull call'],['bear-put-spread','Bear put'],['butterfly','Butterfly'],['ratio-spread','Ratio 1x2']];
blPresets.innerHTML=PRESET_NAMES.map(function(p){ return '<button type="button" data-p="'+p[0]+'">'+p[1]+'</button>'; }).join('');
function loadUnderlyings(){
  fetch('/api/underlyings',{credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
    bl.unders=d.underlyings||[]; bl.plan=d.plan||'starter'; bl.signedIn=!!d.signed_in;
    blStatus.textContent=bl.unders.length?(bl.plan.toUpperCase()+' · '+bl.unders.length+' underlyings'):'chains loading…';
  }).catch(function(){});
}
loadUnderlyings();
/* local search over the (small) underlying list */
(function(){
  var items=[], sel=-1, picked=null;
  function render(){ if(!items.length){ blRes.hidden=true; blRes.innerHTML=''; return; }
    blRes.innerHTML=items.map(function(x,i){ return '<li data-i="'+i+'"'+(i===sel?' class="sel"':'')+'><b>'+esc(x.label)+'</b><small>'+esc(x.kind==='index'?'index':x.name||'')+'</small>'+(x.n50?'<em>N50</em>':x.kind==='stock'?'<em>F&amp;O</em>':'')+'</li>'; }).join(''); blRes.hidden=false; }
  function choose(i){ if(i<0||i>=items.length) return; picked=items[i]; blU.value=picked.label; items=[]; render(); selectUnderlying(picked.key); }
  blU.addEventListener('input',function(){
    var q=blU.value.trim().toUpperCase(); if(!q){ items=[]; render(); return; }
    items=bl.unders.filter(function(x){ return x.label.toUpperCase().indexOf(q)===0||x.label.toUpperCase().indexOf(q)>=0||(x.name||'').toUpperCase().indexOf(q)>=0; })
      .sort(function(a,b){ var pa=a.label.toUpperCase().indexOf(q)===0?0:1, pb=b.label.toUpperCase().indexOf(q)===0?0:1; return pa-pb||a.label.length-b.label.length; }).slice(0,8);
    sel=items.length?0:-1; render();
  });
  blU.addEventListener('keydown',function(e){ if(blRes.hidden) return; if(e.key==='ArrowDown'){ sel=Math.min(items.length-1,sel+1); render(); e.preventDefault(); } else if(e.key==='ArrowUp'){ sel=Math.max(0,sel-1); render(); e.preventDefault(); } else if(e.key==='Enter'){ choose(sel); e.preventDefault(); } else if(e.key==='Escape'){ items=[]; render(); } });
  blRes.addEventListener('mousedown',function(e){ var li=e.target.closest('li[data-i]'); if(li){ choose(Number(li.getAttribute('data-i'))); e.preventDefault(); } });
  blU.addEventListener('blur',function(){ setTimeout(function(){ items=[]; render(); },120); });
})();
var blChainBtn=document.getElementById('bl-chain-btn'), blOi=document.getElementById('bl-oi'), blChain=document.getElementById('bl-chain'), blChainRows=document.getElementById('bl-chain-rows'), blChainNote=document.getElementById('bl-chain-note');
bl.chainOpen=false;
function kfmt(n){ if(n==null) return '—'; var a=Math.abs(n); return (n<0?'-':'')+(a>=1e7?(a/1e7).toFixed(2)+'cr':a>=1e5?(a/1e5).toFixed(1)+'L':a>=1000?(a/1000).toFixed(1)+'k':String(a)); }
function loadChain(){
  if(!bl.u||!bl.chainOpen) return;
  fetch('/api/chain?u='+encodeURIComponent(bl.u)+(bl.expiry?'&expiry='+bl.expiry:''),{credentials:'same-origin'}).then(function(r){ return r.json(); }).then(renderChain).catch(function(){});
}
function renderChain(c){
  if(!c||!c.rows){ blChainRows.innerHTML=''; blChainNote.textContent=c&&c.error?c.error:'chain unavailable'; blOi.hidden=true; return; }
  var o=c.oi, mx=o&&o.max_oi?o.max_oi:0;
  if(o){ blOi.hidden=false;
    blOi.innerHTML=[['PCR (OI)',o.pcr!=null?o.pcr.toFixed(2):'—'],['max pain',o.max_pain!=null?fmt(o.max_pain,0):'—'],['call wall',o.call_wall!=null?fmt(o.call_wall,0):'—'],['put wall',o.put_wall!=null?fmt(o.put_wall,0):'—'],['call OI',kfmt(o.tot_ce)],['put OI',kfmt(o.tot_pe)]]
      .map(function(x){ return '<div><small>'+x[0]+'</small><b>'+x[1]+'</b></div>'; }).join('');
  } else blOi.hidden=true;
  blChainRows.innerHTML=c.rows.map(function(r){
    var ce=r.ce||{}, pe=r.pe||{};
    function oiTd(side,s){ var w=mx&&s.oi?Math.round(s.oi/mx*100):0; return '<td class="'+side+' oi'+(o&&((side==='ce'&&r.strike===o.call_wall)||(side==='pe'&&r.strike===o.put_wall))?' wall':'')+'"><i style="width:'+w+'%"></i><span>'+kfmt(s.oi)+'</span></td>'; }
    function chTd(s){ return '<td class="ch">'+(s.oi_chg==null?'—':(s.oi_chg>0?'+':'')+kfmt(s.oi_chg))+'</td>'; }
    return '<tr'+(r.atm?' class="atm"':'')+'>'+oiTd('ce',ce)+chTd(ce)+'<td>'+(ce.iv!=null?ce.iv.toFixed(1):'—')+'</td><td class="px" data-r="CE" data-k="'+r.strike+'">'+(ce.ltp!=null?ce.ltp.toFixed(2):'—')+'</td>'
      +'<td class="k">'+r.strike+'</td><td class="px" data-r="PE" data-k="'+r.strike+'">'+(pe.ltp!=null?pe.ltp.toFixed(2):'—')+'</td><td>'+(pe.iv!=null?pe.iv.toFixed(1):'—')+'</td>'+chTd(pe)+oiTd('pe',pe)+'</tr>';
  }).join('');
  var since=null; c.rows.some(function(r){ var s=(r.ce&&r.ce.oi_since)||(r.pe&&r.pe.oi_since); if(s){ since=s; return true; } });
  blChainNote.textContent=(o?'OI from the exchange feed · ΔOI since the first tick seen today · click a price to add that leg':'this chain socket carries no open interest yet')+(c.live?'':' · last traded');
}
blChainBtn.addEventListener('click',function(){ bl.chainOpen=!bl.chainOpen; blChainBtn.classList.toggle('on',bl.chainOpen); blChain.hidden=!bl.chainOpen; if(!bl.chainOpen) blOi.hidden=true; else loadChain(); });
blChainRows.addEventListener('click',function(e){ var td=e.target.closest('td.px'); if(!td||bl.legs.length>=8) return; bl.legs.push({right:td.getAttribute('data-r'),strike:Number(td.getAttribute('data-k')),qty:1}); bl.preset=null; priceStrategy(); });
function stopPricing(){ if(bl.timer){ clearInterval(bl.timer); bl.timer=null; } }
function showLock(err){
  stopPricing();                                   // nothing to price while locked
  if(!blLock.hidden && blLock.getAttribute('data-need')===(err.need||'desk')) return;   // already showing: keep the user's state
  blLock.setAttribute('data-need', err.need||'desk');
  blBody.hidden=true; blEmpty.hidden=true; blLock.hidden=false;
  var need=(err.need||'desk'); document.getElementById('bl-lock-title').textContent=need.toUpperCase()+' PLAN';
  document.getElementById('bl-lock-text').textContent=(err.feature==='builder_stocks'?'Strategy building on F&O stocks is part of the '+need+' plan. Index strategies stay free.':'This feature needs the '+need+' plan.');
  var btn=document.getElementById('bl-lock-btn'), note=document.getElementById('bl-lock-note');
  btn.disabled=false;
  if(!err.signed_in){ btn.textContent='SIGN IN TO UPGRADE'; btn.onclick=function(){ location.href='/login?next='+encodeURIComponent('/account?plan='+need); }; note.textContent='Starter is free — sign in with your email, then pay by UPI or card.'; }
  else { btn.textContent='UPGRADE TO '+need.toUpperCase(); note.textContent='You are on '+(err.plan||'starter')+'. Pay by UPI or card; active the moment it clears.';
    btn.onclick=function(){ location.href='/account?plan='+need; }; }
}
function selectUnderlying(key){
  if(window.finoChartTo) window.finoChartTo(key);
  bl.u=key; bl.expiry=null; bl.legs=[]; bl.preset='short-straddle'; blLock.hidden=true; blLock.removeAttribute('data-need'); blEmpty.hidden=true; blBody.hidden=true; blChainRows.innerHTML=''; blOi.hidden=true;
  blStatus.textContent='loading chain…'; blTitle.textContent='STRATEGY BUILDER · '+key;
  priceStrategy(true);
}
function priceStrategy(first){
  if(!bl.u) return;
  var body={u:bl.u, expiry:bl.expiry||undefined};
  if(bl.legs.length) body.legs=bl.legs.map(function(l){ return {right:l.right,strike:l.strike,qty:l.qty}; }); else body.preset=bl.preset;
  fetch('/api/strategy',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  .then(function(r){ return r.json().then(function(d){ d._status=r.status; return d; }); })
  .then(function(d){
    if(d._status===403){ showLock(d); return; }
    if(d.warming&&!d.legs){ blStatus.textContent='chain warming…'; if(!bl.timer) bl.timer=setInterval(priceStrategy,3000); return; }
    if(d.error){ blStatus.textContent=d.error; return; }
    bl.legs=d.legs; bl.strikes=d.strikes; bl.expiry=d.expiry; bl.lastData=d;
    blExp.disabled=false; blExp.innerHTML=(d.expiries||[]).map(function(e){ var dt=new Date(e); return '<option value="'+e+'"'+(e===d.expiry?' selected':'')+'>'+dt.toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+'</option>'; }).join('');
    Array.prototype.forEach.call(blPresets.querySelectorAll('button'),function(b){ b.classList.toggle('on', b.getAttribute('data-p')===bl.preset); });
    renderBuilder(d); blBody.hidden=false; blLock.hidden=true; blEmpty.hidden=true;
    blStatus.textContent=(d.live?'LIVE':'DELAYED')+' · spot '+fmt(d.spot)+(d.warming?' · warming':'');
    loadChain();
    if(!bl.timer) bl.timer=setInterval(priceStrategy,3000);
  }).catch(function(){ blStatus.textContent='offline'; });
}
function renderBuilder(d){
  blLot.textContent='lot '+d.lot+' · ATM '+d.atm+' · step '+d.step;
  blLegs.innerHTML=d.legs.map(function(l,i){
    var opts=d.strikes.map(function(k){ return '<option'+(k===l.strike?' selected':'')+'>'+k+'</option>'; }).join('');
    return '<tr data-i="'+i+'"><td class="'+(l.qty>0?'side-b':'side-s')+'">'+(l.qty>0?'BUY':'SELL')+'</td>'
      +'<td><input type="number" min="-10" max="10" step="1" value="'+l.qty+'" data-f="qty"></td>'
      +'<td><select data-f="right"><option'+(l.right==='CE'?' selected':'')+'>CE</option><option'+(l.right==='PE'?' selected':'')+'>PE</option></select></td>'
      +'<td><select data-f="strike">'+opts+'</select></td>'
      +'<td>'+(l.price!=null?l.price.toFixed(2):'—')+'</td><td>'+(l.iv!=null?l.iv.toFixed(1)+'%':'—')+'</td><td>'+(l.delta!=null?l.delta.toFixed(2):'—')+'</td>'
      +'<td><button type="button" data-act="del" title="remove">✕</button></td></tr>';
  }).join('');
  var m=d.metrics||{};
  function money(v){ return v==null?'UNLIMITED':'₹'+fmt(v,0); }
  var cells=[['net '+(m.net_premium>=0?'credit':'debit'),'₹'+fmt(Math.abs(m.net_premium_lot||0),0)],['max profit',money(m.max_profit_lot)],['max loss',money(m.max_loss_lot)],['breakevens',(m.breakevens||[]).map(function(b){ return fmt(b,0); }).join(' / ')||'—']];
  if(m.greeks) cells.push(['delta',m.greeks.delta.toFixed(1)],['theta /day',m.greeks.theta.toFixed(0)],['vega',m.greeks.vega.toFixed(0)]);
  blMetrics.innerHTML=cells.map(function(c){ return '<div><small>'+c[0]+'</small><b>'+c[1]+'</b></div>'; }).join('');
  drawPayoff(m.payoff||[], d.spot, m.breakevens||[]);
}
function drawPayoff(pts, spot, bes){
  if(!pts.length){ blPayoff.innerHTML=''; return; }
  var xs=pts.map(function(p){ return p[0]; }), ys=pts.map(function(p){ return p[1]; });
  var x0=xs[0], x1=xs[xs.length-1], ymax=Math.max.apply(null,ys.concat([0])), ymin=Math.min.apply(null,ys.concat([0])), span=(ymax-ymin)||1;
  var X=function(x){ return (x-x0)/(x1-x0)*320; }, Y=function(y){ return 8+(ymax-y)/span*114; };
  var d=pts.map(function(p,i){ return (i?'L':'M')+X(p[0]).toFixed(1)+' '+Y(p[1]).toFixed(1); }).join(' ');
  var zero=Y(0).toFixed(1);
  var pos='M'+X(x0).toFixed(1)+' '+zero+' '+pts.map(function(p){ return 'L'+X(p[0]).toFixed(1)+' '+Y(Math.max(0,p[1])).toFixed(1); }).join(' ')+' L'+X(x1).toFixed(1)+' '+zero+' Z';
  var neg='M'+X(x0).toFixed(1)+' '+zero+' '+pts.map(function(p){ return 'L'+X(p[0]).toFixed(1)+' '+Y(Math.min(0,p[1])).toFixed(1); }).join(' ')+' L'+X(x1).toFixed(1)+' '+zero+' Z';
  blPayoff.innerHTML='<path d="'+pos+'" fill="rgba(61,214,140,.18)"/><path d="'+neg+'" fill="rgba(255,92,108,.18)"/>'
    +'<line x1="0" y1="'+zero+'" x2="320" y2="'+zero+'" stroke="#4a34a0" stroke-width="1" stroke-dasharray="3 3"/>'
    +'<line x1="'+X(spot).toFixed(1)+'" y1="4" x2="'+X(spot).toFixed(1)+'" y2="126" stroke="#7fe0f0" stroke-width="1" stroke-dasharray="2 3"/>'
    +bes.map(function(b){ return '<circle cx="'+X(b).toFixed(1)+'" cy="'+zero+'" r="3" fill="#f5c842"/>'; }).join('')
    +'<path d="'+d+'" fill="none" stroke="#f5c842" stroke-width="1.8"/>';
  blAxis.innerHTML='<span>'+fmt(x0,0)+'</span><span style="color:var(--cyan)">spot '+fmt(spot,0)+'</span><span>'+fmt(x1,0)+'</span>';
}
blPresets.addEventListener('click',function(e){ var b=e.target.closest('button[data-p]'); if(!b||!bl.u) return; bl.preset=b.getAttribute('data-p'); bl.legs=[]; priceStrategy(); });
blExp.addEventListener('change',function(){ bl.expiry=Number(blExp.value)||null; bl.legs=[]; priceStrategy(); });
blLegs.addEventListener('change',function(e){
  var tr=e.target.closest('tr[data-i]'); if(!tr) return; var i=Number(tr.getAttribute('data-i')), f=e.target.getAttribute('data-f'), l=bl.legs[i]; if(!l) return;
  if(f==='qty'){ var q=parseInt(e.target.value,10); if(isNaN(q)||q===0) q=1; l.qty=Math.max(-10,Math.min(10,q)); }
  else if(f==='right') l.right=e.target.value; else if(f==='strike') l.strike=Number(e.target.value);
  bl.preset=null; priceStrategy();
});
blLegs.addEventListener('click',function(e){ var b=e.target.closest('button[data-act=del]'); if(!b) return; var i=Number(b.closest('tr').getAttribute('data-i')); bl.legs.splice(i,1); bl.preset=null; if(!bl.legs.length){ bl.preset='short-straddle'; } priceStrategy(); });
/* order ticket: builder legs -> connected broker, confirmed by the member */
var tk=document.getElementById('tk'), tkLegs=document.getElementById('tk-legs'), tkMsg=document.getElementById('tk-msg'), tkRes=document.getElementById('tk-res'), tkLast=null;
function openTicket(){
  if(!bl.u||!bl.legs.length||!bl.lastData) return;
  if(!(window.finoBrokerReady&&window.finoBrokerReady())){ alert('Connect your Upstox account in the BROKER panel first.'); return; }
  var d=bl.lastData; document.getElementById('tk-title').textContent=bl.u+' · '+new Date(d.expiry).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+' · lot '+d.lot;
  tkLegs.innerHTML=d.legs.map(function(l,i){ return '<tr><td>'+l.strike+' '+l.right+'</td><td class="'+(l.qty>0?'up':'down')+'">'+(l.qty>0?'BUY':'SELL')+'</td><td>'+Math.abs(l.qty)+'×'+d.lot+'</td><td>'+(l.price!=null?l.price.toFixed(2):'—')+'</td><td><input type="number" step="0.05" min="0.05" data-i="'+i+'" value="'+(l.price!=null?l.price.toFixed(2):'')+'" style="width:76px"></td></tr>'; }).join('');
  document.getElementById('tk-confirm').checked=false; tkMsg.textContent=''; tkRes.innerHTML=''; document.getElementById('tk-send').disabled=false; tk.hidden=false;
}
document.getElementById('bl-trade').addEventListener('click',openTicket);
document.getElementById('tk-x').addEventListener('click',function(){ tk.hidden=true; });
document.getElementById('tk-cancel').addEventListener('click',function(){ tk.hidden=true; });
document.getElementById('tk-send').addEventListener('click',function(){
  if(!document.getElementById('tk-confirm').checked){ tkMsg.className='br-msg bad'; tkMsg.textContent='tick the confirmation first'; return; }
  var d=bl.lastData, otype=document.getElementById('tk-type').value, lots=parseInt(document.getElementById('tk-lots').value,10)||1;
  var legs=d.legs.map(function(l,i){ var inp=tkLegs.querySelector('input[data-i="'+i+'"]'); return {right:l.right,strike:l.strike,qty:l.qty,price:inp&&inp.value?Number(inp.value):l.price}; });
  var btn=this; btn.disabled=true; tkMsg.className='br-msg'; tkMsg.textContent='sending…';
  srvPost('/api/broker/order',{u:bl.u,expiry:d.expiry,legs:legs,lots:lots,product:document.getElementById('tk-product').value,order_type:otype,confirm:true}).then(function(r){
    if(r.error){ btn.disabled=false; tkMsg.className='br-msg bad'; tkMsg.textContent=r.error; return; }
    tkMsg.className='br-msg '+(r.ok?'ok':'bad'); tkMsg.textContent=r.ok?'all '+r.sent+' leg(s) accepted by Upstox':('stopped after '+r.sent+' of '+r.planned+' leg(s)');
    tkRes.innerHTML=(r.results||[]).map(function(x){ return '<div class="'+(x.ok?'ok':'bad')+'">'+esc(x.leg)+' — '+(x.ok?'order '+esc(x.order_id||''):esc(x.error||'rejected'))+'</div>'; }).join('');
    if(window.finoBrokerPoll) setTimeout(window.finoBrokerPoll,800);
  }).catch(function(){ btn.disabled=false; tkMsg.className='br-msg bad'; tkMsg.textContent='network error — check the BROKER panel before retrying'; });
});
document.getElementById('bl-add').addEventListener('click',function(){ if(!bl.strikes.length) return; var atm=bl.strikes[Math.floor(bl.strikes.length/2)]; if(bl.legs.length>=8) return; bl.legs.push({right:'CE',strike:atm,qty:1}); bl.preset=null; priceStrategy(); });

/* Nifty 50 constituents: the official list, live, sorted by movers */
var n50Rows=document.getElementById('n50-rows'), n50Note=document.getElementById('n50-note');
function pollN50(){
  var panel=document.getElementById('p-n50'); if(panel&&panel.hidden) return;
  fetch('/api/symbols?group=nifty50').then(function(r){ return r.json(); }).then(function(list){
    if(!list||!list.length){ n50Rows.innerHTML='<tr><td colspan="3" style="color:var(--faint)">constituents not quoting yet</td></tr>'; return; }
    list.sort(function(a,b){ return (b.change||0)-(a.change||0); });
    var watched=prefs.watchlist||[];
    n50Rows.innerHTML=list.map(function(e){
      var w=watched.indexOf(e.key)>=0;
      return '<tr data-key="'+esc(e.key)+'" title="'+(w?'in your watchlist':'click to add to watchlist')+'"><td'+(w?' class="w"':'')+'>'+esc(e.symbol)+'<small>'+esc(e.name||'')+'</small></td><td>'+fmt(e.price)+'</td><td class="'+(e.change<0?'down':'up')+'">'+(e.change>=0?'▲ ':'▼ ')+Math.abs(e.change||0).toFixed(2)+'%</td></tr>';
    }).join('');
    var up=list.filter(function(e){ return e.change>0; }).length;
    n50Note.textContent=list.length+' names · '+up+' up · '+(list.length-up)+' down';
  }).catch(function(){});
}
n50Rows.addEventListener('click',function(e){
  var tr=e.target.closest('tr[data-key]'); if(!tr) return;
  var k=tr.getAttribute('data-key'); prefs.watchlist=(prefs.watchlist||[]);
  chartTo(k);
  if(prefs.watchlist.indexOf(k)<0){ prefs.watchlist.push(k); renderWatch(); savePrefs(); pollStocks(); pollN50(); }
});
setInterval(pollN50, 2500); setTimeout(pollN50, 600);
watchEl.addEventListener('click',function(e){
  var cell=e.target.closest('.w'); if(cell&&!e.target.closest('button')){ var sb=cell.querySelector('button[data-sym]'); if(sb) chartTo(sb.getAttribute('data-sym')); return; }
  var b=e.target.closest('button[data-sym]'); if(!b) return;
  prefs.watchlist=(prefs.watchlist||[]).filter(function(s){ return s!==b.getAttribute('data-sym'); });
  renderWatch(); savePrefs();
});
document.getElementById('watch-add').addEventListener('submit',function(e){
  e.preventDefault();
  var hit=watchSearch.picked()||watchSearch.first(); if(!hit) return;
  var s=hit.key;
  prefs.watchlist=(prefs.watchlist||[]); if(prefs.watchlist.indexOf(s)<0) prefs.watchlist.push(s);
  watchSearch.clear(); renderWatch(); savePrefs(); pollStocks();
});

/* ---------- server-side alerts (signed in) ---------- */
var serverAlerts=false, srvAlerts=[], lastEventId=0, srvTimer=null;
var alMode=document.getElementById('al-mode'), alMailWrap=document.getElementById('al-mail-wrap'), alEmail=document.getElementById('al-email');
function srvLabel(a){
  var m=a.metric.indexOf('spot:')===0 ? a.metric.slice(5)+' spot' : a.metric==='straddle' ? 'ATM straddle' : a.metric.toUpperCase()+' '+a.strike;
  return m+' '+(a.cmp==='>='?'≥':'≤')+' '+a.value;
}
function renderServerAlerts(){
  var armed=srvAlerts.filter(function(a){ return a.state==='armed'; }).length;
  alCount.textContent=armed+' ARMED';
  if(!srvAlerts.length){ alList.innerHTML='<li class="al-empty">No alerts on your account. Arm one above — the server watches it even when this tab is closed, and emails you when it fires.</li>'; return; }
  alList.innerHTML=srvAlerts.map(function(a){
    var cur=metricValue(a.metric,a.strike);
    var tag=a.state==='fired'?'<span class="tag fired">FIRED</span>':'<span class="tag hot">ARMED</span>';
    var sub=a.state==='fired'&&a.fired_value!=null?'<small class="fv">fired at '+Number(a.fired_value).toFixed(2)+'</small>':'<small>now '+(cur==null?'—':cur.toFixed(2))+(a.email?' · ✉':'')+'</small>';
    var act=a.state==='fired'?'<button class="rearm" data-id="'+a.id+'" data-act="rearm">RE-ARM</button>':'';
    return '<li><div><b>'+esc(srvLabel(a))+'</b>'+sub+'</div>'+tag+'<span>'+act+' <button data-id="'+a.id+'" data-act="delete">✕</button></span></li>';
  }).join('');
}
function srvPost(path, body){
  return fetch(path,{method:'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},
    body:JSON.stringify(body||{})}).then(function(r){ return r.json(); });
}
function loadServerAlerts(){
  return fetch('/api/alerts',{credentials:'same-origin'}).then(function(r){ return r.ok?r.json():null; }).then(function(d){
    if(!d) return;
    srvAlerts=d.alerts||[];
    var evs=(d.events||[]).slice().reverse();
    var fresh=evs.filter(function(e){ return e.id>lastEventId; });
    if(lastEventId>0 && fresh.length){
      fresh.forEach(function(e){ logAlert(e.message, e.ts); });
      beep();
      if('Notification' in window && Notification.permission==='granted'){
        try{ new Notification('Finostat alert',{body:fresh.map(function(e){ return e.message; }).join('\n'),icon:'/og.jpg'}); }catch(err){}
      }
    } else if(lastEventId===0){
      evs.slice(-8).forEach(function(e){ logAlert(e.message, e.ts); });
    }
    if(evs.length) lastEventId=Math.max(lastEventId, evs[evs.length-1].id);
    renderServerAlerts();
  }).catch(function(){});
}
function enableServerAlerts(){
  serverAlerts=true;
  alMode.textContent='MY ALERTS · SERVER'; alMailWrap.hidden=false;
  loadServerAlerts();
  if(!srvTimer) srvTimer=setInterval(loadServerAlerts, 4000);
}

/* ---------- ingest a sheet payload ---------- */
function ingest(d){
  state.lastEvent=Date.now();
  if(d.quotes && d.quotes.length){ state.quotes=d.quotes; renderTape(d.quotes); renderWatch(); }
  if(d.rows && d.rows.length){ applySheet(d.rows, d.atm!=null?d.atm:state.atm); refreshStrikes(); }
  if(d.mini && d.mini.length){ state.mini=d.mini; renderMini(d.mini); }
  if(d.straddle!=null){ state.straddle=d.straddle; pushStraddle(d.straddle); }
  if(typeof d.live==='boolean') state.live=d.live;
  if(serverAlerts){ renderServerAlerts(); } else { evalAlerts(); renderAlerts(); }
  document.getElementById('sheet-note').textContent = state.live?'live':'delayed';
}

/* ---------- connection ---------- */
var conn=document.getElementById('conn'), sheetStream=null;
function setConn(){
  var open = sheetStream ? sheetStream.readyState===1 : !!pollTimer;
  var fresh = Date.now()-state.lastEvent < 6000;
  if(!open){ conn.textContent='RECONNECTING'; conn.classList.add('off'); return; }
  conn.classList.remove('off');
  // A quiet market sends no ticks; that is idle, not broken.
  conn.textContent = fresh ? (state.live?'LIVE':'DELAYED') : (state.live?'LIVE · IDLE':'IDLE');
}
setInterval(setConn,2000);

var pollTimer=null;
function startPolling(){ if(!pollTimer) pollTimer=setInterval(function(){
  fetch('/api/sheet').then(function(r){ return r.json(); }).then(function(d){
    ingest({rows:d.rows,atm:d.atm,straddle:d.straddle,live:d.live});
  }).catch(function(){});
  fetch('/api/quotes').then(function(r){ return r.json(); }).then(function(q){ ingest({quotes:q}); }).catch(function(){});
},2000); }
function stopPolling(){ if(pollTimer){ clearInterval(pollTimer); pollTimer=null; } }

if('EventSource' in window){
  var ss=new EventSource('/api/sheet/stream'); sheetStream=ss;
  ss.addEventListener('sheet',function(e){
    stopPolling();
    var d; try{ d=JSON.parse(e.data); }catch(err){ return; }
    ingest(d);
  });
  ss.onerror=function(){ startPolling(); };
  var ns=new EventSource('/api/news/stream');
  ns.addEventListener('news',function(e){
    wireLive.textContent='LIVE'; wireLive.classList.remove('off');
    try{ ingestNews(JSON.parse(e.data)); }catch(err){}
  });
  ns.onerror=function(){ wireLive.textContent='RSS'; wireLive.classList.add('off'); };
  setTimeout(function(){ if(!state.lastEvent) startPolling(); },3000);
}else{ startPolling(); }

/* ---------- clock ---------- */
var clk=document.getElementById('clock'), mkt=document.getElementById('mkt');
function tick(){
  clk.textContent=new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false})+' IST';
  var n=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));
  var m=n.getHours()*60+n.getMinutes();
  var open=n.getDay()>0&&n.getDay()<6&&m>=555&&m<=930;
  mkt.textContent='NSE '+(open?'OPEN':'CLOSED'); mkt.classList.toggle('closed',!open);
}
tick(); setInterval(tick,1000);

/* ---------- seed ---------- */
setTimeout(pollStocks, 800);
var seed=window.SEED||{};
document.getElementById('sheet-sym').textContent=seed.symbol||'NIFTY';
document.getElementById('t-sym').textContent=(seed.symbol||'NIFTY')+' · NEAREST EXPIRY';
renderMini(seed.mini);
if(seed.rows&&seed.rows.length){ ingest(seed); } else { renderSheet([],null); }
renderAlerts();
})();
</script>
</body>
</html>
"""


_PAYWALL_CSS = """<style>
body.locked main.desk{filter:blur(7px) saturate(.8);pointer-events:none;user-select:none;opacity:.8}
body.locked .cmd,body.locked .fkeys{pointer-events:none}
.paywall{position:fixed;inset:0;z-index:900;display:flex;align-items:center;justify-content:center;padding:18px;background:radial-gradient(ellipse 60% 50% at 50% 40%,rgba(12,6,38,.35),rgba(12,6,38,.78))}
.paywall .card{width:100%;max-width:560px;background:var(--panel);border:1px solid var(--gold);box-shadow:0 30px 90px rgba(0,0,0,.7),0 0 40px rgba(245,200,66,.12);font-family:var(--body)}
.paywall .hd{display:flex;align-items:center;gap:12px;padding:8px 14px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.paywall .hd .k{color:var(--gold);font-weight:600}.paywall .hd .s{color:var(--cyan)}.paywall .hd .r{margin-left:auto;color:var(--faint)}
.paywall .bd{padding:20px 22px 22px}
.paywall h2{font-family:var(--display);font-size:32px;line-height:.95;text-transform:uppercase;margin:0 0 8px;color:var(--text)}
.paywall p{color:var(--muted);font-size:14.5px;line-height:1.55;margin:0 0 12px}
.paywall ul{list-style:none;margin:0 0 16px;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:4px 14px;font-size:13px;color:var(--text)}
.paywall li{padding-left:14px;position:relative}.paywall li::before{content:"▸";position:absolute;left:0;color:var(--gold)}
.paywall .price{font-family:var(--display);font-size:30px;color:var(--gold);margin:0 0 14px}.paywall .price i{font-style:normal;font-family:var(--mono);font-size:12px;color:var(--muted)}
.paywall .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.paywall a.b{display:inline-flex;align-items:center;font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:11px 16px;border:1px solid var(--line-strong);color:var(--text);text-decoration:none}
.paywall a.b.primary{background:linear-gradient(180deg,var(--gold-2),#f2b830);color:#2a1a02;border-color:var(--gold);font-weight:600}
.paywall a.b:hover{border-color:var(--gold);color:var(--gold)}.paywall a.b.primary:hover{filter:brightness(1.08);color:#000}
.paywall small{display:block;font-family:var(--mono);font-size:10.5px;color:var(--faint);margin-top:12px;letter-spacing:.04em}
@media(max-width:560px){.paywall ul{grid-template-columns:1fr}.paywall h2{font-size:26px}}
</style>"""


def _paywall(signed_in: bool, plan: str) -> str:
    if signed_in:
        head = "Your account is on Starter" if plan == "starter" else f"Your {plan} plan has ended"
        lead = "The live terminal is part of Desk. Everything behind this screen is running — the sheets, the chains, the alerts — it just needs a plan on the account."
        primary = '<a class="b primary" href="/account?plan=desk">Get Desk — pay by UPI or card →</a>'
        secondary = '<a class="b" href="/finch">Finch is free · read it</a>'
    else:
        head = "The terminal is for Desk members"
        lead = "Sign in with your email, pick Desk, and this screen unblurs the moment the payment clears. Starter stays free for Finch, the daily brief and the assessment."
        primary = '<a class="b primary" href="/login?next=%2Faccount%3Fplan%3Ddesk">Sign in &amp; get Desk →</a>'
        secondary = '<a class="b" href="/login">Already a member? Sign in</a>'
    return f"""<div class="paywall" role="dialog" aria-label="Desk plan required"><div class="card">
<div class="hd"><span class="k">DESK</span><span class="s">LIVE TERMINAL</span><span class="r">₹2,199 / 30 DAYS</span></div>
<div class="bd"><h2>{head}</h2><p>{lead}</p>
<ul><li>Sheets live, under 250 ms</li><li>Option chains with OI, PCR, max pain</li><li>Builder on every F&amp;O stock</li><li>Server alerts, emailed</li><li>Watchlist, Nifty 50 panel, news wire</li><li>Nothing auto-renews</li></ul>
<div class="price">₹2,199 <i>/ 30 days · ₹21,990 / year · exclusive of GST</i></div>
<div class="row">{primary}{secondary}</div>
<small>Pro desk (₹5,599) adds recorded history, backtesting and unlimited alerts. <a href="/#plans" style="color:var(--cyan)">Compare plans</a></small>
</div></div></div>"""


def render_dashboard(snapshot: dict, locked: bool = False, signed_in: bool = False, plan: str = "starter") -> bytes:
    doc = DASHBOARD.replace("__SEED__", _seed(snapshot))
    if locked:
        # The page renders its seed as usual (so the blur has real panels under
        # it) but every network call is neutered before the app scripts run.
        guard = ('<script>window.FINO_LOCKED=true;window.fetch=function(){return Promise.reject(new Error("locked"));};'
                 'window.EventSource=function(){return {close:function(){},addEventListener:function(){},onmessage:null};};'
                 'document.addEventListener("DOMContentLoaded",function(){document.body.classList.add("locked");});</script>')
        doc = doc.replace("<script>window.SEED=", _PAYWALL_CSS + guard + "<script>window.SEED=", 1)
        doc = doc.replace("</body>", _paywall(signed_in, plan) + "\n</body>", 1)
    return doc.encode("utf-8")


STRATEGY = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__ — Finostat</title>
<meta name="description" content="__BLURB__">
<meta name="theme-color" content="#0c0626">
<link rel="icon" href="/og.jpg">
<link rel="canonical" href="https://finostat.com/strategies/__SLUG__">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0c0626;--panel:#120a33;--panel-hd:#1c1052;--line:#2c1c66;--line-strong:#4a34a0;
  --gold:#f5c842;--gold-2:#ffe27a;--cyan:#7fe0f0;--up:#3dd68c;--down:#ff5c6c;
  --text:#f1edff;--muted:#a89ccf;--faint:#6d609e;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --body:"IBM Plex Sans",system-ui,sans-serif;
  --display:"Barlow Condensed",Impact,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg);scroll-behavior:smooth}
body{color:var(--text);font-family:var(--body);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,rgba(200,180,255,.03) 0 1px,transparent 1px 3px)}
html::after{content:"";position:fixed;inset:0;z-index:-1;
  background:radial-gradient(ellipse 70% 45% at 50% 0%,rgba(122,60,245,.45),transparent 70%),var(--bg)}
a{color:inherit;text-decoration:none}
.top{display:flex;align-items:center;gap:14px;height:48px;padding:0 16px;
  background:rgba(12,6,38,.94);border-bottom:1px solid var(--line-strong);
  font-family:var(--mono);font-size:11px;position:sticky;top:0;z-index:5;flex-wrap:wrap}
.top .logo{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:.14em;text-transform:uppercase;
  background:linear-gradient(180deg,#fff 20%,var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
.top .r{margin-left:auto;display:flex;gap:14px;color:var(--faint);letter-spacing:.06em}
.top .r a:hover{color:var(--gold)}
.live{color:var(--up);display:inline-flex;align-items:center;gap:6px}
.live::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--up);box-shadow:0 0 8px var(--up);animation:pulse 1.6s infinite}
.live.off{color:var(--down)}.live.off::before{background:var(--down);box-shadow:none;animation:none}
@keyframes pulse{50%{opacity:.35}}
.wrap{width:min(1080px,calc(100% - 36px));margin:0 auto;position:relative;z-index:1;padding:34px 0 64px}
.crumb{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.crumb a:hover{color:var(--gold)}
h1{font-family:var(--display);font-weight:600;font-size:clamp(38px,5vw,58px);line-height:.95;text-transform:uppercase;margin:10px 0 6px}
.tagline{color:var(--muted);max-width:64ch;font-size:16px}
.facts{display:flex;gap:22px;margin:18px 0 26px;font-family:var(--mono);font-size:11px;color:var(--faint);letter-spacing:.06em;flex-wrap:wrap}
.facts b{display:block;color:var(--cyan);font-size:13px;font-weight:500;margin-top:2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line-strong);font-family:var(--mono);font-size:12.5px;box-shadow:0 16px 44px rgba(0,0,0,.35)}
.panel-hd{display:flex;align-items:center;gap:12px;padding:7px 12px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.06em}
.panel-hd .k{color:var(--gold);font-weight:600}
.panel-hd .s{color:var(--cyan)}
.panel-hd .r{margin-left:auto;color:var(--faint)}
.pay{padding:14px 14px 8px;background:#08041f}
.pay svg{width:100%;height:auto;display:block}
table{width:100%;border-collapse:collapse}
th{font-weight:500;color:var(--cyan);text-align:right;padding:7px 12px;border-bottom:1px solid var(--line);font-size:10.5px;letter-spacing:.08em}
th:first-child,td:first-child{text-align:left}
td{padding:6px 12px;text-align:right;border-bottom:1px solid rgba(190,150,255,.08);font-variant-numeric:tabular-nums}
td.act-b{color:var(--up)}td.act-s{color:var(--down)}
dl{display:grid;grid-template-columns:auto 1fr;gap:8px 18px;padding:13px 14px}
dt{color:var(--faint);font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding-top:2px}
dd{color:var(--gold-2);text-align:right;font-size:13.5px}
.note{margin:0;padding:10px 14px;border-top:1px solid var(--line);color:var(--muted);font-family:var(--body);font-size:13px}
.detail{margin-top:26px;color:var(--muted);max-width:74ch;font-size:15.5px}
.others{margin-top:40px}
.others h2{font-family:var(--display);font-size:22px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:12px}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chips a{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  padding:8px 13px;border:1px solid var(--line-strong);color:var(--muted)}
.chips a:hover{border-color:var(--gold);color:var(--gold)}
.cta{margin-top:34px;display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:12px 18px;border:1px solid var(--line-strong)}
.btn:hover{border-color:var(--gold);color:var(--gold)}
.btn.primary{background:linear-gradient(180deg,var(--gold-2),#f2b830);color:#2a1a02;border-color:var(--gold);font-weight:600}
.btn.primary:hover{filter:brightness(1.08);color:#000}
@media (max-width:820px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header class="top">
  <a class="logo" href="/">FINOSTAT</a>
  <div class="r"><span class="live off" id="conn">—</span><a href="/dashboard">TERMINAL</a><a href="/#strategies">ALL STRATEGIES</a></div>
</header>
<main class="wrap">
  <nav class="crumb"><a href="/">FINO</a> · <a href="/#strategies">STRATEGIES</a> · __CODE__</nav>
  <h1>__NAME__</h1>
  <p class="tagline">__BLURB__</p>
  <div class="facts">
    <div>BIAS<b>__BIAS__</b></div>
    <div>VOL VIEW<b>__VOL__</b></div>
    <div>RISK<b>__RISK__</b></div>
    <div>STRUCTURE<b>__TAG__</b></div>
  </div>

  <div class="grid">
    <section class="panel">
      <div class="panel-hd"><span class="k">__CODE__</span><span class="s">PAYOFF AT EXPIRY</span></div>
      <div class="pay"><svg viewBox="0 0 200 78" aria-label="Payoff diagram">
        <line x1="8" y1="48" x2="192" y2="48" stroke="#4a34a0" stroke-width="1" stroke-dasharray="3 3"/>
        <path d="__PAYOFF__" fill="none" stroke="#f5c842" stroke-width="2"/></svg></div>
    </section>
    <section class="panel">
      <div class="panel-hd"><span class="k">LEGS</span><span class="s" id="sym">LIVE CHAIN</span><span class="r" id="upd">—</span></div>
      <table><thead><tr><th>ACTION</th><th>QTY</th><th>TYPE</th><th>STRIKE</th><th>LAST</th></tr></thead>
      <tbody id="legs"></tbody></table>
      <dl id="metrics"></dl>
      <p class="note" id="note" hidden></p>
    </section>
  </div>

  <p class="detail">__DETAIL__</p>

  <div class="cta">
    <a class="btn primary" href="/dashboard">Watch it live on the terminal →</a>
    <a class="btn" href="/#plans">See plans</a>
  </div>

  <div class="others"><h2>Other structures</h2><div class="chips">__OTHERS__</div></div>
</main>
<script>window.SEED=__SEED__;</script>
<script>
(function(){
"use strict";
var SLUG="__SLUG__";
var legsEl=document.getElementById('legs'), metEl=document.getElementById('metrics'),
    noteEl=document.getElementById('note'), conn=document.getElementById('conn'),
    upd=document.getElementById('upd'), symEl=document.getElementById('sym');
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function render(d, live){
  if(!d) return;
  legsEl.innerHTML=(d.legs||[]).map(function(l){
    var cls=l.action==='BUY'?'act-b':'act-s';
    var last=l.price==null?(l.note?esc(l.note):'—'):'₹'+l.price.toFixed(1);
    return '<tr><td class="'+cls+'">'+l.action+'</td><td>'+l.count+'×</td><td>'+l.right+'</td><td>'+l.strike+'</td><td>'+last+'</td></tr>';
  }).join('');
  metEl.innerHTML=(d.metrics||[]).map(function(m){
    return '<dt>'+esc(m[0])+'</dt><dd>'+esc(m[1])+'</dd>';
  }).join('');
  if(d.note){ noteEl.textContent=d.note; noteEl.hidden=false; } else { noteEl.hidden=true; }
  conn.textContent=live?'LIVE':'DELAYED';
  conn.classList.toggle('off',!live);
  upd.textContent=new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false});
}
var seed=window.SEED||null;
if(seed){ symEl.textContent=(seed.symbol||'NIFTY')+' · LIVE CHAIN'; render(seed.strategy, seed.live); }
function poll(){
  fetch('/api/strategies').then(function(r){ return r.json(); }).then(function(all){
    var mine=(all.strategies||[]).filter(function(x){ return x.slug===SLUG; })[0];
    symEl.textContent=(all.symbol||'NIFTY')+' · LIVE CHAIN';
    render(mine, all.live);
  }).catch(function(){ conn.textContent='OFFLINE'; conn.classList.add('off'); });
}
poll(); setInterval(poll, 2500);
})();
</script>
</body>
</html>
"""


def render_strategy(slug: str, snapshot: dict, computed: dict) -> bytes | None:
    import strategies as st
    meta = st.BY_SLUG.get(slug)
    if meta is None:
        return None
    others = "".join(
        f'<a href="/strategies/{c["slug"]}">{c["name"]}</a>'
        for c in st.CATALOG if c["slug"] != slug
    )
    seed = {
        "symbol": snapshot.get("symbol", "NIFTY"),
        "live": bool(snapshot.get("live")),
        "strategy": computed,
    }
    seed_js = json.dumps(seed, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    doc = STRATEGY
    for token, value in (
        ("__SLUG__", slug), ("__NAME__", meta["name"]), ("__CODE__", meta["code"]),
        ("__BLURB__", meta["blurb"]), ("__DETAIL__", meta["detail"]),
        ("__BIAS__", meta["bias"]), ("__VOL__", meta["vol"]), ("__RISK__", meta["risk"]),
        ("__TAG__", meta["tag"]), ("__PAYOFF__", meta["payoff"]),
        ("__OTHERS__", others), ("__SEED__", seed_js),
    ):
        doc = doc.replace(token, value)
    return doc.encode("utf-8")


LOGIN = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — Finostat</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0c0626">
<link rel="icon" href="/og.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0c0626;--panel:#120a33;--panel-hd:#1c1052;--line:#2c1c66;--line-strong:#4a34a0;
  --gold:#f5c842;--gold-2:#ffe27a;--cyan:#7fe0f0;--up:#3dd68c;--down:#ff5c6c;
  --text:#f1edff;--muted:#a89ccf;--faint:#6d609e;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;--body:"IBM Plex Sans",system-ui,sans-serif;
  --display:"Barlow Condensed",Impact,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg)}
html::after{content:"";position:fixed;inset:0;z-index:-1;
  background:radial-gradient(ellipse 70% 45% at 50% 0%,rgba(122,60,245,.5),transparent 70%),var(--bg)}
body{min-height:100vh;display:grid;place-items:center;padding:24px;color:var(--text);
  font-family:var(--body);font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,rgba(200,180,255,.03) 0 1px,transparent 1px 3px)}
a{color:inherit;text-decoration:none}
.card{position:relative;z-index:1;width:min(440px,100%);background:var(--panel);border:1px solid var(--line-strong);
  box-shadow:0 22px 60px rgba(0,0,0,.45)}
.hd{display:flex;align-items:center;gap:12px;padding:8px 14px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);
  font-family:var(--mono);font-size:11px;letter-spacing:.08em}
.hd .k{color:var(--gold);font-weight:600}.hd .s{color:var(--cyan)}
.hd a{margin-left:auto;color:var(--faint)}.hd a:hover{color:var(--gold)}
.body{padding:26px 24px 24px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--gold)}
h1{font-family:var(--display);font-weight:600;font-size:38px;line-height:.95;text-transform:uppercase;margin:8px 0 10px}
p{color:var(--muted)}
form{margin-top:18px}
label{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);margin-bottom:6px}
input[type=email]{width:100%;background:#06031a;border:1px solid var(--line-strong);color:var(--text);
  font:inherit;font-family:var(--mono);font-size:14px;padding:12px 13px;outline:0}
input[type=email]:focus{border-color:var(--gold)}
button{width:100%;margin-top:12px;font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;
  padding:13px 16px;border:1px solid var(--gold);cursor:pointer;font-weight:600;
  background:linear-gradient(180deg,var(--gold-2),#f2b830);color:#2a1a02}
button:hover{filter:brightness(1.08)}
.note{margin-top:16px;font-size:13px;color:var(--faint);line-height:1.5}
.msg{padding:12px 14px;border:1px solid var(--line-strong);font-size:14px;margin-top:4px}
.msg.ok{border-color:var(--up);color:var(--text)}.msg.ok b{color:var(--up)}
.msg.warn{border-color:var(--gold);color:var(--text)}.msg.warn b{color:var(--gold)}
.msg.err{border-color:var(--down);color:var(--text)}.msg.err b{color:var(--down)}
.msg code{font-family:var(--mono);font-size:12px;color:var(--cyan)}
.foot{padding:12px 14px;border-top:1px solid var(--line);font-family:var(--mono);font-size:10.5px;color:var(--faint);letter-spacing:.06em}
</style>
</head>
<body>
<div class="card">
  <div class="hd"><span class="k">AUTH</span><span class="s">SIGN IN · PASSWORDLESS</span><a href="/">← SITE</a></div>
  <div class="body">
    <span class="eyebrow">Finostat account</span>
    <h1>__TITLE__</h1>
    __MESSAGE__
    __FORM__
    <p class="note">No password. We email you a one-time link; it signs you in on the device where you open it, and expires in 15 minutes. First time here? The same link creates your account.</p>
  </div>
  <div class="foot">Sessions last 30 days · sign out any time from the terminal</div>
</div>
</body>
</html>
"""

_LOGIN_FORM = """<form method="post" action="/auth/request">
      <input type="hidden" name="next" value="__NEXT__">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" autocomplete="email" inputmode="email" placeholder="you@example.com" required autofocus>
      <button type="submit">Email me a sign-in link →</button>
    </form>"""


def render_login(state: str = "form", smtp_ok: bool = True, next_: str = "") -> bytes:
    states = {
        "form":    ("Sign in", "", _LOGIN_FORM),
        "sent":    ("Check your inbox",
                    '<div class="msg ok"><b>Link sent.</b> Open the email on this device and click the button. '
                    'Nothing arrives within a minute? Check spam, then request another below.</div>', _LOGIN_FORM),
        "expired": ("Link expired",
                    '<div class="msg warn"><b>That link has expired or was already used.</b> '
                    'Links work once and last 15 minutes. Request a fresh one.</div>', _LOGIN_FORM),
        "invalid": ("Sign in",
                    '<div class="msg err"><b>That doesn\'t look like an email address.</b></div>', _LOGIN_FORM),
        "limited": ("Slow down",
                    '<div class="msg warn"><b>Too many requests.</b> Wait a few minutes, then try again — '
                    'and check your inbox, a link is probably already there.</div>', ""),
        "failed":  ("Couldn't send",
                    '<div class="msg err"><b>The sign-in email could not be sent.</b> This is on our side, '
                    'not yours — try again in a moment.</div>', _LOGIN_FORM),
    }
    title, message, form = states.get(state, states["form"])
    form = form.replace("__NEXT__", html.escape(next_, quote=True))
    if not smtp_ok and state in ("form", "sent"):
        message += ('<div class="msg warn" style="margin-top:8px"><b>Email delivery isn\'t configured on this '
                    'server yet.</b> Links are being logged instead of sent — sign-in works only for the operator.</div>')
    return (LOGIN.replace("__TITLE__", title)
                 .replace("__MESSAGE__", message)
                 .replace("__FORM__", form)).encode("utf-8")
