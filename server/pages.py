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
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
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
.tcmd{display:flex;align-items:center;gap:8px;flex:1;max-width:520px;min-width:160px;border:1px solid var(--line-strong);background:#06031a;padding:0 10px;height:30px;position:relative}
.tcmd .go{color:var(--gold);font-weight:700;font-size:11px;letter-spacing:.1em}
.tcmd input{flex:1;background:none;border:0;outline:0;color:var(--text);font:inherit;font-size:12px;text-transform:uppercase;letter-spacing:.06em;min-width:0}
.tcmd input::placeholder{color:var(--faint);text-transform:none;letter-spacing:0}
.tcmd:focus-within{border-color:var(--gold)}
.tcmd-msg{position:absolute;left:0;top:32px;font-size:10.5px;color:var(--muted);background:var(--panel);border:1px solid var(--line-strong);padding:4px 8px;white-space:nowrap;z-index:6}
.tcmd-msg.bad{color:var(--down)}.tcmd-msg.ok{color:var(--up)}
.help{position:fixed;inset:0;z-index:960;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(6,3,20,.7)}.help[hidden]{display:none}
.help .card{width:100%;max-width:720px;max-height:calc(100vh - 32px);overflow:auto;background:var(--panel);border:1px solid var(--gold);box-shadow:0 30px 80px rgba(0,0,0,.6);font-family:var(--mono);font-size:11.5px}
.help .hd{display:flex;gap:10px;padding:8px 12px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.08em;text-transform:uppercase}.help .hd .k{color:var(--gold);font-weight:600}.help .hd .x{margin-left:auto;background:none;border:0;color:var(--muted);cursor:pointer;font-size:16px}
.help .bd{padding:12px 14px;display:grid;grid-template-columns:1fr 1fr;gap:6px 22px}.help h4{grid-column:1/-1;font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--cyan);margin:8px 0 2px}
.help div{display:flex;gap:10px;align-items:baseline;line-height:1.5}.help code{color:var(--gold);min-width:190px;white-space:nowrap}.help span{color:var(--muted)}
@media(max-width:860px){.tcmd{max-width:none}.help .bd{grid-template-columns:1fr}.help code{min-width:0}}
.top .r{margin-left:auto;display:flex;gap:16px;align-items:center;font-size:11px;color:var(--faint);letter-spacing:.06em}
.top .r a:hover{color:var(--gold)}
.top .home-ic{flex:0 0 auto;width:30px;height:30px;border-radius:9px;overflow:hidden;margin-right:2px;box-shadow:0 0 0 1px rgba(245,200,66,.3)}
.top .home-ic img{width:100%;height:100%;display:block}
.top .home-ic:hover{box-shadow:0 0 0 1px var(--gold),0 0 16px rgba(245,200,66,.45)}
@keyframes fino-glow{0%,100%{box-shadow:0 0 0 1px rgba(245,200,66,.35),0 0 14px rgba(245,200,66,.22)}50%{box-shadow:0 0 0 1px rgba(245,200,66,.7),0 0 26px rgba(245,200,66,.5)}}
@media (prefers-reduced-motion:reduce){.top .home-ic{animation:none}}

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
.a-cas{grid-column:span 2;min-height:420px}
.a-book{grid-column:span 2;min-height:360px}
.a-wide{grid-column:span 2;min-height:380px}
.an .an-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-bottom:1px solid var(--line);font-size:10.5px}
.an .seg button{font-size:10px;letter-spacing:.08em;padding:4px 9px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.an .seg button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.an-sel,.an-in{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:11px;padding:3px 6px}.an-in{width:58px;text-transform:uppercase}
.an-lbl{display:inline-flex;align-items:center;gap:5px;color:var(--faint);letter-spacing:.08em;font-size:9.5px}
.an-btn{font-size:10px;letter-spacing:.1em;padding:5px 11px;border:1px solid var(--gold);color:var(--gold);background:none;cursor:pointer}.an-btn:hover{background:var(--gold);color:#2a1a02}.an-btn:disabled{opacity:.4;cursor:default}
.an-note{color:var(--faint);font-size:10.5px;margin-left:auto}.an-state{color:var(--faint)}.an-state.ok{color:var(--up)}.an-state.err{color:var(--down)}
.an-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.an-kpi div{background:var(--panel);padding:5px 10px}.an-kpi small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.an-kpi b{font-family:var(--display);font-size:19px;font-weight:600;color:var(--gold)}.an-kpi b.c{color:var(--cyan)}.an-kpi b.up{color:var(--up)}.an-kpi b.down{color:var(--down)}.an-kpi b.m{color:var(--text)}
.an-cvw{position:relative;height:230px;flex:0 0 auto;min-width:0}.a-wide .an-cvw{height:270px}.an-split .an-cvw{height:300px}.an-cv{position:absolute;inset:0;width:100%;height:100%;display:block}
.an-foot{padding:6px 10px;border-top:1px solid var(--line);font-size:10px;color:var(--faint);line-height:1.45}
.an-split{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);flex:1;min-height:0}.an-tbl-wrap{border-left:1px solid var(--line);max-height:320px}
.an-table{width:100%;border-collapse:collapse;font-size:11px}.an-table th{position:sticky;top:0;background:var(--panel-hd);color:var(--faint);font-weight:500;font-size:9.5px;letter-spacing:.1em;padding:4px 8px;text-align:right}.an-table th:first-child{text-align:left}
.an-table td{padding:3px 8px;text-align:right;border-bottom:1px solid rgba(190,150,255,.08);font-variant-numeric:tabular-nums}.an-table td:first-child{text-align:left;color:var(--cyan)}.an-table tr.atm td{background:rgba(245,200,66,.1)}.an-table tr.atm td:first-child{color:var(--gold)}
.an-scrub{display:flex;align-items:center;gap:10px;padding:6px 10px;border-bottom:1px solid var(--line)}.an-scrub input{flex:1;accent-color:var(--gold)}.an-scrub b{font-family:var(--display);font-size:18px;color:var(--gold);min-width:56px;text-align:right}
.an-play{display:inline-flex;gap:6px;align-items:center}
@media(max-width:860px){.a-wide{grid-column:span 1}.an-split{grid-template-columns:1fr}.an-tbl-wrap{border-left:0;border-top:1px solid var(--line);max-height:220px}}
.ev-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-bottom:1px solid var(--line);font-size:10.5px}
.ev-top .seg button{font-size:10px;letter-spacing:.08em;padding:4px 9px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.ev-top .seg button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.ev-body{flex:1;overflow:auto;font-size:11px}
.ev-table{width:100%;border-collapse:collapse}.ev-table th{text-align:left;font-weight:500;color:var(--faint);font-size:9.5px;letter-spacing:.08em;padding:4px 8px;border-bottom:1px solid var(--line-strong);position:sticky;top:0;background:var(--panel)}
.ev-table td{padding:5px 8px;border-bottom:1px solid rgba(190,150,255,.07);vertical-align:top}
.ev-table td.d{color:var(--gold);white-space:nowrap;font-weight:600}.ev-table td.d small{display:block;color:var(--faint);font-weight:400;letter-spacing:.06em}
.ev-table .kind{font-size:9px;letter-spacing:.1em;padding:1px 5px;border:1px solid var(--line-strong);color:var(--muted);margin-right:6px}.ev-table .kind.results{color:var(--cyan);border-color:var(--cyan)}.ev-table .kind.macro{color:var(--down);border-color:var(--down)}.ev-table .kind.expiry{color:var(--gold);border-color:var(--gold)}
.ev-table td.mv{white-space:nowrap;text-align:right}.ev-table td.mv b{font-family:var(--display);font-size:17px;color:var(--text)}.ev-table td.mv small{display:block;color:var(--faint);font-size:9.5px}
.ev-table tr.today td{background:rgba(245,200,66,.06)}.ev-table td a{color:var(--cyan);cursor:pointer}
.ev-empty{padding:12px;color:var(--faint);line-height:1.5}
.bk-tot{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.bk-tot div{background:var(--panel);padding:6px 10px}.bk-tot small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.bk-tot b{font-family:var(--display);font-size:20px;font-weight:600}
.bk-body{padding:6px 10px 8px;flex:1;font-size:11px}
.bk-h{font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin:8px 0 4px}
.bk-table{width:100%;border-collapse:collapse;font-size:10.5px}.bk-table th{text-align:right;font-weight:500;color:var(--faint);font-size:9.5px;letter-spacing:.08em;padding:3px 6px;border-bottom:1px solid var(--line-strong)}
.bk-table td{padding:4px 6px;text-align:right;white-space:nowrap;border-bottom:1px solid rgba(190,150,255,.07)}.bk-table th:first-child,.bk-table td:first-child,.bk-table th:nth-child(2),.bk-table td:nth-child(2){text-align:left}
.bk-table td:first-child{color:var(--cyan)}.bk-table .src{font-size:9px;letter-spacing:.1em;color:var(--gold);border:1px solid var(--gold);padding:0 4px;margin-left:5px}
.bk-table button{font-size:9.5px;letter-spacing:.06em;padding:2px 6px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.bk-table button:hover{border-color:var(--gold);color:var(--gold)}
.bk-sc{border-collapse:collapse;font-size:10.5px}.bk-sc th,.bk-sc td{padding:3px 8px;text-align:right;border:1px solid rgba(190,150,255,.08)}.bk-sc th{color:var(--faint);font-weight:500;font-size:9.5px}.bk-sc td.pos{color:var(--up)}.bk-sc td.neg{color:var(--down)}.bk-sc td.now{outline:1px solid var(--gold)}
.bk-empty{color:var(--faint);line-height:1.5;padding:6px 0}
.bk-attr{display:flex;gap:14px;flex-wrap:wrap;font-size:10.5px;color:var(--muted);margin:2px 0 4px}.bk-attr b{color:var(--text)}
.cas-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-bottom:1px solid var(--line);font-size:10.5px}
.cas-top select{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:11px;padding:3px 6px}
.cas-top .seg button{font-size:10px;letter-spacing:.08em;padding:4px 9px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.cas-top .seg button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.cas-top .live{color:var(--up)}.cas-top .off{color:var(--faint)}
.cas-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.cas-kpi div{background:var(--panel);padding:6px 10px}.cas-kpi small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.cas-kpi b{font-family:var(--display);font-size:20px;font-weight:600}
.cas-chart{flex:1;min-height:300px;padding:6px 10px 8px;position:relative}.cas-chart svg{width:100%;height:100%;min-height:290px;display:block}
.cas-legend{display:flex;gap:16px;font-size:10px;color:var(--muted);padding:0 10px 6px}.cas-legend i{display:inline-block;width:14px;height:2px;vertical-align:middle;margin-right:6px}
.cas-empty{padding:14px 12px;color:var(--faint);font-size:11.5px;line-height:1.5}
.cas-tip{position:absolute;pointer-events:none;background:rgba(12,6,38,.95);border:1px solid var(--line-strong);padding:5px 8px;font-size:10.5px;white-space:nowrap;display:none}
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
.a-chart .ch-body{flex:1;min-height:420px;background:#06031a;display:flex;flex-direction:column;min-height:0}
.ch-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:6px 10px;border-bottom:1px solid var(--line);font-size:10.5px;flex-shrink:0}
.ch-tools .seg button{font-size:10px;letter-spacing:.08em;padding:3px 8px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.ch-tools .seg button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.ch-tog{font-size:10px;letter-spacing:.08em;padding:3px 8px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.ch-tog.on{border-color:var(--cyan);color:var(--cyan)}
.ch-ohlc{color:var(--text);font-variant-numeric:tabular-nums}.ch-ohlc b{color:var(--gold)}.ch-ohlc .up{color:var(--up)}.ch-ohlc .down{color:var(--down)}.ch-hint{margin-left:auto;color:var(--faint);font-size:10px}
.ch-wrap{position:relative;flex:1;min-height:360px}#ch-cv{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:crosshair;touch-action:none}
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
  .a-cas,.a-book,.a-chart,.a-wide{grid-column:auto}    /* a span-2 item on a 1-column grid creates an implicit track and collapses the real one */
  .al-form{grid-template-columns:1fr 1fr;grid-auto-rows:auto}
  .al-form button{grid-column:1/-1}
}
@media (prefers-reduced-motion:reduce){.tape-inner{animation:none}.live::before{animation:none}}
</style>
</head>
<body>

<header class="top"><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a>
  <a class="logo" href="/">FINO<b>·</b>TERMINAL</a>
  <span class="sym" id="t-sym">NIFTY · NEAREST EXPIRY</span>
  <form class="tcmd" id="tcmd" autocomplete="off"><span class="go">GO</span><input id="tcmd-in" placeholder="RELIANCE · IC NIFTY 2 · NIFTY 24500 CE · ALERT NIFTY > 24800 · ? for help" aria-label="Command line"><div class="tcmd-msg" id="tcmd-msg" hidden></div></form>
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
<div class="help" id="help" hidden role="dialog" aria-label="Command reference"><div class="card"><div class="hd"><span class="k">HELP</span><span>COMMAND LINE · press / to focus, ? for this card, Esc to close</span><button class="x" type="button" id="help-x" aria-label="Close">×</button></div>
<div class="bd">
<h4>Symbols</h4>
<div><code>RELIANCE</code><span>chart it; if it has options, load it in the builder</span></div>
<div><code>NIFTY · BN · SENSEX · FIN</code><span>index shortcuts (BANKNIFTY, FINNIFTY)</span></div>
<div><code>BSE:RELIANCE</code><span>the BSE listing</span></div>
<div><code>W TCS</code> <span>add to the watchlist (<code>UNW TCS</code> removes)</span></div>
<h4>Analytics</h4>
<div><code>SURF · SKEW · CURV · GEX</code><span>IV surface, vol skew &amp; moneyness, implied distribution, dealer gamma</span></div>
<div><code>RPLY · BKTS</code><span>replay any past expiry day; backtest a structure across expiries since Oct 2024</span></div>
<h4>Options</h4>
<div><code>NIFTY OPT</code><span>open the option chain with OI</span></div>
<div><code>NIFTY 24500 CE</code><span>add a long leg · <code>NIFTY 24500 PE SELL 2</code> for a short of 2</span></div>
<div><code>IC NIFTY 2</code><span>iron condor, 2 lots on the ticket · also SS (short straddle), LS, SG (short strangle), LSG, IF (iron fly), BCS, BPS, FLY, RATIO</span></div>
<div><code>PAPER</code> / <code>TRADE</code><span>journal the built strategy / send it to the broker</span></div>
<h4>Alerts</h4>
<div><code>ALERT NIFTY > 24800</code><span>spot alert on any index or stock</span></div>
<div><code>ALERT STRADDLE < 150</code><span>ATM straddle alert</span></div>
<h4>Panels</h4>
<div><code>BOOK · CAS · CHART · CHAIN · SHEET · ALERTS · WATCH · BUILDER · BROKER · N50 · WIRE · MINI</code><span>jump to a panel (unhides it)</span></div>
<div><code>HIDE WIRE</code> / <code>SHOW WIRE</code><span>layout without the menu</span></div>
<div><code>BRIEF · FINCH · ACCOUNT · HOME</code><span>open a page</span></div>
<h4>Keys</h4>
<div><code>/</code><span>focus the command line</span></div>
<div><code>Esc</code><span>close this card, the ticket, or blur</span></div>
<div><code>F1–F8</code><span>panel shortcuts (bottom bar)</span></div>
</div></div></div>
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

  <section class="panel" id="p-events" aria-label="Event calendar">
    <div class="panel-hd"><span class="k">EVNT</span><span class="s">EVENTS · IMPLIED MOVE PRICED</span><span class="r"><span id="ev-state">—</span></span></div>
    <div class="ev-top"><span class="seg" id="ev-filter"><button type="button" data-k="all" class="on">ALL</button><button type="button" data-k="expiry">EXPIRIES</button><button type="button" data-k="results">RESULTS</button><button type="button" data-k="macro">MACRO</button></span><span style="color:var(--faint)">next 21 days · move = ATM straddle of the expiry spanning the date · click a row to load it in the builder</span></div>
    <div class="ev-body" id="ev-body"><div class="ev-empty">loading…</div></div>
  </section>
  <section class="panel a-book" id="p-book" aria-label="Positions book">
    <div class="panel-hd"><span class="k">BOOK</span><span class="s">POSITIONS · NET GREEKS · WHAT-IF</span><span class="r"><span id="bk-state">—</span></span></div>
    <div class="bk-tot" id="bk-tot"></div>
    <div class="bk-body" id="bk-body"><div class="bk-empty">loading…</div></div>
  </section>
  <section class="panel a-cas" id="p-cas" aria-label="Closing auction session">
    <div class="panel-hd"><span class="k">CAS</span><span class="s" id="cas-title">CLOSING AUCTION · IEP vs SYNTHETIC FUTURE</span><span class="r"><span id="cas-state">—</span></span></div>
    <div class="cas-top"><span class="seg" id="cas-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span>
      <select id="cas-date" aria-label="Session date"></select><span id="cas-note" style="color:var(--faint)">records 15:15–15:40 IST every trading day · ATM frozen at 15:15</span></div>
    <div class="cas-kpi" id="cas-kpi"></div>
    <div class="cas-chart"><svg id="cas-svg" viewBox="0 0 900 300" preserveAspectRatio="none" aria-label="IEP vs synthetic future"></svg><div class="cas-tip" id="cas-tip"></div></div>
    <div class="cas-legend"><span><i style="background:#7fe0f0"></i>Index IEP / level</span><span><i style="background:#f5c842"></i>Synthetic future (ATM + CE − PE)</span><span><i style="background:#ff5c6c;height:1px"></i>3:15 reference</span></div>
  </section>
  <section class="panel a-chart" id="p-chart" aria-label="Chart">
    <div class="panel-hd"><span class="k">CHRT</span><span class="s" id="ch-sym">NIFTY 50</span><span class="ch-note" id="ch-note">click any symbol on the desk to chart it</span>
      <span class="r"><span class="live off" id="ch-state">—</span></span></div>
    <div class="ch-body">
      <div class="ch-tools"><span class="seg" id="ch-tf"><button type="button" data-tf="1m">1m</button><button type="button" data-tf="5m" class="on">5m</button><button type="button" data-tf="15m">15m</button><button type="button" data-tf="1h">1h</button><button type="button" data-tf="D">D</button></span><button type="button" class="ch-tog on" id="ch-vp" title="Volume profile of the visible range">VP</button><span class="ch-ohlc" id="ch-ohlc">—</span><span class="ch-hint">scroll to zoom · drag to pan · NSE &amp; BSE data via Upstox</span></div>
      <div class="ch-wrap"><canvas id="ch-cv"></canvas></div>
    </div>
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
      <div class="bl-tools"><button type="button" id="bl-add">+ LEG</button><button type="button" id="bl-chain-btn" title="Option chain with open interest">CHAIN</button><button type="button" id="bl-paper" title="Save these legs as a paper position in the BOOK">PAPER</button><button type="button" id="bl-trade" title="Send these legs to your connected broker">TRADE</button><span id="bl-lot"></span></div>
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


  <section class="panel a-wide an" id="p-surf" aria-label="IV surface">
    <div class="panel-hd"><span class="k">SURF</span><span class="s">IV SURFACE · RICH/CHEAP</span><span class="r"><span class="an-state" id="surf-state">—</span></span></div>
    <div class="an-top"><span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span><span class="seg" id="surf-mode"><button type="button" data-m="iv" class="on">IV %</button><button type="button" data-m="rich">RICH / CHEAP</button></span><span class="an-note" id="surf-note">hover a cell</span></div>
    <div class="an-kpi" id="surf-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="surf-cv"></canvas></div>
    <div class="an-foot">Moneyness = ln(K/S). Rich/cheap = each strike's IV against its expiry's own fitted smile, in vol points: magenta is expensive, cyan is cheap. Exchange IVs and OI via Upstox; refreshes every minute.</div>
  </section>
  <section class="panel an" id="p-skew" aria-label="Vol skew and moneyness">
    <div class="panel-hd"><span class="k">SKEW</span><span class="s">VOL SKEW · MONEYNESS</span><span class="r"><span class="an-state" id="skew-state">—</span></span></div>
    <div class="an-top"><span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span><select class="an-sel an-exp" aria-label="Expiry"></select><span class="seg" id="skew-x"><button type="button" data-x="strike" class="on">STRIKE</button><button type="button" data-x="m">MONEYNESS</button><button type="button" data-x="delta">DELTA</button></span></div>
    <div class="an-kpi" id="skew-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="skew-cv"></canvas></div>
    <div class="an-foot" id="skew-note">CE IV cyan · PE IV magenta · fitted smile gold. 25Δ risk reversal = put IV − call IV; butterfly = wing average − ATM.</div>
  </section>
  <section class="panel an" id="p-curv" aria-label="Implied distribution">
    <div class="panel-hd"><span class="k">CURV</span><span class="s">IMPLIED DISTRIBUTION</span><span class="r"><span class="an-state" id="curv-state">—</span></span></div>
    <div class="an-top"><span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span><select class="an-sel an-exp" aria-label="Expiry"></select></div>
    <div class="an-kpi" id="curv-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="curv-cv"></canvas></div>
    <div class="an-foot">Risk-neutral density from the option chain (Breeden–Litzenberger on the fitted smile). Gold = what the market prices; dashed = a no-skew lognormal at ATM vol. Shaded band = 16th–84th percentile.</div>
  </section>
  <section class="panel an" id="p-gex" aria-label="Dealer gamma exposure">
    <div class="panel-hd"><span class="k">GEX</span><span class="s">DEALER GAMMA BY STRIKE</span><span class="r"><span class="an-state" id="gex-state">—</span></span></div>
    <div class="an-top"><span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span><select class="an-sel an-exp" aria-label="Expiry"></select></div>
    <div class="an-kpi" id="gex-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="gex-cv"></canvas></div>
    <div class="an-foot">₹ crore of dealer gamma per 1% move. Calls sold to dealers count positive (they hedge against the move), puts negative (they hedge with it). Gold line = cumulative; the flip is where it crosses zero.</div>
  </section>
  <section class="panel a-wide an" id="p-rply" aria-label="Historical replay">
    <div class="panel-hd"><span class="k">RPLY</span><span class="s">HISTORICAL REPLAY · EXPIRY DAYS</span><span class="r"><span class="an-state" id="rp-state">—</span></span></div>
    <div class="an-top"><span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span><select class="an-sel" id="rp-date" aria-label="Expiry day"></select><button type="button" class="an-btn" id="rp-load">LOAD DAY</button>
      <span class="an-play"><button type="button" class="an-btn" id="rp-play" disabled>▶ PLAY</button><select class="an-sel" id="rp-speed"><option value="4">1 min / 250 ms</option><option value="10">1 min / 100 ms</option><option value="1">1 min / 1 s</option></select></span>
      <span class="an-note" id="rp-note">pick an expiry day and load it — 1-minute candles, ATM ±5 strikes</span></div>
    <div class="an-scrub"><input type="range" id="rp-t" min="0" max="0" value="0" step="1" disabled aria-label="Time"><b id="rp-time">--:--</b></div>
    <div class="an-kpi" id="rp-kpi"></div>
    <div class="an-split"><div class="an-cvw"><canvas class="an-cv" id="rp-cv"></canvas></div>
      <div class="scroll an-tbl-wrap"><table class="an-table"><thead><tr><th>STRIKE</th><th>CE</th><th>PE</th><th>CE+PE</th></tr></thead><tbody id="rp-rows"></tbody></table></div></div>
  </section>
  <section class="panel a-wide an" id="p-bkts" aria-label="Backtesting">
    <div class="panel-hd"><span class="k">BKTS</span><span class="s">EXPIRY-DAY BACKTEST</span><span class="r"><span class="an-state" id="bt-state">—</span></span></div>
    <div class="an-top"><span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span><select class="an-sel" id="bt-strat" aria-label="Strategy"><option value="short_straddle">Short straddle</option><option value="short_strangle">Short strangle</option><option value="iron_fly">Iron fly</option><option value="iron_condor">Iron condor</option><option value="long_straddle">Long straddle</option><option value="long_strangle">Long strangle</option></select>
      <label class="an-lbl">IN <input class="an-in" id="bt-entry" value="10:00" maxlength="5" aria-label="Entry time"></label><label class="an-lbl">OUT <input class="an-in" id="bt-exit" value="15:15" maxlength="5" aria-label="Exit time"></label>
      <label class="an-lbl">WINGS <select class="an-sel" id="bt-wings"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label>
      <label class="an-lbl">EXPIRIES <select class="an-sel" id="bt-n"><option value="26">last 26</option><option value="52" selected>last 52</option><option value="104">last 104</option><option value="400">all</option></select></label>
      <button type="button" class="an-btn" id="bt-run">RUN</button><span class="an-note" id="bt-note">1-minute closes on each past expiry day since Oct 2024 · no slippage or costs</span></div>
    <div class="an-kpi" id="bt-kpi"></div>
    <div class="an-split"><div class="an-cvw"><canvas class="an-cv" id="bt-cv"></canvas></div>
      <div class="scroll an-tbl-wrap"><table class="an-table"><thead><tr><th>EXPIRY</th><th>ATM</th><th>MOVE</th><th>CREDIT</th><th>P&amp;L / LOT</th><th>MAE</th></tr></thead><tbody id="bt-rows"></tbody></table></div></div>
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
var PANELS=[['sheet','BFLY sheet'],['events','Events'],['book','Positions book'],['cas','Closing auction'],['chart','Chart'],['straddle','Straddle chart'],['alerts','Alerts'],['watch','Watchlist'],['builder','Strategy builder'],['broker','Broker'],['n50','Nifty 50'],['wire','News wire'],['mini','Mini sheet'],['surf','IV surface'],['skew','Vol skew'],['curv','Implied distribution'],['gex','Gamma exposure'],['rply','Replay'],['bkts','Backtest']];
/* ---------- command line ---------- */
var tcmdIn=document.getElementById('tcmd-in'), tcmdMsg=document.getElementById('tcmd-msg'), helpEl=document.getElementById('help');
var PRESET_ALIAS={IC:'iron-condor',CONDOR:'iron-condor',IF:'iron-fly',IRONFLY:'iron-fly',SS:'short-straddle',STRADDLE:'short-straddle',LS:'long-straddle',SG:'short-strangle',STRANGLE:'short-strangle',LSG:'long-strangle',BCS:'bull-call-spread',BPS:'bear-put-spread',FLY:'butterfly',BFLY:'butterfly',BUTTERFLY:'butterfly',RATIO:'ratio-spread'};
var PANEL_ALIAS={EVENTS:'events',EVENT:'events',CAL:'events',CALENDAR:'events',ECO:'events',BOOK:'book',CAS:'cas',CHART:'chart',CHRT:'chart',SHEET:'sheet',BFLY:'sheet',STRADDLE:'straddle',ALERTS:'alerts',ALERT:'alerts',ALRT:'alerts',WATCH:'watch',WL:'watch',BUILDER:'builder',BLDR:'builder',STRAT:'builder',BROKER:'broker',BRKR:'broker',N50:'n50',NIFTY50:'n50',WIRE:'wire',NEWS:'wire',MINI:'mini',SURF:'surf',SURFACE:'surf',IVS:'surf',SKEW:'skew',SMILE:'skew',MONEY:'skew',MONEYNESS:'skew',CURV:'curv',CURVE:'curv',BELL:'curv',DIST:'curv',GEX:'gex',GAMMA:'gex',RPLY:'rply',REPLAY:'rply',BKTS:'bkts',BACKTEST:'bkts',BT:'bkts'};
var INDEX_ALIAS={NIFTY:'NIFTY 50','NIFTY50':'NIFTY 50','NIFTY 50':'NIFTY 50',BN:'BANKNIFTY',BANKNIFTY:'BANKNIFTY',NIFTYBANK:'BANKNIFTY',SENSEX:'SENSEX',SX:'SENSEX',FIN:'FINNIFTY',FINNIFTY:'FINNIFTY',VIX:'INDIA VIX',INDIAVIX:'INDIA VIX'};
function say(msg,kind){ tcmdMsg.textContent=msg; tcmdMsg.className='tcmd-msg '+(kind||''); tcmdMsg.hidden=false; clearTimeout(say.t); say.t=setTimeout(function(){ tcmdMsg.hidden=true; },3500); }
function goPanel(id){ var el=document.getElementById('p-'+id); if(!el) return false; if(el.hidden){ var hide=(prefs.layout=prefs.layout||{hide:[]}).hide=prefs.layout.hide||[]; var i=hide.indexOf(id); if(i>=0) hide.splice(i,1); applyLayout(); savePrefs(); } el.scrollIntoView({behavior:'smooth',block:'start'}); return true; }
function resolveSym(tok){ tok=tok.toUpperCase(); if(INDEX_ALIAS[tok]) return Promise.resolve({key:INDEX_ALIAS[tok],index:true});
  var k=tok.indexOf(':')>0?tok:'NSE:'+tok; var known=bl.unders.filter(function(x){ return x.key===k||x.label===tok||x.label===k; })[0]; if(known) return Promise.resolve({key:known.key,fo:true});
  return fetch('/api/symbols?q='+encodeURIComponent(tok)+'&limit=3',{credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){ var hits=(d.symbols||d.results||d||[]); var hit=hits.filter(function(x){ return (x.key||'').toUpperCase()===k||(x.symbol||'').toUpperCase()===tok; })[0]||hits[0]; return hit?{key:hit.key,fo:!!hit.fo}:null; }).catch(function(){ return null; }); }
function withChain(key, fn){ bl.after=fn; selectUnderlying(key); }
function cmdAlert(symTok, cmp, value){
  var m=null, key=null;
  if(symTok==='STRADDLE') m='straddle';
  return (m?Promise.resolve({key:'straddle'}):resolveSym(symTok)).then(function(s){ if(!s) return say('unknown symbol '+symTok,'bad'); key=s.key; var metricId=m||('spot:'+key);
    if(serverAlerts){ return srvPost('/api/alerts',{metric:metricId,strike:null,cmp:cmp,value:value,email:true}).then(function(r){ if(r&&r.error) return say('not armed: '+r.error,'bad'); say('alert armed: '+key+' '+cmp+' '+value+' (email)','ok'); loadServerAlerts(); }); }
    alerts.push({metric:metricId,strike:null,cmp:cmp,value:value,state:'armed',created:Date.now()}); saveAlerts(); renderAlerts(); pollStocks(); say('alert armed in this browser: '+key+' '+cmp+' '+value+' — sign in for email alerts','ok'); goPanel('alerts'); });
}
function runCommand(raw){
  var t=raw.trim().replace(/\s+/g,' '); if(!t) return; var U=t.toUpperCase(), a=U.split(' ');
  if(U==='?'||U==='HELP'){ helpEl.hidden=false; return; }
  if(U==='BRIEF'){ window.open('/brief','_blank'); return say('opening the brief'); }
  if(U==='FINCH'){ window.open('/finch','_blank'); return say('opening Finch'); }
  if(U==='ACCOUNT'||U==='PLAN'||U==='PLANS'){ location.href='/account'; return; }
  if(U==='HOME'||U==='SITE'){ location.href='/'; return; }
  if(U==='PAPER'){ document.getElementById('bl-paper').click(); return; }
  if(U==='TRADE'||U==='TICKET'){ openTicket(); return; }
  if(U==='CHAIN'||U==='OPT'){ if(!bl.u) return say('load an underlying first, e.g. NIFTY OPT','bad'); if(!bl.chainOpen) document.getElementById('bl-chain-btn').click(); goPanel('builder'); return say('chain · '+bl.u,'ok'); }
  if((a[0]==='HIDE'||a[0]==='SHOW')&&a[1]&&PANEL_ALIAS[a[1]]){ var id=PANEL_ALIAS[a[1]], hide=(prefs.layout=prefs.layout||{hide:[]}).hide=prefs.layout.hide||[]; var i=hide.indexOf(id); if(a[0]==='HIDE'&&i<0) hide.push(id); if(a[0]==='SHOW'&&i>=0) hide.splice(i,1); applyLayout(); savePrefs(); return say((a[0]==='HIDE'?'hidden ':'shown ')+id,'ok'); }
  if(a.length===1&&PANEL_ALIAS[U]){ goPanel(PANEL_ALIAS[U]); return say('→ '+PANEL_ALIAS[U],'ok'); }
  if((a[0]==='W'||a[0]==='WATCH'||a[0]==='UNW'||a[0]==='UNWATCH')&&a[1]){ var rm=a[0].indexOf('UN')===0; return resolveSym(a[1]).then(function(s){ if(!s) return say('unknown symbol '+a[1],'bad'); prefs.watchlist=prefs.watchlist||[]; var j=prefs.watchlist.indexOf(s.key); if(rm){ if(j>=0) prefs.watchlist.splice(j,1); } else if(j<0) prefs.watchlist.push(s.key); renderWatch(); savePrefs(); pollStocks(); goPanel('watch'); say((rm?'removed ':'watching ')+s.key,'ok'); }); }
  if(a[0]==='ALERT'&&a.length>=4){ var cmp=a[2][0]==='>'?'>=':(a[2][0]==='<'?'<=':''); var v=parseFloat(a[3]); if(!cmp||isNaN(v)) return say('ALERT <SYMBOL> > 24800','bad'); return cmdAlert(a[1],cmp,v); }
  if(PRESET_ALIAS[a[0]]&&a[1]){ var preset=PRESET_ALIAS[a[0]], lots=parseInt(a[2],10)||1; return resolveSym(a[1]).then(function(s){ if(!s||!(s.index||s.fo)) return say(a[1]+' has no options','bad'); withChain(s.key,function(){ bl.preset=preset; bl.legs=[]; priceStrategy(); document.getElementById('tk-lots').value=lots; }); goPanel('builder'); say(preset.replace(/-/g,' ')+' · '+s.key+' · '+lots+' lot'+(lots>1?'s':''),'ok'); }); }
  var legm=U.match(/^(\S+(?: 50)?) (\d{3,6}) (CE|PE)(?: (BUY|SELL|B|S))?(?: (\d{1,2}))?$/);
  if(legm){ var strike=Number(legm[2]), right=legm[3], side=(legm[4]||'BUY')[0]==='S'?-1:1, q=(parseInt(legm[5],10)||1)*side; return resolveSym(legm[1]).then(function(s){ if(!s||!(s.index||s.fo)) return say(legm[1]+' has no options','bad');
      var add=function(d){ if(d.strikes.indexOf(strike)<0) return say(strike+' is outside the loaded chain (ATM ±10)','bad'); bl.legs=bl.legs.concat([{right:right,strike:strike,qty:q}]); bl.preset=null; priceStrategy(); say((q>0?'buy ':'sell ')+Math.abs(q)+'× '+strike+' '+right+' · '+s.key,'ok'); };
      if(bl.u===s.key&&bl.strikes.length) add({strikes:bl.strikes}); else withChain(s.key,add); goPanel('builder'); }); }
  if(a.length===2&&(a[1]==='OPT'||a[1]==='CHAIN'||a[1]==='OPTIONS')){ return resolveSym(a[0]).then(function(s){ if(!s||!(s.index||s.fo)) return say(a[0]+' has no options','bad'); withChain(s.key,function(){ if(!bl.chainOpen) document.getElementById('bl-chain-btn').click(); }); goPanel('builder'); say('chain · '+s.key,'ok'); }); }
  if(a.length===1){ return resolveSym(a[0]).then(function(s){ if(!s) return say('unknown: '+t+' — ? for help','bad'); chartTo(s.key); if(s.index||s.fo) selectUnderlying(s.key); goPanel('chart'); say('charted '+s.key+(s.index||s.fo?' · builder loaded':''),'ok'); }); }
  say('unknown: '+t+' — ? for help','bad');
}
document.getElementById('tcmd').addEventListener('submit',function(e){ e.preventDefault(); var v=tcmdIn.value; tcmdIn.value=''; runCommand(v); });
document.getElementById('help-x').addEventListener('click',function(){ helpEl.hidden=true; });
document.addEventListener('keydown',function(e){
  var inField=/^(INPUT|TEXTAREA|SELECT)$/.test((e.target&&e.target.tagName)||'');
  if(e.key==='Escape'){ if(!helpEl.hidden){ helpEl.hidden=true; return; } var tkEl=document.getElementById('tk'); if(tkEl&&!tkEl.hidden){ tkEl.hidden=true; return; } if(inField) e.target.blur(); return; }
  if(inField) return;
  if(e.key==='/'){ e.preventDefault(); tcmdIn.focus(); }
  else if(e.key==='?'){ e.preventDefault(); helpEl.hidden=false; }
});
/* ---------- EVENTS: calendar with the premium attached ---------- */
var evBody=document.getElementById('ev-body'), evState=document.getElementById('ev-state'), evPanel=document.getElementById('p-events'), evFilter='all', evData=null;
function renderEvents(d){
  evData=d; var rows=(d.events||[]).filter(function(e){ return evFilter==='all'||e.kind===evFilter; });
  evState.textContent=(d.counts?d.counts.expiry+' exp · '+d.counts.results+' results · '+d.counts.macro+' macro':'')+(d.results_error?' · results feed down':'');
  if(!rows.length){ evBody.innerHTML='<div class="ev-empty">Nothing in the next '+d.days+' days'+(evFilter!=='all'?' for this filter':'')+'.</div>'; return; }
  evBody.innerHTML='<table class="ev-table"><thead><tr><th>DATE</th><th>EVENT</th><th style="text-align:right">IMPLIED MOVE</th></tr></thead><tbody>'+rows.map(function(e){
    var dt=new Date(e.date+'T00:00:00+05:30'), day=dt.toLocaleDateString('en-IN',{weekday:'short'}), dm=dt.toLocaleDateString('en-IN',{day:'2-digit',month:'short'});
    var days=Math.round((dt-new Date(d.today+'T00:00:00+05:30'))/864e5), when=days===0?'today':days===1?'tomorrow':'in '+days+'d';
    var mv=e.move, mvh=mv?(mv.warming?'<small>pricing…</small>':'<b>±'+mv.pct.toFixed(2)+'%</b><small>straddle ₹'+fmt(mv.straddle)+' · '+new Date(mv.expiry).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+' expiry</small>'):(e.segment?'<small>—</small>':'<small>—</small>');
    return '<tr'+(days===0?' class="today"':'')+' data-u="'+esc(e.u)+'" data-exp="'+(e.expiry||(mv&&mv.expiry)||'')+'"><td class="d">'+dm+'<small>'+day+' · '+when+'</small></td><td><span class="kind '+e.kind+'">'+e.kind+'</span><a>'+esc(e.title)+'</a>'+(e.detail?'<div style="color:var(--faint);font-size:10px;margin-top:2px">'+esc(e.detail)+'</div>':'')+'</td><td class="mv">'+mvh+'</td></tr>'; }).join('')+'</tbody></table>';
}
function pollEvents(){ if(window.FINO_LOCKED||evPanel.hidden) return; fetch('/api/events?days=21',{credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){ if(d&&d.events) renderEvents(d); }).catch(function(){}); }
document.getElementById('ev-filter').addEventListener('click',function(e){ var b=e.target.closest('button[data-k]'); if(!b) return; evFilter=b.getAttribute('data-k'); Array.prototype.forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); if(evData) renderEvents(evData); });
evBody.addEventListener('click',function(e){ var tr=e.target.closest('tr[data-u]'); if(!tr) return; var u=tr.getAttribute('data-u'), exp=Number(tr.getAttribute('data-exp'))||null; if(/^NSE:|^BSE:/.test(u)&&!bl.unders.some(function(x){ return x.key===u; })){ chartTo(u); return; } withChain(u,function(){ if(exp){ bl.expiry=exp; bl.legs=[]; priceStrategy(); } }); goPanel('builder'); });
setTimeout(pollEvents,1500); setInterval(pollEvents,60000);
/* ---------- BOOK: positions, net greeks, what-if ---------- */
var bkTot=document.getElementById('bk-tot'), bkBody=document.getElementById('bk-body'), bkState=document.getElementById('bk-state'), bkPanel=document.getElementById('p-book');
function rupee(v,d){ if(v==null) return '—'; return (v<0?'−':'')+'₹'+fmt(Math.abs(v),d==null?0:d); }
function renderBook(d){
  var t=d.totals||{}, g=t.greeks||{}, a=t.attribution||{};
  bkTot.innerHTML=[['open P&L',rupee(t.pnl),t.pnl],['today',rupee(t.day_pnl),t.day_pnl],['net delta (₹/pt)',g.delta!=null?fmt(g.delta,1):'—',null],['gamma',g.gamma!=null?fmt(g.gamma,2):'—',null],['theta /day',rupee(g.theta),g.theta],['vega /1% IV',rupee(g.vega),g.vega],['positions',(t.open||0)+(t.unpriced?' ('+t.unpriced+' unpriced)':''),null]]
    .map(function(x){ return '<div><small>'+x[0]+'</small><b'+(x[2]!=null?' class="'+(x[2]>=0?'up':'down')+'"':'')+'>'+x[1]+'</b></div>'; }).join('');
  bkState.textContent=(d.positions||[]).length?((d.positions.length)+' open'+(d.broker?' · broker linked':'')):'empty';
  var h='';
  if(!(d.positions||[]).length){ h+='<div class="bk-empty">No open positions. Build a strategy and press <b>PAPER</b> to journal it at today\'s prices — the book marks it live, nets the Greeks and shows what a move would do. Positions at a connected broker appear here automatically.</div>'; }
  else {
    h+='<div class="bk-attr">today\'s P&L ≈ <b>delta '+rupee(a.delta)+'</b> + <b>theta '+rupee(a.theta)+'</b> + <b>gamma/vega/other '+rupee(a.other)+'</b></div>';
    h+='<div class="bl-scroll"><table class="bk-table"><thead><tr><th>UNDERLYING</th><th>LEGS</th><th>LOTS</th><th>P&L</th><th>TODAY</th><th>Δ</th><th>Θ/day</th><th>V</th><th></th></tr></thead><tbody>'+d.positions.map(function(p){
      var exp=new Date(p.expiry).toLocaleDateString('en-IN',{day:'2-digit',month:'short'});
      return '<tr><td>'+esc(p.u)+' <small style="color:var(--faint)">'+exp+'</small>'+(p.source==='upstox'?'<span class="src">UPSTOX</span>':'')+'</td><td title="'+esc(p.note||'')+'">'+esc(p.label)+(p.priced?'':' <small style="color:var(--down)">unpriced</small>')+'</td><td>'+p.lots+'</td><td class="'+(p.pnl>=0?'up':'down')+'">'+rupee(p.pnl)+'</td><td class="'+(p.day_pnl>=0?'up':'down')+'">'+rupee(p.day_pnl)+'</td><td>'+fmt(p.greeks.delta,1)+'</td><td>'+rupee(p.greeks.theta)+'</td><td>'+rupee(p.greeks.vega)+'</td><td>'+(p.source==='paper'?'<button type="button" data-close="'+p.id+'">close</button> <button type="button" data-del="'+p.id+'" title="delete without recording">✕</button>':'')+'</td></tr>'; }).join('')+'</tbody></table></div>';
    var sc=d.scenarios; if(sc){ h+='<div class="bk-h">What-if · book P&L vs now (spot shift × IV shift)</div><div class="bl-scroll" style="display:flex;gap:18px;flex-wrap:wrap">';
      ['0','1'].forEach(function(day){ h+='<table class="bk-sc"><thead><tr><th>'+(day==='0'?'today':'tomorrow')+'</th>'+sc.spot_shifts.map(function(s){ return '<th>'+(s>0?'+':'')+s+'%</th>'; }).join('')+'</tr></thead><tbody>'+sc.iv_shifts.map(function(iv,i){ return '<tr><th>IV '+(iv>0?'+':'')+iv+'</th>'+sc.grid[day][i].map(function(v,j){ return '<td class="'+(v>0?'pos':v<0?'neg':'')+((iv===0&&sc.spot_shifts[j]===0&&day==='0')?' now':'')+'">'+rupee(v)+'</td>'; }).join('')+'</tr>'; }).join('')+'</tbody></table>'; });
      h+='</div>'; }
  }
  if((d.closed||[]).length){ h+='<div class="bk-h">Closed (paper journal)</div><div class="bl-scroll"><table class="bk-table"><thead><tr><th>UNDERLYING</th><th>LEGS</th><th>LOTS</th><th>OPENED</th><th>CLOSED</th><th>REALISED</th></tr></thead><tbody>'+d.closed.map(function(p){
      var real=0, ok=true; p.legs.forEach(function(l,i){ var e=p.entries[i], x=p.exits?p.exits[i]:null; if(e==null||x==null){ ok=false; return; } real+=(x-e)*l.qty*p.lots*p.lot; });
      return '<tr><td>'+esc(p.u)+'</td><td>'+p.legs.map(function(l){ return (l.qty>0?'+':'−')+Math.abs(l.qty)+' '+l.strike+' '+l.right; }).join(' · ')+'</td><td>'+p.lots+'</td><td>'+new Date(p.opened*1000).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+'</td><td>'+new Date(p.closed*1000).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+'</td><td class="'+(real>=0?'up':'down')+'">'+(ok?rupee(real):'—')+'</td></tr>'; }).join('')+'</tbody></table></div>'; }
  bkBody.innerHTML=h;
}
function pollBook(){
  if(window.FINO_LOCKED||bkPanel.hidden) return;
  fetch('/api/book',{credentials:'same-origin'}).then(function(r){ return r.json().then(function(d){ d._st=r.status; return d; }); }).then(function(d){
    if(d._st===401){ bkState.textContent='sign in'; bkBody.innerHTML='<div class="bk-empty">Sign in to keep a book.</div>'; return; }
    if(d._st!==200) return; renderBook(d);
  }).catch(function(){});
}
bkBody.addEventListener('click',function(e){
  var c=e.target.closest('button[data-close]'); if(c){ if(!confirm('Close this paper position at the current marks?')) return; srvPost('/api/book/close',{id:Number(c.getAttribute('data-close'))}).then(pollBook); return; }
  var x=e.target.closest('button[data-del]'); if(x){ if(!confirm('Delete this paper position without recording it?')) return; srvPost('/api/book/delete',{id:Number(x.getAttribute('data-del'))}).then(pollBook); }
});
setTimeout(pollBook,1100); setInterval(pollBook,5000);
window.finoBookPoll=pollBook;
/* ---------- CAS: index IEP vs synthetic future ---------- */
var casState={u:'NIFTY 50',date:'',data:null,timer:null};
var casSvg=document.getElementById('cas-svg'), casKpi=document.getElementById('cas-kpi'), casDate=document.getElementById('cas-date'), casTip=document.getElementById('cas-tip'), casPanel=document.getElementById('p-cas'), casStateEl=document.getElementById('cas-state');
function hhmm(ts){ var d=new Date(ts*1000); return d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZone:'Asia/Kolkata'}); }
function drawCas(d){
  var pts=(d.points||[]).filter(function(p){ return p[1]!=null||p[2]!=null; });
  if(!pts.length){ casSvg.innerHTML='<text x="450" y="150" text-anchor="middle" fill="#6d609e" font-size="13" font-family="IBM Plex Mono,monospace">'+(d.live?'waiting for the first ticks…':'no session recorded for '+esc(d.date)+' — the recorder runs 15:15–15:40 IST on trading days')+'</text>'; return; }
  var t0=pts[0][0], t1=Math.max(pts[pts.length-1][0], t0+60), W=900,H=300,L=64,R=14,T=12,B=28;
  var vals=[]; pts.forEach(function(p){ if(p[1]!=null) vals.push(p[1]); if(p[2]!=null) vals.push(p[2]); }); if(d.ref!=null) vals.push(d.ref);
  var lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals), pad=(hi-lo||10)*0.06; lo-=pad; hi+=pad;
  var X=function(t){ return L+(t-t0)/(t1-t0)*(W-L-R); }, Y=function(v){ return T+(hi-v)/(hi-lo)*(H-T-B); };
  var path=function(i){ var s='',pen=false; pts.forEach(function(p){ if(p[i]==null){ pen=false; return; } s+=(pen?'L':'M')+X(p[0]).toFixed(1)+' '+Y(p[i]).toFixed(1)+' '; pen=true; }); return s; };
  var g=''; var steps=5; for(var k=0;k<=steps;k++){ var v=lo+(hi-lo)*k/steps, y=Y(v); g+='<line x1="'+L+'" y1="'+y.toFixed(1)+'" x2="'+(W-R)+'" y2="'+y.toFixed(1)+'" stroke="rgba(74,52,160,.35)" stroke-dasharray="2 4"/><text x="'+(L-6)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" fill="#6d609e" font-size="10" font-family="IBM Plex Mono,monospace">'+fmt(v,0)+'</text>'; }
  var ticks=6; for(var j=0;j<=ticks;j++){ var tt=t0+(t1-t0)*j/ticks, x=X(tt); g+='<line x1="'+x.toFixed(1)+'" y1="'+T+'" x2="'+x.toFixed(1)+'" y2="'+(H-B)+'" stroke="rgba(74,52,160,.2)"/><text x="'+x.toFixed(1)+'" y="'+(H-10)+'" text-anchor="middle" fill="#6d609e" font-size="10" font-family="IBM Plex Mono,monospace">'+hhmm(tt).slice(0,5)+'</text>'; }
  if(d.ref!=null) g+='<line x1="'+L+'" y1="'+Y(d.ref).toFixed(1)+'" x2="'+(W-R)+'" y2="'+Y(d.ref).toFixed(1)+'" stroke="#ff5c6c" stroke-width="1" stroke-dasharray="6 4" opacity=".8"/>';
  g+='<path d="'+path(2)+'" fill="none" stroke="#f5c842" stroke-width="1.8" vector-effect="non-scaling-stroke"/>';
  g+='<path d="'+path(1)+'" fill="none" stroke="#7fe0f0" stroke-width="1.8" vector-effect="non-scaling-stroke"/>';
  casSvg.innerHTML=g; casSvg._map={pts:pts,t0:t0,t1:t1,L:L,R:R,W:W};
}
function renderCas(d){
  casState.data=d; var st=d.stats||{};
  var exp=d.expiry?new Date(d.expiry).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'—';
  casKpi.innerHTML=[['3:15 reference',d.ref!=null?fmt(d.ref,2):'—'],['fixed ATM',d.atm!=null?fmt(d.atm,0):'—'],['expiry',exp],['index now',st.index!=null?fmt(st.index,2):'—'],['synthetic now',st.synth!=null?fmt(st.synth,2):'—'],['basis (index − synth)',st.basis!=null?((st.basis>=0?'+':'')+fmt(st.basis,2)):'—'],['index range',st.index_lo!=null?fmt(st.index_lo,0)+' – '+fmt(st.index_hi,0):'—'],['iep ticks',st.iep_ticks!=null?st.iep_ticks:'—']]
    .map(function(x){ return '<div><small>'+x[0]+'</small><b'+(x[0].indexOf('basis')===0&&st.basis!=null?' class="'+(st.basis>=0?'up':'down')+'"':'')+'>'+x[1]+'</b></div>'; }).join('');
  casStateEl.textContent=d.live?'LIVE · recording':(d.n?d.n+' samples · '+esc(d.date):'idle · '+esc(d.date)); casStateEl.className=d.live?'live':'off';
  var opts=(d.dates||[]); if(opts.indexOf(d.date)<0) opts=[d.date].concat(opts);
  casDate.innerHTML=opts.map(function(x){ return '<option value="'+x+'"'+(x===d.date?' selected':'')+'>'+x+'</option>'; }).join('');
  drawCas(d);
}
function pollCas(){
  if(window.FINO_LOCKED||casPanel.hidden) return;
  fetch('/api/cas?u='+encodeURIComponent(casState.u)+(casState.date?'&date='+casState.date:''),{credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){ if(d&&!d.error) renderCas(d); }).catch(function(){});
}
document.getElementById('cas-u').addEventListener('click',function(e){ var b=e.target.closest('button[data-u]'); if(!b) return; casState.u=b.getAttribute('data-u'); Array.prototype.forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); pollCas(); });
casDate.addEventListener('change',function(){ casState.date=casDate.value; pollCas(); });
casSvg.addEventListener('mousemove',function(e){ var m=casSvg._map; if(!m) return; var r=casSvg.getBoundingClientRect(), x=(e.clientX-r.left)/r.width*m.W; var t=m.t0+(x-m.L)/(m.W-m.L-m.R)*(m.t1-m.t0); var best=null; m.pts.forEach(function(p){ if(!best||Math.abs(p[0]-t)<Math.abs(best[0]-t)) best=p; }); if(!best) return;
  casTip.style.display='block'; casTip.style.left=Math.min(e.clientX-r.left+12, r.width-180)+'px'; casTip.style.top=(e.clientY-r.top-30)+'px'; casTip.innerHTML=hhmm(best[0])+' · <span style="color:#7fe0f0">'+(best[1]!=null?fmt(best[1],2):'—')+'</span> · <span style="color:#f5c842">'+(best[2]!=null?fmt(best[2],2):'—')+'</span>'+(best[1]!=null&&best[2]!=null?' · Δ '+fmt(best[1]-best[2],1):''); });
