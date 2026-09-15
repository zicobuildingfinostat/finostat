"""Starter catalogue for /shop: Finostat-branded goods with trader phrases, seeded once when the shop is
empty. Each item gets a generated branded mockup (SVG) so the shelves look full from day one; replace
with real product photos from /shop/admin whenever they exist."""
from __future__ import annotations

import html
import secrets

GOLD, INDIGO, CYAN, PINK, TEXT = "#f5c842", "#120a33", "#7fe0f0", "#ff6ec7", "#f1edff"
FONT_D = "Barlow Condensed, Impact, sans-serif"
FONT_M = "IBM Plex Mono, ui-monospace, Menlo, monospace"

# (name, kind, phrase, sub, price, compare, sizes, description)
ITEMS = [
    ("Theta Gang Mug", "mug", "TIME DECAYS.\nI COLLECT.", "330 ml ceramic · gold rim", 499, 699, [],
     "The seller's morning cup. 330 ml ceramic mug, matte indigo with a gold rim, dishwasher safe. Front: TIME DECAYS. I COLLECT. Back: the Finostat mark. Comes in a kraft box."),
    ("Max Pain Mug", "mug", "MEET ME AT\nMAX PAIN", "330 ml ceramic · gold rim", 499, 699, [],
     "For the expiry-day desk. 330 ml ceramic, matte indigo, gold rim, dishwasher safe. Front: MEET ME AT MAX PAIN. Back: a NIFTY option-chain strip in gold."),
    ("Sell Premium Tee", "tee", "SELL PREMIUM.\nSTAY HUMBLE.", "240 GSM heavyweight cotton", 899, 1199, ["S", "M", "L", "XL", "XXL"],
     "Heavyweight 240 GSM combed cotton, oversized drop-shoulder fit, indigo with a gold chest print. Back: FINOSTAT · DESK-GRADE across the shoulders. Pre-shrunk; wash inside out."),
    ("IV Crush Survivor Tee", "tee", "IV CRUSH\nSURVIVOR", "240 GSM heavyweight cotton", 899, 1199, ["S", "M", "L", "XL", "XXL"],
     "You bought the straddle before results. You know. 240 GSM combed cotton, oversized fit, indigo with a cyan print. Back: a vol-surface heatmap in gold."),
    ("Delta Neutral Tee", "tee", "DELTA NEUTRAL,\nEMOTIONALLY VOLATILE", "240 GSM heavyweight cotton", 899, 1199, ["S", "M", "L", "XL", "XXL"],
     "The most honest line in options. 240 GSM combed cotton, oversized fit, black with a gold print. Back: Γ · Θ · V · Δ in a column."),
    ("Zero DTE Hoodie", "hoodie", "ZERO DTE.\nZERO FEAR.", "400 GSM fleece · kangaroo pocket", 1899, 2499, ["S", "M", "L", "XL", "XXL"],
     "Expiry-day armour. 400 GSM brushed fleece, kangaroo pocket, ribbed cuffs, indigo with an embroidered gold mark on the chest and ZERO DTE. ZERO FEAR. printed across the back."),
    ("The Chain Desk Mat", "mat", "THE CHAIN", "900 × 400 mm · stitched edge", 1299, 1599, [],
     "An XL desk mat printed with a full NIFTY option chain in the terminal's palette: strikes, OI bars, walls, max pain. 900 × 400 mm, 4 mm rubber base, stitched edge, wipe clean. Keyboard and mouse live on the chain."),
    ("Gamma Flip Mouse Pad", "mat", "GAMMA FLIP", "260 × 210 mm · rubber base", 399, 549, [],
     "Dealer gamma profile printed edge to edge, flip level in gold. 260 × 210 mm, 3 mm rubber base, smooth cloth top for low-DPI precision."),
    ("Finostat Desk 87 Keyboard", "keyboard", "BUY · SELL · HEDGE", "TKL mechanical · hot-swap · gold keycaps", 6999, 8499, [],
     "A tenkeyless mechanical keyboard built for the desk: hot-swappable linear switches, PBT keycaps in indigo with gold legends, a gold BUY key, a pink SELL key and a cyan HEDGE key on the function row. USB-C, detachable cable, gasket-mounted for a soft, quiet bottom-out. Ships with a keycap puller and the three novelty caps fitted."),
    ("BUY / SELL / HEDGE Keycap Set", "keycaps", "BUY · SELL · HEDGE", "3 novelty caps · Cherry profile", 599, 799, [],
     "Three PBT novelty keycaps in Cherry profile: BUY in gold, SELL in pink, HEDGE in cyan. Fits any MX-style board. Put them on F1, F2 and Esc and never mis-click again."),
    ("The Trade Journal", "journal", "WRITE THE TRADE.\nTHEN TAKE IT.", "A5 · 200 pages · R-multiple columns", 449, 599, [],
     "A5 hardback, 200 ruled pages laid out for options: setup, entry, stop, target, R planned, R achieved, what the tape said. Lay-flat binding, ribbon marker, gold-foil mark on indigo cloth."),
    ("Greeks Sticker Pack", "stickers", "Δ Γ Θ V", "8 die-cut vinyl stickers", 199, 299, [],
     "Eight die-cut vinyl stickers: Delta, Gamma, Theta, Vega, MAX PAIN, THETA GANG, the Finostat mark and a tiny option chain. Weatherproof, laptop-safe."),
    ("PCR 1.0 Cap", "cap", "PCR 1.0", "6-panel cotton twill · brass buckle", 599, 799, [],
     "Balanced, like the market on a good day. Six-panel unstructured cotton twill in indigo, gold embroidered PCR 1.0 on the front, Finostat on the back strap, brass buckle."),
    ("Nine Systems, One Call Poster", "poster", "NINE SYSTEMS.\nONE CALL.", "A2 · 250 GSM matte", 699, 899, [],
     "An A2 print of the engine: nine published systems and the smart-money layer feeding one score, drawn in gold and cyan on indigo. 250 GSM matte, ships rolled in a tube."),
    ("Straddle & Chill Tumbler", "tumbler", "STRADDLE\n& CHILL", "500 ml steel · double wall", 799, 999, [],
     "Double-wall stainless steel, 500 ml, keeps the chai hot through the first hour and the water cold through the last. Matte indigo, gold print, leak-proof lid."),
    ("Position Sized Laptop Sleeve", "sleeve", "POSITION SIZED", "13–14 inch · neoprene", 1299, 1599, [],
     "Fits 13 to 14 inch laptops. Neoprene with a soft lining, indigo with POSITION SIZED in gold along the zip. A small pocket for the charger and the journal."),
    ("Stay Hedged Bottle", "bottle", "STAY HEDGED", "750 ml steel · single wall", 699, 899, [],
     "750 ml single-wall stainless steel bottle, matte indigo, gold print, bamboo lid. Light enough for the gym bag, honest enough for the desk."),
    ("Long Gamma Tote", "tote", "LONG GAMMA", "heavy canvas · 40 × 38 cm", 499, 699, [],
     "Heavy 12 oz canvas tote, natural with an indigo print: LONG GAMMA on one side, the Finostat mark on the other. Long handles, inside pocket. Carries the journal, the tumbler and the week's groceries."),
]


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def mockup(name: str, kind: str, phrase: str, sub: str) -> str:
    """A branded square mockup: silhouette of the object with the phrase, indigo/gold palette."""
    lines = phrase.split("\n")
    body = []
    if kind in ("mug", "tumbler", "bottle"):
        body.append(f'<rect x="260" y="230" width="380" height="440" rx="34" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/>')
        if kind == "mug":
            body.append(f'<path d="M640 320 q120 0 120 110 t-120 110" fill="none" stroke="{GOLD}" stroke-width="18"/>')
            body.append(f'<rect x="260" y="230" width="380" height="18" fill="{GOLD}"/>')
        else:
            body.append(f'<rect x="300" y="190" width="300" height="52" rx="10" fill="{GOLD}"/>')
    elif kind in ("tee", "hoodie"):
        body.append(f'<path d="M300 250 L380 200 Q450 240 520 200 L600 250 L660 340 L590 380 L590 720 L310 720 L310 380 L240 340 Z" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6" stroke-linejoin="round"/>')
        if kind == "hoodie":
            body.append(f'<path d="M380 200 Q450 150 520 200 Q450 260 380 200 Z" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/><rect x="380" y="560" width="140" height="90" rx="10" fill="none" stroke="{GOLD}" stroke-width="5"/>')
    elif kind in ("mat",):
        body.append(f'<rect x="130" y="300" width="640" height="300" rx="18" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/>')
        for i in range(12):
            h = 20 + (i * 37) % 120
            body.append(f'<rect x="{170 + i * 50}" y="{560 - h}" width="22" height="{h}" fill="{CYAN if i % 2 == 0 else PINK}" opacity=".8"/>')
    elif kind == "keyboard":
        body.append(f'<rect x="120" y="360" width="660" height="230" rx="16" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/>')
        for r in range(4):
            for c in range(15):
                col = GOLD if (r == 0 and c == 1) else PINK if (r == 0 and c == 2) else CYAN if (r == 0 and c == 0) else "#2c1c66"
                body.append(f'<rect x="{146 + c * 42}" y="{384 + r * 48}" width="36" height="40" rx="6" fill="{col}"/>')
    elif kind == "keycaps":
        for i, (lab, col) in enumerate((("BUY", GOLD), ("SELL", PINK), ("HEDGE", CYAN))):
            x = 180 + i * 200
            body.append(f'<rect x="{x}" y="380" width="160" height="160" rx="18" fill="{col}"/><rect x="{x + 14}" y="{394}" width="132" height="120" rx="12" fill="rgba(0,0,0,.15)"/>')
            body.append(f'<text x="{x + 80}" y="470" fill="#0c0626" font-family="{FONT_M}" font-size="30" font-weight="700" text-anchor="middle">{lab}</text>')
    elif kind == "journal":
        body.append(f'<rect x="270" y="220" width="360" height="470" rx="10" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/><rect x="270" y="220" width="30" height="470" fill="{GOLD}"/>')
    elif kind == "stickers":
        for i, (lab, col) in enumerate((("Δ", GOLD), ("Γ", CYAN), ("Θ", PINK), ("V", TEXT))):
            x, y = 230 + (i % 2) * 260, 260 + (i // 2) * 240
            body.append(f'<circle cx="{x + 100}" cy="{y + 100}" r="96" fill="{INDIGO}" stroke="{col}" stroke-width="8"/><text x="{x + 100}" y="{y + 130}" fill="{col}" font-family="{FONT_D}" font-size="88" font-weight="700" text-anchor="middle">{lab}</text>')
    elif kind == "cap":
        body.append(f'<path d="M230 470 Q450 200 670 470 Z" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/><path d="M160 480 Q450 430 740 480 L740 510 Q450 470 160 510 Z" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/>')
    elif kind == "poster":
        body.append(f'<rect x="230" y="150" width="440" height="600" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/>')
        for i in range(9):
            body.append(f'<circle cx="{280 + (i % 3) * 170}" cy="{260 + (i // 3) * 120}" r="22" fill="none" stroke="{CYAN}" stroke-width="3"/><line x1="{280 + (i % 3) * 170}" y1="{282 + (i // 3) * 120}" x2="450" y2="660" stroke="{GOLD}" stroke-width="1.5" opacity=".6"/>')
        body.append(f'<circle cx="450" cy="660" r="34" fill="{GOLD}"/>')
    elif kind == "sleeve":
        body.append(f'<rect x="160" y="300" width="580" height="360" rx="24" fill="{INDIGO}" stroke="{GOLD}" stroke-width="6"/><line x1="200" y1="340" x2="700" y2="340" stroke="{GOLD}" stroke-width="6" stroke-dasharray="12 8"/>')
    elif kind == "tote":
        body.append(f'<rect x="230" y="330" width="440" height="400" rx="12" fill="#efe6cf" stroke="{INDIGO}" stroke-width="6"/><path d="M330 330 Q330 200 450 200 Q570 200 570 330" fill="none" stroke="{INDIGO}" stroke-width="16"/>')
    # phrase overlay
    n = len(lines)
    size = 62 if max(len(x) for x in lines) <= 14 else 46
    y0 = 470 - (n - 1) * size * 0.55
    for i, ln in enumerate(lines):
        col = GOLD if kind != "tote" else INDIGO
        body.append(f'<text x="450" y="{y0 + i * size * 1.05:.0f}" fill="{col}" font-family="{FONT_D}" font-size="{size}" font-weight="700" text-anchor="middle" letter-spacing="1">{_esc(ln)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900" role="img" aria-label="{_esc(name)} mockup">'
            f'<defs><radialGradient id="g" cx=".5" cy=".4" r=".8"><stop offset="0" stop-color="#1c1052"/><stop offset="1" stop-color="#06031a"/></radialGradient></defs>'
            f'<rect width="900" height="900" fill="url(#g)"/>' + "".join(body)
            + f'<text x="450" y="810" fill="{CYAN}" font-family="{FONT_M}" font-size="22" text-anchor="middle" letter-spacing="3">{_esc(sub.upper())}</text>'
            f'<text x="450" y="850" fill="{GOLD}" font-family="{FONT_M}" font-size="18" text-anchor="middle" letter-spacing="6">FINOSTAT</text></svg>')


def seed(shop) -> int:
    """Create the starter catalogue if the shop has no products. Returns how many were created."""
    if shop.products(active_only=False):
        return 0
    n = 0
    for name, kind, phrase, sub, price, compare, sizes, desc in ITEMS:
        img = f"{secrets.token_hex(8)}.svg"
        (shop.img_dir / img).write_text(mockup(name, kind, phrase, sub), encoding="utf-8")
        shop.save_product({"name": name, "description": desc + "\n\nPhoto shown is the design mockup; the product ships in the printed colours.", "price": price, "compare_price": compare,
                           "stock": 25, "sizes": sizes, "images": [img], "active": True, "sort": n})
        n += 1
    return n