casSvg.addEventListener('mouseleave',function(){ casTip.style.display='none'; });
setTimeout(pollCas,700); setInterval(function(){ var d=casState.data; if(d&&d.live) pollCas(); },2000); setInterval(function(){ var d=casState.data; if(!d||!d.live) pollCas(); },30000);
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
  h+='<div class="br-row" style="margin-top:auto"><span class="br-msg">'+(d.can_trade?'token ends 03:30 IST · every order is confirmed on a ticket first':'read-only for now: order routing opens once Finostat is empanelled with Upstox')+'</span><button type="button" class="br-btn" data-act="disconnect" style="margin-left:auto">Disconnect</button></div>';
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
window.finoCanTrade=function(){ return !!(brState.data&&brState.data.can_trade); };
window.finoBrokerPoll=pollBroker;
/* ---------- chart: our own candles from Upstox (TradingView's embed refuses NSE symbols) ---------- */
var chart={sym:null,pending:'NIFTY 50',ready:true,loading:false,tf:'5m',data:[],n:120,end:0,hover:null,drag:null,timer:null,at:0,vp:true};
try{ chart.vp=localStorage.getItem('fino_chart_vp')!=='off'; }catch(e){}
var chSym=document.getElementById('ch-sym'), chNote=document.getElementById('ch-note'), chPanel=document.getElementById('p-chart'), chState=document.getElementById('ch-state'), chOhlc=document.getElementById('ch-ohlc'), chCv=document.getElementById('ch-cv');
function chFmt(v,d){ if(v==null||isNaN(v)) return '—'; d=d==null?(v>=1000?1:2):d; return Number(v).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d}); }
function chVol(v){ if(!v) return '—'; return v>=1e7?(v/1e7).toFixed(2)+'cr':v>=1e5?(v/1e5).toFixed(1)+'L':v>=1000?(v/1000).toFixed(1)+'k':String(v); }
function chColor(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#fff'; }
function chMarketOpen(){ var d=new Date(Date.now()+(330+new Date().getTimezoneOffset())*60000); var m=d.getHours()*60+d.getMinutes(); return d.getDay()>0&&d.getDay()<6&&m>=9*60&&m<=15*60+45; }
function fetchCandles(){
  if(!chart.sym||window.FINO_LOCKED) return;
  var sym=chart.sym, tf=chart.tf, atEnd=(chart.end>=chart.data.length-1);
  fetch('/api/candles?u='+encodeURIComponent(sym)+'&tf='+tf,{credentials:'same-origin'}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){
    if(sym!==chart.sym||tf!==chart.tf) return;
    if(x.s>=400){ chNote.textContent=(x.j&&x.j.error)||('chart unavailable ('+x.s+')'); chState.textContent='—'; chState.className='live off'; return; }
    var same=chart.data.length===x.j.candles.length; chart.data=x.j.candles; chart.at=Date.now();
    if(!same||atEnd){ chart.end=chart.data.length-1; }
    if(chart.n>chart.data.length) chart.n=chart.data.length;
    var open=chMarketOpen(); chState.textContent=open?'LIVE':'CLOSED'; chState.className='live'+(open?'':' off');
    var last=chart.data[chart.data.length-1], prev=chart.data.length>1?chart.data[chart.data.length-2]:last;
    var base=tf==='D'?(prev?prev[4]:last[1]):chart.data.filter(function(c){ return c[0].slice(0,10)<last[0].slice(0,10); }).slice(-1)[0];
    var ref=base?(Array.isArray(base)?base[4]:base):last[1]; var chg=last[4]-ref;
    chNote.innerHTML='<b style="color:var(--gold)">'+chFmt(last[4])+'</b> <span class="'+(chg>=0?'up':'down')+'">'+(chg>=0?'+':'')+chFmt(chg)+' ('+(chg/ref*100).toFixed(2)+'%)</span> · '+tf+' · '+chart.data.length+' bars';
    renderChart();
  }).catch(function(){ chNote.textContent='chart: network'; });
}
function renderChart(){
  var cv=chCv; if(!cv||chPanel.hidden) return; var d=chart.data; var r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1; var W=Math.max(200,Math.floor(r.width)), H=Math.max(160,Math.floor(r.height));
  if(cv.width!==Math.floor(W*dpr)||cv.height!==Math.floor(H*dpr)){ cv.width=Math.floor(W*dpr); cv.height=Math.floor(H*dpr); }
  var c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,W,H); c.font='10px IBM Plex Mono, monospace';
  var C={up:chColor('--up'),down:chColor('--down'),gold:chColor('--gold'),cyan:chColor('--cyan'),faint:chColor('--faint'),muted:chColor('--muted'),text:chColor('--text')};
  if(!d.length){ c.fillStyle=C.faint; c.fillText('loading candles…',12,24); return; }
  var axR=64, axB=20, volH=Math.floor(H*.16); var pw=W-axR, ph=H-axB-volH-6;
  var n=Math.max(10,Math.min(chart.n,d.length)); var end=Math.max(n-1,Math.min(chart.end,d.length-1)); var start=end-n+1; var vis=d.slice(start,end+1);
  var hi=-Infinity, lo=Infinity, vmax=0; vis.forEach(function(k){ if(k[2]>hi) hi=k[2]; if(k[3]<lo) lo=k[3]; if(k[5]>vmax) vmax=k[5]; }); var pad=(hi-lo)*.08||1; hi+=pad; lo-=pad;
  var bw=pw/n; var X=function(i){ return (i-start)*bw+bw/2; }, Y=function(p){ return 8+(hi-p)/(hi-lo)*(ph-8); };
  c.strokeStyle='rgba(190,150,255,.10)'; c.fillStyle=C.faint; c.textAlign='left';
  for(var g=0;g<=5;g++){ var p=lo+(hi-lo)*g/5, y=Y(p); c.beginPath(); c.moveTo(0,y); c.lineTo(pw,y); c.stroke(); c.fillText(chFmt(p),pw+6,y+3); }
  var lastDay=null; c.textAlign='center'; var every=Math.max(1,Math.round(n/8));
  vis.forEach(function(k,i){ var day=k[0].slice(0,10); var idx=start+i; if(chart.tf!=='D'&&lastDay&&day!==lastDay){ c.strokeStyle='rgba(190,150,255,.18)'; c.setLineDash([2,3]); c.beginPath(); c.moveTo(X(idx)-bw/2,0); c.lineTo(X(idx)-bw/2,H-axB); c.stroke(); c.setLineDash([]); }
    if(i%every===0){ c.fillStyle=C.faint; c.fillText(chart.tf==='D'?day.slice(5):(day!==lastDay&&lastDay?day.slice(5)+' '+k[0].slice(11,16):k[0].slice(11,16)),X(idx),H-6); } lastDay=day; });
  vis.forEach(function(k,i){ var idx=start+i, x=X(idx), up=k[4]>=k[1]; var col=up?C.up:C.down; var vh=vmax?k[5]/vmax*volH:0; c.fillStyle=up?'rgba(72,232,150,.28)':'rgba(255,92,120,.28)'; c.fillRect(x-bw*.35,H-axB-vh,Math.max(1,bw*.7),vh);
    c.strokeStyle=col; c.fillStyle=col; c.lineWidth=1; c.beginPath(); c.moveTo(x,Y(k[2])); c.lineTo(x,Y(k[3])); c.stroke(); var yo=Y(k[1]), yc=Y(k[4]); var top=Math.min(yo,yc), h=Math.max(1,Math.abs(yo-yc)); var w=Math.max(1,bw*.62); if(bw>=3) c.fillRect(x-w/2,top,w,h); else c.fillRect(x-.5,top,1,h); });
  /* volume profile of the visible range: volume spread across each bar's low–high, 48 price bins,
     point of control (POC) and the 70% value area (VAH/VAL) */
  var vpInfo=null;
  if(chart.vp&&vmax>0){ var bins=48, bh=(hi-lo)/bins, prof=new Array(bins).fill(0), profUp=new Array(bins).fill(0), tot=0;
    vis.forEach(function(k){ var l=k[3], h=k[2], v=k[5]||0; if(!v) return; var b0=Math.max(0,Math.floor((l-lo)/bh)), b1=Math.min(bins-1,Math.floor((h-lo)/bh)); var per=v/(b1-b0+1); for(var b=b0;b<=b1;b++){ prof[b]+=per; if(k[4]>=k[1]) profUp[b]+=per; } tot+=v; });
    var pmax=Math.max.apply(null,prof)||1, poc=prof.indexOf(pmax); var inVA=new Array(bins).fill(false); inVA[poc]=true; var acc=prof[poc], up_=poc+1, dn_=poc-1;
    while(acc<tot*.7&&(up_<bins||dn_>=0)){ var a=up_<bins?prof[up_]:-1, b=dn_>=0?prof[dn_]:-1; if(a>=b){ inVA[up_]=true; acc+=a; up_++; } else { inVA[dn_]=true; acc+=b; dn_--; } }
    var maxW=pw*.22; for(var bi=0;bi<bins;bi++){ if(!prof[bi]) continue; var yTop=Y(lo+(bi+1)*bh), yBot=Y(lo+bi*bh), w=prof[bi]/pmax*maxW; var upW=prof[bi]?w*profUp[bi]/prof[bi]:0;
      c.fillStyle=bi===poc?'rgba(245,200,66,.55)':(inVA[bi]?'rgba(70,225,255,.30)':'rgba(70,225,255,.13)'); c.fillRect(pw-w,yTop+.5,w,Math.max(1,yBot-yTop-1));
      if(bi!==poc){ c.fillStyle=inVA[bi]?'rgba(72,232,150,.22)':'rgba(72,232,150,.10)'; c.fillRect(pw-upW,yTop+.5,upW,Math.max(1,yBot-yTop-1)); } }
    var vah=lo+(up_)*bh, val=lo+(dn_+1)*bh, pocP=lo+(poc+.5)*bh; var yp=Y(pocP); c.strokeStyle='rgba(245,200,66,.7)'; c.setLineDash([4,3]); c.beginPath(); c.moveTo(0,yp); c.lineTo(pw,yp); c.stroke(); c.setLineDash([]);
    c.fillStyle=C.gold; c.textAlign='left'; c.fillText('POC '+chFmt(pocP),6,yp-4); c.fillStyle='rgba(70,225,255,.9)'; c.fillText('VAH '+chFmt(vah),6,Y(vah)-4); c.fillText('VAL '+chFmt(val),6,Y(val)+12);
    vpInfo={poc:pocP,vah:vah,val:val}; }
  chart._vp=vpInfo;
  var last=d[d.length-1]; if(end===d.length-1){ var yl=Y(last[4]); c.strokeStyle=C.gold; c.setLineDash([3,3]); c.beginPath(); c.moveTo(0,yl); c.lineTo(pw,yl); c.stroke(); c.setLineDash([]); c.fillStyle=C.gold; c.fillRect(pw+2,yl-8,axR-4,16); c.fillStyle='#2a1a02'; c.textAlign='left'; c.fillText(chFmt(last[4]),pw+6,yl+3); }
  if(chart.hover!=null){ var hi_=Math.max(start,Math.min(end,chart.hover.i)); var k2=d[hi_]; var hx=X(hi_); c.strokeStyle='rgba(255,255,255,.35)'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(hx,0); c.lineTo(hx,H-axB); c.stroke(); if(chart.hover.y!=null&&chart.hover.y<ph){ c.beginPath(); c.moveTo(0,chart.hover.y); c.lineTo(pw,chart.hover.y); c.stroke(); var pv=hi-(chart.hover.y-8)/(ph-8)*(hi-lo); c.setLineDash([]); c.fillStyle='rgba(255,255,255,.12)'; c.fillRect(pw+2,chart.hover.y-8,axR-4,16); c.fillStyle=C.text; c.textAlign='left'; c.fillText(chFmt(pv),pw+6,chart.hover.y+3); } c.setLineDash([]);
    c.fillStyle='rgba(255,255,255,.12)'; c.textAlign='center'; c.fillRect(hx-38,H-axB+2,76,16); c.fillStyle=C.text; c.fillText(k2[0].slice(5,16).replace('T',' '),hx,H-axB+14);
    var ch2=k2[4]-k2[1]; chOhlc.innerHTML='<b>O</b> '+chFmt(k2[1])+' <b>H</b> '+chFmt(k2[2])+' <b>L</b> '+chFmt(k2[3])+' <b>C</b> '+chFmt(k2[4])+' <span class="'+(ch2>=0?'up':'down')+'">'+(ch2>=0?'+':'')+chFmt(ch2)+'</span> <b>V</b> '+chVol(k2[5]); }
  else { var k3=d[end]; var ch3=k3[4]-k3[1]; chOhlc.innerHTML='<b>O</b> '+chFmt(k3[1])+' <b>H</b> '+chFmt(k3[2])+' <b>L</b> '+chFmt(k3[3])+' <b>C</b> '+chFmt(k3[4])+' <span class="'+(ch3>=0?'up':'down')+'">'+(ch3>=0?'+':'')+chFmt(ch3)+'</span> <b>V</b> '+chVol(k3[5]); }
  chart._geo={start:start,end:end,bw:bw,pw:pw,ph:ph};
}
function drawChart(){ if(chart.pending){ chart.sym=chart.pending; chart.pending=null; chart.data=[]; chart.end=0; chSym.textContent=chart.sym; chNote.textContent='loading '+chart.sym+'…'; chOhlc.textContent='—'; renderChart(); fetchCandles(); } else renderChart(); }
function loadTV(){ drawChart(); }
function chartTo(key){ if(!key) return; if(chart.sym===key&&!chart.pending) return; chart.pending=key; if(chPanel.hidden) return; drawChart(); }
window.finoChartTo=chartTo;            /* the builder lives in its own scope below */
if(chCv){
  document.getElementById('ch-tf').addEventListener('click',function(e){ var b=e.target.closest('button[data-tf]'); if(!b) return; Array.prototype.forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); chart.tf=b.getAttribute('data-tf'); chart.data=[]; chart.n=120; chart.end=0; chNote.textContent='loading…'; renderChart(); fetchCandles(); });
  document.getElementById('ch-vp').addEventListener('click',function(){ chart.vp=!chart.vp; this.classList.toggle('on',chart.vp); try{ localStorage.setItem('fino_chart_vp',chart.vp?'on':'off'); }catch(e){} renderChart(); });
  document.getElementById('ch-vp').classList.toggle('on',chart.vp);
  chCv.addEventListener('wheel',function(e){ if(!chart.data.length) return; e.preventDefault(); var g=chart._geo; if(!g) return; var r=chCv.getBoundingClientRect(); var fx=(e.clientX-r.left)/g.pw; var n0=chart.n; var n1=Math.round(Math.max(15,Math.min(chart.data.length,n0*(e.deltaY>0?1.18:0.85)))); var anchor=g.start+fx*n0; chart.n=n1; chart.end=Math.max(n1-1,Math.min(chart.data.length-1,Math.round(anchor+(1-fx)*n1-1))); renderChart(); },{passive:false});
  chCv.addEventListener('pointerdown',function(e){ chart.drag={x:e.clientX,end:chart.end}; chCv.setPointerCapture(e.pointerId); });
  chCv.addEventListener('pointermove',function(e){ var r=chCv.getBoundingClientRect(); var g=chart._geo; if(!g) return; if(chart.drag){ var dx=e.clientX-chart.drag.x; var shift=Math.round(-dx/g.bw); chart.end=Math.max(Math.min(chart.n,chart.data.length)-1,Math.min(chart.data.length-1,chart.drag.end+shift)); }
    var i=g.start+Math.floor((e.clientX-r.left)/g.bw); chart.hover={i:i,y:e.clientY-r.top}; renderChart(); });
  chCv.addEventListener('pointerup',function(){ chart.drag=null; }); chCv.addEventListener('pointercancel',function(){ chart.drag=null; });
  chCv.addEventListener('pointerleave',function(){ chart.drag=null; chart.hover=null; renderChart(); });
  window.addEventListener('resize',function(){ renderChart(); });
  setInterval(function(){ if(document.hidden||chPanel.hidden||!chart.sym) return; var age=Date.now()-chart.at; if((chMarketOpen()&&age>20000)||age>300000) fetchCandles(); },5000);
}
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
  blChainNote.textContent=(o?'OI from the exchange '+(c.oi_source==='rest'?'(Upstox) · ΔOI vs previous close':'feed · ΔOI since the first tick seen today')+' · click a price to add that leg':'no open interest for this chain yet')+(c.live?'':' · last traded');
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
    if(bl.after){ var f=bl.after; bl.after=null; try{ f(d); }catch(err){} }
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
  if(!(window.finoCanTrade&&window.finoCanTrade())){ alert('Order routing is not open to your account yet — positions and funds are. It switches on once Finostat is empanelled with Upstox.'); return; }
  var d=bl.lastData; document.getElementById('tk-title').textContent=bl.u+' · '+new Date(d.expiry).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+' · lot '+d.lot;
  tkLegs.innerHTML=d.legs.map(function(l,i){ return '<tr><td>'+l.strike+' '+l.right+'</td><td class="'+(l.qty>0?'up':'down')+'">'+(l.qty>0?'BUY':'SELL')+'</td><td>'+Math.abs(l.qty)+'×'+d.lot+'</td><td>'+(l.price!=null?l.price.toFixed(2):'—')+'</td><td><input type="number" step="0.05" min="0.05" data-i="'+i+'" value="'+(l.price!=null?l.price.toFixed(2):'')+'" style="width:76px"></td></tr>'; }).join('');
  document.getElementById('tk-confirm').checked=false; tkMsg.textContent=''; tkRes.innerHTML=''; document.getElementById('tk-send').disabled=false; tk.hidden=false;
}
document.getElementById('bl-trade').addEventListener('click',openTicket);
document.getElementById('bl-paper').addEventListener('click',function(){
  if(!bl.u||!bl.legs.length||!bl.lastData){ alert('Price a strategy first.'); return; }
  var lots=parseInt(prompt('Paper-trade '+bl.u+' · '+bl.legs.length+' leg(s) at current prices. Lots?','1')||'0',10); if(!(lots>0)) return;
  var note=prompt('Note for the journal (optional)','')||'';
  srvPost('/api/book/open',{u:bl.u,expiry:bl.lastData.expiry,lots:lots,note:note,legs:bl.lastData.legs.map(function(l){ return {right:l.right,strike:l.strike,qty:l.qty,price:l.price}; })}).then(function(r){
    if(r.error){ alert(r.error); return; } blStatus.textContent='paper position #'+r.id+' saved'; if(window.finoBookPoll) window.finoBookPoll(); var p=document.getElementById('p-book'); if(p) p.scrollIntoView({behavior:'smooth',block:'nearest'});
  });
});
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
<script>(function(){
  var U=['NIFTY 50','BANKNIFTY','FINNIFTY','SENSEX'];
  function $(id){ return document.getElementById(id); }
  function css(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#fff'; }
  var C={gold:css('--gold'),cyan:css('--cyan'),up:css('--up'),down:css('--down'),faint:css('--faint'),muted:css('--muted'),text:css('--text'),line:css('--line-strong'),mag:'#ff5fd2'};
  function nf(x,d){ if(x==null||isNaN(x)) return '—'; d=d==null?1:d; return Number(x).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d}); }
  function inr(x){ if(x==null) return '—'; var a=Math.abs(x); var s=a>=1e7?(a/1e7).toFixed(2)+' cr':a>=1e5?(a/1e5).toFixed(2)+' L':nf(a,0); return (x<0?'−':'')+'₹'+s; }
  function ctx2d(cv){ var r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1; var w=Math.max(200,Math.floor(r.width)), h=Math.max(120,Math.floor(r.height)); if(cv.width!==Math.floor(w*dpr)||cv.height!==Math.floor(h*dpr)){ cv.width=Math.floor(w*dpr); cv.height=Math.floor(h*dpr); } var c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,w,h); c.font='10px IBM Plex Mono, monospace'; return {c:c,w:w,h:h}; }
  function kpi(el,items){ el.innerHTML=items.map(function(k){ return '<div><small>'+k[0]+'</small><b'+(k[2]?' class="'+k[2]+'"':'')+'>'+k[1]+'</b></div>'; }).join(''); }
  function state(id,txt,cls){ var e=$(id); if(!e) return; e.textContent=txt; e.className='an-state'+(cls?' '+cls:''); }
  function getJSON(url,ok,fail){ fetch(url,{credentials:'same-origin'}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ if(x.s>=400){ fail(x.j&&x.j.error?x.j.error:(x.s===402?'Desk plan required':'HTTP '+x.s)); } else ok(x.j); }).catch(function(){ fail('network'); }); }
  function segInit(panel,cls,attr,cur,onChange){ var seg=panel.querySelector(cls); if(!seg) return; seg.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; Array.prototype.forEach.call(seg.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); onChange(b.getAttribute(attr)); }); }
  function fillExp(sel,exps,cur){ if(!sel) return; var have=Array.prototype.map.call(sel.options,function(o){ return o.value; }); if(have.join()===exps.join()){ sel.value=cur; return; } sel.innerHTML=exps.map(function(e){ var d=new Date(e+'T15:30:00+05:30'); return '<option value="'+e+'">'+d.toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+'</option>'; }).join(''); sel.value=cur; }
  function axes(c,w,h,pad){ c.strokeStyle='rgba(190,150,255,.14)'; c.lineWidth=1; c.beginPath(); c.moveTo(pad.l,pad.t); c.lineTo(pad.l,h-pad.b); c.lineTo(w-pad.r,h-pad.b); c.stroke(); }
  function visible(id){ var el=$(id); return el&&!el.hidden&&!document.hidden; }
  function heat(t){ /* 0..1 -> cyan..violet..magenta */ t=Math.max(0,Math.min(1,t)); var a=[70,225,255], b=[120,60,255], d=[255,95,210]; var x=t<.5?[a,b,t*2]:[b,d,(t-.5)*2]; var r=Math.round(x[0][0]+(x[1][0]-x[0][0])*x[2]), g=Math.round(x[0][1]+(x[1][1]-x[0][1])*x[2]), bl=Math.round(x[0][2]+(x[1][2]-x[0][2])*x[2]); return 'rgb('+r+','+g+','+bl+')'; }
  function diverge(t){ /* -1..1 -> cyan..dark..magenta */ t=Math.max(-1,Math.min(1,t)); var k=Math.abs(t); var base=[24,14,60]; var to=t<0?[70,225,255]:[255,95,210]; return 'rgb('+Math.round(base[0]+(to[0]-base[0])*k)+','+Math.round(base[1]+(to[1]-base[1])*k)+','+Math.round(base[2]+(to[2]-base[2])*k)+')'; }

  /* ---------------- SURF ---------------- */
  var surf={u:'NIFTY 50',mode:'iv',data:null,hover:null};
  var surfPanel=$('p-surf');
  if(surfPanel){
    segInit(surfPanel,'.an-u','data-u',surf.u,function(u){ surf.u=u; loadSurf(); });
    segInit(surfPanel,'#surf-mode','data-m',surf.mode,function(m){ surf.mode=m; drawSurf(); });
    var scv=$('surf-cv');
    scv.addEventListener('mousemove',function(e){ if(!surf.data||!surf.geo) return; var r=scv.getBoundingClientRect(); var x=e.clientX-r.left,y=e.clientY-r.top; var g=surf.geo; var ci=Math.floor((x-g.x0)/g.cw), ri=Math.floor((y-g.y0)/g.rh); if(ci<0||ri<0||ci>=g.nc||ri>=g.nr){ surf.hover=null; } else surf.hover=[ri,ci]; drawSurf(); });
    scv.addEventListener('mouseleave',function(){ surf.hover=null; drawSurf(); });
  }
  function loadSurf(){ if(!surfPanel) return; state('surf-state','loading…'); getJSON('/api/surface?u='+encodeURIComponent(surf.u),function(d){ surf.data=d; state('surf-state',(d.live?'LIVE':'LAST')+' · '+(d.source==='upstox-rest'?'EXCHANGE IV':'MODEL IV'),'ok'); var front=d.rows[0]||{}; kpi($('surf-kpi'),[['spot',nf(d.spot,1),'c']].concat(d.term.map(function(t){ return [t.label+' · '+Math.round(t.t_days)+'d',t.atm_iv!=null?nf(t.atm_iv,1)+'%':'—']; })).concat([['25Δ RR (front)',front.rr25!=null?(front.rr25>0?'+':'')+nf(front.rr25,2):'—',front.rr25>0?'down':'up'],['25Δ BF (front)',front.bf25!=null?nf(front.bf25,2):'—','m']])); drawSurf(); },function(err){ state('surf-state',err,'err'); }); }
  function drawSurf(){ var d=surf.data; if(!d||!scv) return; var g=ctx2d(scv), c=g.c; var padL=64, padT=22, padB=6, padR=8; var nc=d.cols.length, nr=d.rows.length; if(!nr){ c.fillStyle=C.faint; c.fillText('no expiries with a fitted smile yet',padL,padT+20); return; }
    var cw=(g.w-padL-padR)/nc, rh=(g.h-padT-padB)/nr; surf.geo={x0:padL,y0:padT,cw:cw,rh:rh,nc:nc,nr:nr};
    var lo=d.iv_range?d.iv_range[0]:0, hi=d.iv_range?d.iv_range[1]:1, rm=d.rich_max||1;
    c.textAlign='center'; c.fillStyle=C.faint; d.cols.forEach(function(m,i){ c.fillText((m>0?'+':'')+m+'%',padL+cw*(i+.5),14); });
    d.rows.forEach(function(row,ri){ row.cells.forEach(function(cell,ci){ var x=padL+cw*ci, y=padT+rh*ri; var v=surf.mode==='iv'?cell.iv:cell.rich; c.fillStyle= v==null?'rgba(255,255,255,.03)':(surf.mode==='iv'?heat(hi>lo?(v-lo)/(hi-lo):.5):diverge(rm?v/rm:0)); c.fillRect(x+1,y+1,cw-2,rh-2); if(surf.hover&&surf.hover[0]===ri&&surf.hover[1]===ci){ c.strokeStyle=C.gold; c.lineWidth=2; c.strokeRect(x+1.5,y+1.5,cw-3,rh-3); } if(v!=null&&cw>34){ c.fillStyle= surf.mode==='iv'?'rgba(0,0,0,.75)':'#fff'; c.font=(rh>26?'11px':'10px')+' IBM Plex Mono, monospace'; c.fillText(surf.mode==='iv'?v.toFixed(1):((v>0?'+':'')+v.toFixed(1)),x+cw/2,y+rh/2+4); } });
      c.textAlign='right'; c.fillStyle=C.text; c.font='10.5px IBM Plex Mono, monospace'; c.fillText(row.label,padL-8,padT+rh*ri+rh/2+1); c.fillStyle=C.faint; c.font='9px IBM Plex Mono, monospace'; c.fillText(Math.round(row.t_days)+'d',padL-8,padT+rh*ri+rh/2+12); c.textAlign='center'; });
    var note=$('surf-note'); if(surf.hover){ var row=d.rows[surf.hover[0]], cell=row.cells[surf.hover[1]], m=d.cols[surf.hover[1]]; note.textContent=row.label+' · '+(m>0?'+':'')+m+'% moneyness ≈ '+nf(d.spot*Math.exp(m/100),0)+' · IV '+(cell.iv!=null?cell.iv.toFixed(2)+'%':'—')+' · '+(cell.rich!=null?(cell.rich>0?'rich +':'cheap ')+cell.rich.toFixed(2)+' vol':'no fit'); } else note.textContent=surf.mode==='iv'?'IV range '+nf(lo,1)+'–'+nf(hi,1)+'% · hover a cell':'scale ±'+nf(rm,1)+' vol · hover a cell'; }

  /* ---------------- SKEW ---------------- */
  var skew={u:'NIFTY 50',exp:'',x:'strike',data:null};
  var skewPanel=$('p-skew');
  if(skewPanel){ segInit(skewPanel,'.an-u','data-u',skew.u,function(u){ skew.u=u; skew.exp=''; loadSkew(); }); segInit(skewPanel,'#skew-x','data-x',skew.x,function(x){ skew.x=x; drawSkew(); }); skewPanel.querySelector('.an-exp').addEventListener('change',function(e){ skew.exp=e.target.value; loadSkew(); }); }
  function loadSkew(){ if(!skewPanel) return; state('skew-state','loading…'); getJSON('/api/skew?u='+encodeURIComponent(skew.u)+(skew.exp?'&expiry='+skew.exp:''),function(d){ skew.data=d; skew.exp=d.expiry; fillExp(skewPanel.querySelector('.an-exp'),d.expiries,d.expiry); state('skew-state',(d.live?'LIVE':'LAST')+' · '+Math.round(d.t_days)+'d','ok');
      kpi($('skew-kpi'),[['spot',nf(d.spot,1),'c'],['ATM IV',d.atm_iv!=null?nf(d.atm_iv,2)+'%':'—'],['25Δ risk reversal',d.rr25!=null?(d.rr25>0?'+':'')+nf(d.rr25,2):'—',d.rr25>0?'down':'up'],['25Δ butterfly',d.bf25!=null?nf(d.bf25,2):'—','m'],['skew slope',d.skew_slope!=null?nf(d.skew_slope,3)+' /1%':'—','m']]); drawSkew(); },function(err){ state('skew-state',err,'err'); }); }
  function drawSkew(){ var d=skew.data, cv=$('skew-cv'); if(!d||!cv) return; var g=ctx2d(cv), c=g.c, pad={l:44,r:10,t:10,b:22}; var pts=d.points.filter(function(p){ return p.iv!=null; }); if(pts.length<3){ c.fillStyle=C.faint; c.fillText('not enough implied vols',pad.l,30); return; }
    function X(p){ return skew.x==='strike'?p.strike:skew.x==='m'?p.m:(p.ce_delta!=null?p.ce_delta:(p.pe_delta!=null?1+p.pe_delta:null)); }
    var xs=pts.map(X).filter(function(v){ return v!=null; }); var xmin=Math.min.apply(null,xs), xmax=Math.max.apply(null,xs); if(skew.x==='delta'){ xmin=0; xmax=1; }
    var ys=[]; pts.forEach(function(p){ [p.ce_iv,p.pe_iv,p.fit].forEach(function(v){ if(v!=null) ys.push(v); }); }); var ymin=Math.min.apply(null,ys), ymax=Math.max.apply(null,ys); var m=(ymax-ymin)*.12||1; ymin-=m; ymax+=m;
    var sx=function(v){ return pad.l+(v-xmin)/((xmax-xmin)||1)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-(v-ymin)/((ymax-ymin)||1)*(g.h-pad.t-pad.b); };
    axes(c,g.w,g.h,pad); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=ymin+(ymax-ymin)*i/4; c.fillText(v.toFixed(1),pad.l-4,sy(v)+3); c.strokeStyle='rgba(190,150,255,.08)'; c.beginPath(); c.moveTo(pad.l,sy(v)); c.lineTo(g.w-pad.r,sy(v)); c.stroke(); }
    c.textAlign='center'; for(var j=0;j<=6;j++){ var xv=xmin+(xmax-xmin)*j/6; c.fillText(skew.x==='strike'?nf(xv,0):skew.x==='m'?(xv>0?'+':'')+xv.toFixed(1)+'%':xv.toFixed(2)+'Δ',sx(xv),g.h-8); }
    var atmX=skew.x==='strike'?d.spot:skew.x==='m'?0:0.5; c.strokeStyle='rgba(70,225,255,.5)'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(sx(atmX),pad.t); c.lineTo(sx(atmX),g.h-pad.b); c.stroke(); c.setLineDash([]);
    function line(key,color,dash){ var ok=false; c.strokeStyle=color; c.lineWidth=key==='fit'?1.4:1.8; if(dash) c.setLineDash([5,4]); c.beginPath(); pts.forEach(function(p){ var xv=X(p), yv=p[key]; if(xv==null||yv==null) return; if(!ok){ c.moveTo(sx(xv),sy(yv)); ok=true; } else c.lineTo(sx(xv),sy(yv)); }); c.stroke(); c.setLineDash([]); if(key!=='fit'){ c.fillStyle=color; pts.forEach(function(p){ var xv=X(p), yv=p[key]; if(xv==null||yv==null) return; c.beginPath(); c.arc(sx(xv),sy(yv),2.2,0,Math.PI*2); c.fill(); }); } }
    line('fit',C.gold,true); line('ce_iv',C.cyan,false); line('pe_iv',C.mag,false);
    c.font='9.5px IBM Plex Mono, monospace'; c.textAlign='left'; c.fillStyle=C.cyan; c.fillText('CE IV',pad.l+6,pad.t+10); c.fillStyle=C.mag; c.fillText('PE IV',pad.l+46,pad.t+10); c.fillStyle=C.gold; c.fillText('FIT',pad.l+86,pad.t+10); }

  /* ---------------- CURV ---------------- */
  var curv={u:'NIFTY 50',exp:'',data:null};
  var curvPanel=$('p-curv');
  if(curvPanel){ segInit(curvPanel,'.an-u','data-u',curv.u,function(u){ curv.u=u; curv.exp=''; loadCurv(); }); curvPanel.querySelector('.an-exp').addEventListener('change',function(e){ curv.exp=e.target.value; loadCurv(); }); }
  function loadCurv(){ if(!curvPanel) return; state('curv-state','loading…'); getJSON('/api/curve?u='+encodeURIComponent(curv.u)+(curv.exp?'&expiry='+curv.exp:''),function(d){ curv.data=d; curv.exp=d.expiry; fillExp(curvPanel.querySelector('.an-exp'),d.expiries,d.expiry); state('curv-state',(d.live?'LIVE':'LAST')+' · '+nf(d.t_days,1)+'d','ok');
      kpi($('curv-kpi'),[['spot',nf(d.spot,1),'c'],['expected move (1σ)','±'+nf(d.expected_move,0)+' · '+nf(d.expected_move_pct,2)+'%'],['16–84% range',nf(d.p16,0)+' – '+nf(d.p84,0),'m'],['5–95% range',nf(d.p05,0)+' – '+nf(d.p95,0),'m'],['P(close above spot)',nf(d.p_up*100,1)+'%',d.p_up>=.5?'up':'down'],['mode / mean',nf(d.mode,0)+' / '+nf(d.mean,0),'m'],['tails beyond 1σ',nf(d.tail_left*100,1)+'% ↓ · '+nf(d.tail_right*100,1)+'% ↑','m']]); drawCurv(); },function(err){ state('curv-state',err,'err'); }); }
  function drawCurv(){ var d=curv.data, cv=$('curv-cv'); if(!d||!cv||!d.x) return; var g=ctx2d(cv), c=g.c, pad={l:10,r:10,t:12,b:22}; var xmin=d.x[0], xmax=d.x[d.x.length-1]; var ymax=Math.max(Math.max.apply(null,d.pdf),Math.max.apply(null,d.lognormal))*1.08||1;
    var sx=function(v){ return pad.l+(v-xmin)/(xmax-xmin)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-v/ymax*(g.h-pad.t-pad.b); };
    c.fillStyle='rgba(245,200,66,.10)'; c.beginPath(); c.moveTo(sx(d.p16),g.h-pad.b); d.x.forEach(function(x,i){ if(x>=d.p16&&x<=d.p84) c.lineTo(sx(x),sy(d.pdf[i])); }); c.lineTo(sx(d.p84),g.h-pad.b); c.closePath(); c.fill();
    c.strokeStyle='rgba(200,180,255,.45)'; c.setLineDash([4,4]); c.lineWidth=1.2; c.beginPath(); d.x.forEach(function(x,i){ i?c.lineTo(sx(x),sy(d.lognormal[i])):c.moveTo(sx(x),sy(d.lognormal[i])); }); c.stroke(); c.setLineDash([]);
    var grad=c.createLinearGradient(0,pad.t,0,g.h-pad.b); grad.addColorStop(0,'rgba(245,200,66,.35)'); grad.addColorStop(1,'rgba(245,200,66,.02)'); c.fillStyle=grad; c.beginPath(); c.moveTo(sx(xmin),g.h-pad.b); d.x.forEach(function(x,i){ c.lineTo(sx(x),sy(d.pdf[i])); }); c.lineTo(sx(xmax),g.h-pad.b); c.closePath(); c.fill();
    c.strokeStyle=C.gold; c.lineWidth=2; c.beginPath(); d.x.forEach(function(x,i){ i?c.lineTo(sx(x),sy(d.pdf[i])):c.moveTo(sx(x),sy(d.pdf[i])); }); c.stroke();
    function vline(x,color,label,dash){ c.strokeStyle=color; c.lineWidth=1; if(dash) c.setLineDash([3,3]); c.beginPath(); c.moveTo(sx(x),pad.t); c.lineTo(sx(x),g.h-pad.b); c.stroke(); c.setLineDash([]); c.fillStyle=color; c.textAlign='center'; c.fillText(label,sx(x),pad.t-2); }
    vline(d.spot,C.cyan,'spot '+nf(d.spot,0),false); vline(d.p16,C.faint,nf(d.p16,0),true); vline(d.p84,C.faint,nf(d.p84,0),true);
    c.fillStyle=C.faint; c.textAlign='center'; for(var i=0;i<=6;i++){ var v=xmin+(xmax-xmin)*i/6; c.fillText(nf(v,0),sx(v),g.h-8); } c.textAlign='left'; c.fillStyle=C.gold; c.fillText('implied',pad.l+6,pad.t+10); c.fillStyle='rgba(200,180,255,.7)'; c.fillText('lognormal (no skew)',pad.l+58,pad.t+10); }

  /* ---------------- GEX ---------------- */
  var gex={u:'NIFTY 50',exp:'',data:null};
  var gexPanel=$('p-gex');
  if(gexPanel){ segInit(gexPanel,'.an-u','data-u',gex.u,function(u){ gex.u=u; gex.exp=''; loadGex(); }); gexPanel.querySelector('.an-exp').addEventListener('change',function(e){ gex.exp=e.target.value; loadGex(); }); }
  function loadGex(){ if(!gexPanel) return; state('gex-state','loading…'); getJSON('/api/gex?u='+encodeURIComponent(gex.u)+(gex.exp?'&expiry='+gex.exp:''),function(d){ gex.data=d; gex.exp=d.expiry; fillExp(gexPanel.querySelector('.an-exp'),d.expiries,d.expiry); state('gex-state',(d.live?'LIVE':'LAST')+' · LOT '+d.lot,'ok');
      kpi($('gex-kpi'),[['spot',nf(d.spot,1),'c'],['net GEX / 1%','₹'+nf(d.total,1)+' cr',d.total>=0?'up':'down'],['regime',d.total>=0?'PINNING':'CHASING',d.total>=0?'up':'down'],['gamma flip',d.flip!=null?nf(d.flip,0):'—','m'],['largest +',nf(d.max_pos.strike,0)+' · ₹'+nf(d.max_pos.net,1)+' cr','up'],['largest −',nf(d.max_neg.strike,0)+' · ₹'+nf(d.max_neg.net,1)+' cr','down']]); $('gex-state').title=d.regime; drawGex(); },function(err){ state('gex-state',err,'err'); }); }
  function drawGex(){ var d=gex.data, cv=$('gex-cv'); if(!d||!cv||!d.strikes) return; var g=ctx2d(cv), c=g.c, pad={l:46,r:46,t:12,b:22}; var rows=d.strikes; var n=rows.length; var vmax=Math.max.apply(null,rows.map(function(r){ return Math.max(Math.abs(r.call),Math.abs(r.put)); }))||1; var cmax=Math.max.apply(null,rows.map(function(r){ return Math.abs(r.cum); }))||1;
    var bw=(g.w-pad.l-pad.r)/n; var mid=pad.t+(g.h-pad.t-pad.b)/2; var half=(g.h-pad.t-pad.b)/2;
    var sx=function(i){ return pad.l+bw*(i+.5); }, syv=function(v){ return mid-v/vmax*half*.92; }, syc=function(v){ return mid-v/cmax*half*.92; };
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,mid); c.lineTo(g.w-pad.r,mid); c.stroke();
    rows.forEach(function(r,i){ var x=sx(i)-bw*.36; c.fillStyle='rgba(72,232,150,.85)'; var yc=syv(r.call); c.fillRect(x,Math.min(yc,mid),bw*.72,Math.abs(mid-yc)); c.fillStyle='rgba(255,92,120,.85)'; var yp=syv(r.put); c.fillRect(x,Math.min(yp,mid),bw*.72,Math.abs(mid-yp)); });
    c.strokeStyle=C.gold; c.lineWidth=1.8; c.beginPath(); rows.forEach(function(r,i){ i?c.lineTo(sx(i),syc(r.cum)):c.moveTo(sx(i),syc(r.cum)); }); c.stroke();
    var ks=rows.map(function(r){ return r.strike; }); var k0=ks[0], k1=ks[n-1]; function sk(k){ return pad.l+(k-k0)/((k1-k0)||1)*(g.w-pad.l-pad.r-bw)+bw/2; }
    c.strokeStyle=C.cyan; c.setLineDash([3,3]); c.beginPath(); c.moveTo(sk(d.spot),pad.t); c.lineTo(sk(d.spot),g.h-pad.b); c.stroke(); if(d.flip!=null){ c.strokeStyle=C.gold; c.beginPath(); c.moveTo(sk(d.flip),pad.t); c.lineTo(sk(d.flip),g.h-pad.b); c.stroke(); } c.setLineDash([]);
    c.fillStyle=C.faint; c.textAlign='center'; var every=Math.max(1,Math.round(n/8)); rows.forEach(function(r,i){ if(i%every===0) c.fillText(nf(r.strike,0),sx(i),g.h-8); }); c.textAlign='right'; c.fillText('+'+nf(vmax,1),pad.l-4,pad.t+10); c.fillText('−'+nf(vmax,1),pad.l-4,g.h-pad.b-2); c.textAlign='left'; c.fillStyle=C.gold; c.fillText('cum ±'+nf(cmax,1),g.w-pad.r+4,pad.t+10); c.fillStyle=C.cyan; c.fillText('spot',sk(d.spot)+3,pad.t+10); if(d.flip!=null){ c.fillStyle=C.gold; c.fillText('flip',sk(d.flip)+3,pad.t+22); } }

  /* ---------------- RPLY ---------------- */
  var rp={u:'NIFTY 50',day:'',data:null,i:0,timer:null,poll:null};
  var rpPanel=$('p-rply');
  if(rpPanel){ segInit(rpPanel,'.an-u','data-u',rp.u,function(u){ rp.u=u; loadDays(); }); $('rp-load').addEventListener('click',function(){ rp.day=$('rp-date').value; if(rp.day) loadDay(); }); $('rp-t').addEventListener('input',function(e){ rp.i=Number(e.target.value); drawRp(); }); $('rp-play').addEventListener('click',function(){ if(rp.timer){ stopRp(); return; } var ms=Math.round(1000/Number($('rp-speed').value||4)); $('rp-play').textContent='❚❚ PAUSE'; rp.timer=setInterval(function(){ if(!rp.data) return stopRp(); if(rp.i>=rp.data.frames.length-1) return stopRp(); rp.i++; $('rp-t').value=rp.i; drawRp(); },ms); }); }
  function stopRp(){ if(rp.timer){ clearInterval(rp.timer); rp.timer=null; } var b=$('rp-play'); if(b) b.textContent='▶ PLAY'; }
  function loadDays(){ if(!rpPanel) return; state('rp-state','loading days…'); getJSON('/api/replay/days?u='+encodeURIComponent(rp.u),function(d){ var sel=$('rp-date'); sel.innerHTML=d.days.slice(0,120).map(function(x){ return '<option value="'+x+'">'+new Date(x+'T15:30:00+05:30').toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'2-digit'})+'</option>'; }).join(''); state('rp-state',d.days.length+' EXPIRY DAYS','ok'); $('rp-note').textContent='archive: '+d.days[d.days.length-1]+' → '+d.days[0]+' · pick a day and load it'; },function(err){ state('rp-state',err,'err'); }); }
  function loadDay(){ stopRp(); state('rp-state','fetching candles…'); $('rp-load').disabled=true; if(rp.poll) clearTimeout(rp.poll);
    (function tick(){ getJSON('/api/replay/day?u='+encodeURIComponent(rp.u)+'&date='+rp.day,function(j){ if(j.status==='running'){ state('rp-state','fetching '+Math.round(j.progress*100)+'%'); $('rp-note').textContent='first load of a day pulls one candle file per strike; later loads are instant'; rp.poll=setTimeout(tick,1200); return; } if(j.status==='error'){ state('rp-state',j.error||'failed','err'); $('rp-load').disabled=false; return; } rp.data=j.result; rp.i=0; $('rp-load').disabled=false; $('rp-play').disabled=false; var t=$('rp-t'); t.disabled=false; t.max=rp.data.frames.length-1; t.value=0; state('rp-state',rp.u+' · '+rp.day+' · LOT '+rp.data.lot,'ok'); $('rp-note').textContent='drag the scrubber or press play · open '+nf(rp.data.open,1)+' · high '+nf(rp.data.high,1)+' · low '+nf(rp.data.low,1)+' · close '+nf(rp.data.close,1); drawRp(); },function(err){ state('rp-state',err,'err'); $('rp-load').disabled=false; }); })(); }
  function drawRp(){ var d=rp.data, cv=$('rp-cv'); if(!d||!cv) return; var f=d.frames[rp.i]; $('rp-time').textContent=f.t;
    kpi($('rp-kpi'),[['spot @ '+f.t,nf(f.spot,1),'c'],['ATM',nf(f.atm,0),'m'],['ATM straddle',f.straddle!=null?'₹'+nf(f.straddle,1):'—'],['from open',(f.spot-d.open>=0?'+':'')+nf(f.spot-d.open,1)+' · '+nf((f.spot-d.open)/d.open*100,2)+'%',f.spot>=d.open?'up':'down'],['day range',nf(d.low,0)+' – '+nf(d.high,0),'m']]);
    var g=ctx2d(cv), c=g.c, pad={l:50,r:50,t:12,b:22}; var n=d.frames.length; var sp=d.frames.map(function(x){ return x.spot; }); var st=d.frames.map(function(x){ return x.straddle; }).filter(function(v){ return v!=null; }); var smin=Math.min.apply(null,sp), smax=Math.max.apply(null,sp); var tmin=st.length?Math.min.apply(null,st):0, tmax=st.length?Math.max.apply(null,st):1; var m=(smax-smin)*.08||1; smin-=m; smax+=m;
    var sx=function(i){ return pad.l+i/(n-1)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-(v-smin)/((smax-smin)||1)*(g.h-pad.t-pad.b); }, sy2=function(v){ return g.h-pad.b-(v-tmin)/((tmax-tmin)||1)*(g.h-pad.t-pad.b); };
    axes(c,g.w,g.h,pad); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=smin+(smax-smin)*i/4; c.fillText(nf(v,0),pad.l-4,sy(v)+3); } c.textAlign='left'; for(var j=0;j<=4;j++){ var w=tmin+(tmax-tmin)*j/4; c.fillText('₹'+nf(w,0),g.w-pad.r+4,sy2(w)+3); } c.textAlign='center'; [0,Math.floor(n/4),Math.floor(n/2),Math.floor(3*n/4),n-1].forEach(function(i){ c.fillText(d.frames[i].t,sx(i),g.h-8); });
    c.strokeStyle='rgba(70,225,255,.22)'; c.lineWidth=1; c.beginPath(); sp.forEach(function(v,i){ i?c.lineTo(sx(i),sy(v)):c.moveTo(sx(i),sy(v)); }); c.stroke();
    c.strokeStyle='rgba(245,200,66,.22)'; c.beginPath(); var started=false; d.frames.forEach(function(x,i){ if(x.straddle==null) return; started?c.lineTo(sx(i),sy2(x.straddle)):c.moveTo(sx(i),sy2(x.straddle)); started=true; }); c.stroke();
    c.strokeStyle=C.cyan; c.lineWidth=2; c.beginPath(); for(var k=0;k<=rp.i;k++){ k?c.lineTo(sx(k),sy(sp[k])):c.moveTo(sx(k),sy(sp[k])); } c.stroke();
    c.strokeStyle=C.gold; c.lineWidth=1.8; c.beginPath(); started=false; for(var q=0;q<=rp.i;q++){ var x=d.frames[q]; if(x.straddle==null) continue; started?c.lineTo(sx(q),sy2(x.straddle)):c.moveTo(sx(q),sy2(x.straddle)); started=true; } c.stroke();
    c.strokeStyle='rgba(255,255,255,.35)'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(sx(rp.i),pad.t); c.lineTo(sx(rp.i),g.h-pad.b); c.stroke(); c.setLineDash([]); c.fillStyle=C.cyan; c.textAlign='left'; c.fillText('spot',pad.l+6,pad.t+10); c.fillStyle=C.gold; c.fillText('ATM straddle',pad.l+40,pad.t+10);
    $('rp-rows').innerHTML=f.rows.map(function(r){ var sum=(r[1]!=null&&r[2]!=null)?r[1]+r[2]:null; return '<tr'+(r[0]===f.atm?' class="atm"':'')+'><td>'+nf(r[0],0)+'</td><td>'+(r[1]!=null?nf(r[1],2):'—')+'</td><td>'+(r[2]!=null?nf(r[2],2):'—')+'</td><td>'+(sum!=null?nf(sum,2):'—')+'</td></tr>'; }).join(''); }

  /* ---------------- BKTS ---------------- */
  var bt={u:'NIFTY 50',poll:null,data:null};
  var btPanel=$('p-bkts');
  if(btPanel){ segInit(btPanel,'.an-u','data-u',bt.u,function(u){ bt.u=u; }); $('bt-run').addEventListener('click',runBt); }
  function runBt(){ if(bt.poll) clearTimeout(bt.poll); var q='/api/backtest?u='+encodeURIComponent(bt.u)+'&strategy='+$('bt-strat').value+'&entry='+encodeURIComponent($('bt-entry').value.trim())+'&exit='+encodeURIComponent($('bt-exit').value.trim())+'&n='+$('bt-n').value+'&wings='+$('bt-wings').value; $('bt-run').disabled=true; state('bt-state','running…');
    (function tick(){ getJSON(q,function(j){ if(j.status==='running'){ state('bt-state','fetching '+Math.round(j.progress*100)+'%'); $('bt-note').textContent='first run pulls one candle file per leg per expiry; results are kept, so re-runs are instant'; bt.poll=setTimeout(tick,1500); return; } $('bt-run').disabled=false; if(j.status==='error'){ state('bt-state',j.error||'failed','err'); return; } bt.data=j.result; var s=bt.data.stats; state('bt-state',s.n+' EXPIRIES · '+s.first+' → '+s.last,'ok'); $('bt-note').textContent=bt.data.label+' · in '+bt.data.entry+' out '+bt.data.exit+' · lot '+s.lot+' · 1-minute closes, no slippage or costs';
      kpi($('bt-kpi'),[['win rate',nf(s.win_rate,1)+'%',s.win_rate>=50?'up':'down'],['avg P&L / lot',inr(s.avg),s.avg>=0?'up':'down'],['total / lot',inr(s.total),s.total>=0?'up':'down'],['median',inr(s.median),'m'],['best / worst',inr(s.best)+' / '+inr(s.worst),'m'],['profit factor',s.profit_factor!=null?nf(s.profit_factor,2):'∞','m'],['max drawdown',inr(s.max_drawdown),'down'],['avg MAE (pts)',nf(s.avg_mae_pts,1),'m']]); drawBt(); },function(err){ state('bt-state',err,'err'); $('bt-run').disabled=false; }); })(); }
  function drawBt(){ var d=bt.data, cv=$('bt-cv'); if(!d||!cv) return; var g=ctx2d(cv), c=g.c, pad={l:64,r:10,t:12,b:22}; var eq=d.equity, n=eq.length; var lo=Math.min(0,Math.min.apply(null,eq)), hi=Math.max(0,Math.max.apply(null,eq)); var m=(hi-lo)*.08||1; lo-=m; hi+=m;
    var sx=function(i){ return pad.l+(n>1?i/(n-1):0)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-(v-lo)/((hi-lo)||1)*(g.h-pad.t-pad.b); };
    axes(c,g.w,g.h,pad); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=lo+(hi-lo)*i/4; c.fillText(inr(v),pad.l-4,sy(v)+3); } c.strokeStyle='rgba(255,255,255,.18)'; c.beginPath(); c.moveTo(pad.l,sy(0)); c.lineTo(g.w-pad.r,sy(0)); c.stroke();
    var last=eq[n-1]; var grad=c.createLinearGradient(0,pad.t,0,g.h-pad.b); grad.addColorStop(0,last>=0?'rgba(72,232,150,.30)':'rgba(255,92,120,.30)'); grad.addColorStop(1,'rgba(0,0,0,0)'); c.fillStyle=grad; c.beginPath(); c.moveTo(sx(0),sy(0)); eq.forEach(function(v,i){ c.lineTo(sx(i),sy(v)); }); c.lineTo(sx(n-1),sy(0)); c.closePath(); c.fill();
    c.strokeStyle=last>=0?C.up:C.down; c.lineWidth=2; c.beginPath(); eq.forEach(function(v,i){ i?c.lineTo(sx(i),sy(v)):c.moveTo(sx(i),sy(v)); }); c.stroke();
    c.textAlign='center'; c.fillStyle=C.faint; [0,Math.floor(n/2),n-1].forEach(function(i){ if(d.rows[i]) c.fillText(d.rows[i].day,sx(i),g.h-8); }); c.textAlign='left'; c.fillStyle=C.text; c.fillText('cumulative P&L per lot · '+d.label,pad.l+6,pad.t+10);
    $('bt-rows').innerHTML=d.rows.slice().reverse().map(function(r){ return '<tr><td>'+r.day+'</td><td>'+nf(r.atm,0)+'</td><td class="'+(r.move_pct>=0?'up':'down')+'">'+(r.move_pct>=0?'+':'')+nf(r.move_pct,2)+'%</td><td>'+nf(r.credit,1)+'</td><td class="'+(r.pnl>=0?'up':'down')+'">'+inr(r.pnl)+'</td><td>'+nf(r.mae,1)+'</td></tr>'; }).join(''); }

  /* ---------------- lifecycle ---------------- */
  function refreshLive(){ if(visible('p-surf')) loadSurf(); if(visible('p-skew')) loadSkew(); if(visible('p-curv')) loadCurv(); if(visible('p-gex')) loadGex(); }
  refreshLive(); if(rpPanel) loadDays();
  setInterval(refreshLive,60000);
  window.addEventListener('resize',function(){ drawSurf(); drawSkew(); drawCurv(); drawGex(); drawRp(); drawBt(); });
  document.addEventListener('visibilitychange',function(){ if(!document.hidden) refreshLive(); });
  window.finoAnalyticsRefresh=refreshLive;
})();</script>
<script>(function(){var h=(location.hash||'').replace('#','');var el=h&&document.getElementById('p-'+h);if(el){setTimeout(function(){el.scrollIntoView({behavior:'smooth',block:'start'});},300);}})();</script>
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
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
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
.top .home-ic{flex:0 0 auto;width:30px;height:30px;border-radius:9px;overflow:hidden;margin-right:2px;box-shadow:0 0 0 1px rgba(245,200,66,.3)}
.top .home-ic img{width:100%;height:100%;display:block}
.top .home-ic:hover{box-shadow:0 0 0 1px var(--gold),0 0 16px rgba(245,200,66,.45)}
@keyframes fino-glow{0%,100%{box-shadow:0 0 0 1px rgba(245,200,66,.35),0 0 14px rgba(245,200,66,.22)}50%{box-shadow:0 0 0 1px rgba(245,200,66,.7),0 0 26px rgba(245,200,66,.5)}}
@media (prefers-reduced-motion:reduce){.top .home-ic{animation:none}}

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
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a>
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
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
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
.home-ic{position:fixed;top:14px;left:14px;width:36px;height:36px;border-radius:9px;overflow:hidden;z-index:5;box-shadow:0 0 0 1px rgba(245,200,66,.3)}
.home-ic img{width:100%;height:100%;display:block}.home-ic:hover{box-shadow:0 0 0 1px var(--gold),0 0 16px rgba(245,200,66,.45)}
@keyframes fino-glow{0%,100%{box-shadow:0 0 0 1px rgba(245,200,66,.35),0 0 14px rgba(245,200,66,.22)}50%{box-shadow:0 0 0 1px rgba(245,200,66,.7),0 0 26px rgba(245,200,66,.5)}}
@media (prefers-reduced-motion:reduce){.home-ic{animation:none}}
</style>
</head>
<body>
<a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a>
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
