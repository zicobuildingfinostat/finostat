"""Evergreen blog guides: written once, served forever, each pointing at the tool that does the job.
Slugs are stable (they are indexed URLs). Bodies are HTML fragments in the site's voice."""
from __future__ import annotations

VIP = '<a href="/vip-indicator">VIP Indicator</a>'
XAU = '<a href="/xau-sovereign">XAU Sovereign</a>'

GUIDES = [
    {"slug": "how-to-read-an-option-chain", "title": "How to read an option chain in five minutes: OI, PCR, max pain and walls", "tags": ["option chain", "open interest", "nifty"],
     "summary": "The four numbers on a NIFTY or BANKNIFTY option chain that tell you where the market is leaning, where it is likely to stall, and where it will hurt the most people at expiry.",
     "body": """
<p>An option chain looks like a wall of numbers. Traders who use it every day read only four things from it, in this order.</p>
<h2>1. Open interest by strike</h2>
<p>Open interest is the number of contracts still open at a strike. Where call OI piles up above spot, sellers have sold that strike heavily and will defend it: that is resistance. Where put OI piles up below spot, put writers are betting the market stays above it: support. On the free <a href="/option-chain/nifty">NIFTY chain</a> these show up as the <b>call wall</b> and <b>put wall</b>.</p>
<h2>2. Put–call ratio</h2>
<p>PCR is total put OI divided by total call OI. Around 0.8 to 1.2 is normal. Above 1.3 the crowd is loaded with puts, which often marks the late stage of a fall; below 0.7 it is loaded with calls, which often marks a tired rally. Watch the change through the day more than the level.</p>
<h2>3. Max pain</h2>
<p>Max pain is the strike at which the most option buyers lose at expiry. Price does not have to go there, but on expiry day it is where sellers would love it to pin, and it is a fair reference for "where will this settle if nothing happens".</p>
<h2>4. Change in OI, not just OI</h2>
<p>OI that was already there yesterday is old information. What matters is which strikes added or lost OI in the last 15 minutes and whether price rose or fell while they did. That combination is called build-up, and it is the difference between "resistance" and "resistance being attacked". The terminal's OISCAN panel tags every strike this way live; the <a href="/blog/oi-build-up-explained">build-up guide</a> explains the four tags.</p>
<h2>Putting it together</h2>
<p>A chain with a fat call wall 200 points above spot, a fat put wall 200 points below, PCR near 1 and max pain in the middle is a range: sellers' territory. A chain where the call wall is being eaten by fresh call buying while put writers add below is a breakout in progress. The __P__ reads this structure for you on the chart, and marks entries, stops and targets so you are not squinting at the table.</p>
""".replace("__P__", VIP)},
    {"slug": "expected-move-atm-straddle", "title": "Expected move: what the ATM straddle is telling you before you trade", "tags": ["expected move", "straddle", "implied volatility"],
     "summary": "The at-the-money straddle is the market's own price for the move to expiry. Here is how to turn it into a daily range, and how to tell when the day is running hotter than expected.",
     "body": """
<p>Before the first candle prints, the option market has already priced how far it expects the index to travel. That price is the ATM straddle: one call plus one put at the strike closest to spot.</p>
<h2>From straddle to range</h2>
<p>A straddle prices roughly 0.8 of a one-standard-deviation move to expiry. So 1σ ≈ straddle ÷ 0.8. For a single day, use implied volatility instead: <b>expected day move = spot × IV × √(1/252)</b>. With NIFTY at 23,400 and IV at 14%, that is about 206 points, a 1σ band of 23,194 to 23,606.</p>
<h2>Why it matters</h2>
<p>Every strategy is a bet on realised versus expected. Sellers earn when the day stays inside the band; buyers need it to break out. Knowing the band turns "the market moved 150 points" into "the market moved 0.7σ, well inside what was priced" — a very different sentence.</p>
<h2>Realised versus expected</h2>
<p>By 11:00 you can already compare today's high–low range against the 2σ-wide expected range. Under 60% and it is a quiet day where theta wins; over 120% and straddles are paying, so fresh short premium is dangerous. The terminal's MOVE panel draws the band on today's path and updates the ratio every 30 seconds; the daily <a href="/brief">expiry brief</a> carries the morning number.</p>
<h2>What sellers do with it</h2>
<p>Strikes at or beyond the 1σ band collect premium with a statistical edge on a normal day. The __P__ option-selling engine uses exactly this: it takes the expected move, the dealing range and the nearest supply and demand, and prints the call and put strikes on the chart, with a STAND ASIDE when the tape is expanding.</p>
""".replace("__P__", VIP)},
    {"slug": "iv-percentile-is-premium-rich", "title": "IV percentile: is the premium rich or cheap today?", "tags": ["implied volatility", "iv percentile", "option selling"],
     "summary": "A 180-point straddle means nothing on its own. Compare it with the same clock time on the last twenty expiry cycles and you know whether you are being paid to sell.",
     "body": """
<p>Option sellers have one job: sell premium when it is expensive and stay away when it is cheap. The problem is that "expensive" is relative. A NIFTY straddle worth ₹180 two days before expiry may be rich in a calm month and cheap in a volatile one.</p>
<h2>The fix: same time, same distance to expiry</h2>
<p>Take today's straddle as a percentage of spot. Now look at the same clock time on each of the last twenty expiry cycles, at the same distance from expiry. If today sits above 75% of them, premium is rich; below 25%, cheap. That is the straddle percentile. Do the same with the implied volatility you back out of the straddle and you have the IV percentile.</p>
<h2>Why not just use VIX?</h2>
<p>India VIX is useful and worth watching (its one-year rank tells you the broad regime), but it is a 30-day number for one index. Your trade is a specific expiry on a specific day; the percentile against past cycles is the like-for-like measure.</p>
<h2>How the numbers move through the day</h2>
<p>Straddles decay in a curve, not a line: fast in the first hour, flat through lunch, fast again into the close on expiry day. Plotting today against the median of past cycles shows whether you are early, on schedule or late. The terminal's IVP panel draws exactly that chart and updates the percentile every minute.</p>
<h2>A rule of thumb</h2>
<p>Sell when the straddle percentile is above 60 and the day's realised range is running under expected; stand aside below 30 or when the range is expanding. The __P__ SELLER engine bakes both checks into its score on NIFTY and BANKNIFTY.</p>
""".replace("__P__", VIP)},
    {"slug": "oi-build-up-explained", "title": "OI build-up explained: long build-up, short build-up, short covering and long unwinding", "tags": ["open interest", "oi build-up", "screener"],
     "summary": "Price and open interest move in four combinations, and each one means something different for calls and for puts. The four tags, and how to read them near the money.",
     "body": """
<p>Open interest tells you positions exist. The change in OI together with the change in price tells you what kind of positions are being added or removed. There are only four cases.</p>
<table><thead><tr><th>Price</th><th>OI</th><th>Tag</th><th>Meaning</th></tr></thead><tbody>
<tr><td>up</td><td>up</td><td>long build-up</td><td>fresh buying</td></tr>
<tr><td>down</td><td>up</td><td>short build-up</td><td>fresh writing</td></tr>
<tr><td>up</td><td>down</td><td>short covering</td><td>writers squeezed out</td></tr>
<tr><td>down</td><td>down</td><td>long unwinding</td><td>buyers giving up</td></tr>
</tbody></table>
<h2>Calls and puts read differently</h2>
<p>Short build-up in a call above spot is call writing: supply, a ceiling. Short build-up in a put below spot is put writing: support, a floor. Short covering in calls is bullish fuel (the ceiling is being removed); short covering in puts is bearish. Long build-up in calls is bullish speculation; long build-up in puts is either hedging or a bearish bet, which is why weighting matters.</p>
<h2>Windows</h2>
<p>Day-level build-up (versus the previous close) tells you the big picture. Fifteen-minute build-up tells you what is happening now. A call wall that has held all day but shows short covering in the last fifteen minutes is about to be tested.</p>
<h2>The desk read</h2>
<p>Put the tags near the money together: call writing above and put writing below is a range; call writers covering with put writers adding is a bullish lean; the reverse is bearish. The terminal's OISCAN panel samples NIFTY, BANKNIFTY, FINNIFTY and SENSEX every three minutes and writes this sentence for you, and screens the NIFTY 50 F&amp;O stocks on a day basis.</p>
<p>When the OI read and the chart's market structure agree, the setup is strong. The __P__ draws the structure side of that equation.</p>
""".replace("__P__", VIP)},
    {"slug": "market-structure-bos-choch", "title": "Market structure for option traders: break of structure and change of character", "tags": ["market structure", "smart money", "price action"],
     "summary": "Trend is a sequence of swing highs and lows. Two events, BOS and CHoCH, tell you whether the sequence is continuing or has just flipped, and they are the backbone of every smart-money read.",
     "body": """
<p>Indicators lag because they average. Structure does not: it is the raw sequence of swing highs and swing lows, and it changes on a single close.</p>
<h2>Swings</h2>
<p>A swing high is a candle whose high is higher than the three candles on either side; a swing low is the mirror. Because you need the three candles after it, a swing is confirmed three bars late. That delay is the price of never repainting.</p>
<h2>BOS: break of structure</h2>
<p>In an uptrend price makes higher highs and higher lows. When a close breaks the last swing high, the uptrend has continued: break of structure. It confirms what you already believed.</p>
<h2>CHoCH: change of character</h2>
<p>When, in that same uptrend, a close breaks the last swing <em>low</em> instead, the sequence has broken: change of character. It is the earliest structural warning that the trend has flipped, usually well before a moving average crosses.</p>
<h2>Why option traders care</h2>
<p>Structure sets the bias for everything else. A bullish structure with price in the lower half of its range (a discount) is where you sell puts or buy calls; a bearish structure in the upper half (premium) is where you sell calls. Trading against structure is how good option-chain reads still lose money.</p>
<h2>See it drawn</h2>
<p>The __P__ marks every swing, BOS and CHoCH on NIFTY, BANKNIFTY and any F&amp;O stock from 5-minute to daily candles, then layers order blocks, fair value gaps and liquidity on top. The <a href="/blog/order-blocks-and-fair-value-gaps">next guide</a> covers those zones.</p>
""".replace("__P__", VIP)},
    {"slug": "order-blocks-and-fair-value-gaps", "title": "Order blocks and fair value gaps: where the big orders sit on a NIFTY chart", "tags": ["order block", "fair value gap", "smart money"],
     "summary": "The two zones smart-money traders wait for, how they are defined precisely enough to code, and how to trade a return to them with options.",
     "body": """
<p>Large orders do not fill in one candle. They leave two footprints on the chart that price tends to revisit.</p>
<h2>Order block</h2>
<p>The last candle against the move before a break of structure. Before a sharp rally that breaks a swing high, look for the last red candle: that candle's range is the bullish order block. Institutions accumulated there, the market ran, and unfilled orders remain. A return to the block is a place to buy, or to sell puts below it. The block dies when price closes through it.</p>
<h2>Fair value gap</h2>
<p>A three-candle imbalance: when the low of candle three is above the high of candle one, the middle candle moved so fast that no trading happened in the gap. Markets tend to come back and fill it. Until then it acts as a magnet and, when price returns, as support in an uptrend.</p>
<h2>Rules that can be coded</h2>
<p>Vague definitions produce vague trades, so use strict ones. Order block: the last opposite-colour candle within twenty bars before a BOS or CHoCH, valid until a close beyond its far edge. FVG: low[i] &gt; high[i−2] for bullish, high[i] &lt; low[i−2] for bearish, valid until price trades through the gap's far edge. These are the definitions the __P__ uses, so what you see on the chart is reproducible.</p>
<h2>Trading a return</h2>
<p>Wait for price to enter a zone in the direction of structure, then look for a rejection candle or a displacement away from it. Sellers: sell the option on the other side of the zone. Buyers: enter with the stop beyond the zone. The zone gives you the location; the stop is defined for you.</p>
""".replace("__P__", VIP)},
    {"slug": "liquidity-sweeps-stop-hunts", "title": "Liquidity sweeps: why the stop hunt is the signal, not the noise", "tags": ["liquidity", "equal highs", "smart money"],
     "summary": "Equal highs and equal lows are where the market keeps everyone's stops. A wick through them that closes back inside is one of the cleanest reversal signals on any timeframe.",
     "body": """
<p>Ask where the stops are and you will know where price goes next. Stops cluster at obvious levels: equal highs from a double top, equal lows from a double bottom, yesterday's high and low.</p>
<h2>The sweep</h2>
<p>Price spikes above the equal highs, triggers the buy stops of everyone who was short and the breakout orders of everyone who was waiting, then closes back below the level. That is a liquidity sweep. The breakout traders are now trapped, and the market has fresh fuel to go the other way.</p>
<h2>Sweep versus breakout</h2>
<p>The difference is the close. A close beyond the level is a breakout; a wick beyond with a close back inside is a sweep. Only one of them is a reversal signal, which is why you must wait for the candle to finish before acting.</p>
<h2>On an index</h2>
<p>NIFTY sweeps the previous day's high or low several times a week, usually in the first hour. A sweep of the low followed by a bullish displacement candle and a break of the last minor swing high is the classic long setup; the mirror is the short. For sellers, a sweep of the high on a rangebound day is the moment to sell calls above it.</p>
<h2>Automating the read</h2>
<p>The __P__ finds equal highs and lows within a quarter of an ATR of each other, draws them as liquidity, marks the sweep with an × when it happens, and feeds it into the engine's score with a three-bar window so a sweep is fresh, not stale.</p>
""".replace("__P__", VIP)},
    {"slug": "greeks-a-seller-watches", "title": "The Greeks a seller actually watches: theta, vega and gamma on expiry day", "tags": ["greeks", "theta", "gamma", "expiry"],
     "summary": "You do not need all five Greeks to sell options well. You need to know how three of them behave in the last two days of an expiry, and what they cost when they turn.",
     "body": """
<p>Sellers get paid in theta and pay in gamma and vega. Understanding the exchange rate between them is the whole business.</p>
<h2>Theta: what you earn</h2>
<p>Theta is the daily decay of an option's price. It is not linear: an ATM option loses far more in the last two days than in the previous five. That is why expiry-day selling exists, and why it is crowded.</p>
<h2>Gamma: what you owe</h2>
<p>Gamma is how fast delta changes. In the last hours of expiry an ATM option's gamma explodes: a 100-point move can turn a comfortable short straddle into a directional position of several lots' worth of delta. Theta and gamma are the same number seen from two sides; the more you earn from decay, the more a move costs.</p>
<h2>Vega: the surprise</h2>
<p>Vega is the price sensitivity to a one-point change in implied volatility. On calm days it is a friend to sellers; on event days IV can jump five points in minutes and every short option marks against you at once, before spot has even moved.</p>
<h2>Measuring the book, not the leg</h2>
<p>Per-leg Greeks mislead. What matters is the net: delta in rupees per 1% move, gamma in rupees per 1% move, vega per point, theta per day, for the whole book across expiries. The terminal's RISK board shows exactly that and tells you how many futures lots or ATM options would flatten the delta.</p>
<h2>Sizing</h2>
<p>Decide the rupee loss you accept on a 2% move before you sell anything, and size so the shock grid says you are inside it. The __P__ SELLER engine only prints a strike when the regime is calm, but the position size is always yours.</p>
""".replace("__P__", VIP)},
    {"slug": "when-to-sell-premium-regime-checklist", "title": "When to sell premium and when to stand aside: a regime checklist", "tags": ["option selling", "regime", "adx", "range"],
     "summary": "Most losses from option selling come from selling on the wrong day, not at the wrong strike. Five checks that separate a selling day from a stand-aside day.",
     "body": """
<p>Selling options is a good business on the right days and a terrible one on the wrong days. The strike matters less than the regime. Run these five checks before you sell.</p>
<h2>1. Is there a trend? (ADX)</h2>
<p>ADX below 20 means price is oscillating: sellers' territory. Above 28 means a trend is in force and every sold option on the wrong side will be tested. Between them, size down.</p>
<h2>2. Is the range calm or coiled? (Bollinger width)</h2>
<p>Narrow bands mean a quiet market, which is good, until they get too narrow: a squeeze precedes expansion. Sell when band width is in the middle of its recent history, not at the very bottom.</p>
<h2>3. Where is price in its range?</h2>
<p>Mid-range is ideal for a straddle. Near the top of a bearish structure, sell calls; near the bottom of a bullish structure, sell puts. Selling straddles at the edge of a range is how you get run over on the breakout.</p>
<h2>4. Is premium rich?</h2>
<p>Check the straddle percentile against past cycles. If you are not being paid above the median, the edge is thin and the gamma risk is not.</p>
<h2>5. Is today quiet so far?</h2>
<p>Compare the realised range with the expected move. A day already at 120% of expected is an expanding day; adding shorts into it is fighting the tape.</p>
<h2>All five, automated</h2>
<p>The __P__ SELLER engine scores these five conditions on every closed candle, picks the side from market structure, prints the call and put strike on the chart, and prints STAND ASIDE when the score turns. Pair it with the RISK board and the day's plan writes itself.</p>
""".replace("__P__", VIP)},
    {"slug": "gold-trading-for-indian-traders", "title": "Gold for Indian traders: XAU/USD, MCX and how a gold engine reads the chart", "tags": ["gold", "xauusd", "mcx"],
     "summary": "Gold trades around the clock and rarely respects Indian market hours. What moves it, which chart to watch, and how a rules-based engine turns nine systems into one call.",
     "body": """
<p>Gold is the one market Indian traders follow that never closes for them. XAU/USD sets the price in London and New York; MCX Gold in rupees follows it with a currency overlay.</p>
<h2>What moves it</h2>
<p>Real US yields (gold pays no coupon, so higher real rates hurt it), the dollar index, central-bank buying, and fear. The Federal Reserve decision and US CPI are the two events that move it most; the <a href="/calendar">calendar</a> lists both in IST.</p>
<h2>Which chart</h2>
<p>Use XAU/USD for structure: it is the liquid reference, and the daily, four-hour and hourly charts carry the order blocks, fair value gaps and liquidity pools that MCX inherits. Trade the instrument you have access to, but read the chart the world reads.</p>
<h2>Nine systems, one call</h2>
<p>Trend-following rules that well-known traders published (the Turtle breakout, the 200-day rule, Linda Raschke's Holy Grail, MACD, RSI, Supertrend, Ichimoku, Bollinger, the EMA ribbon) each vote on every closed candle. A smart-money layer votes on structure, zones and liquidity. The blend is a score from −1 to +1; BUY prints above +0.25, SELL below −0.25, with hysteresis so it does not flip every bar. That is what __P__ does, with entry, stop and a 2R target on the chart and a Pine Script for TradingView.</p>
<h2>Timeframes</h2>
<p>Daily for the bias, four-hour for the swing, hourly for the entry. When all three agree, size normally; when they disagree, size small or wait. The gold panel in the <a href="/global">Global terminal</a> shows all three side by side with the DVOL volatility index and futures funding.</p>
""".replace("__P__", XAU)},
    {"slug": "scalping-index-options-vwap-supertrend", "title": "Scalping index options with VWAP and Supertrend: a fast trend playbook", "tags": ["scalping", "vwap", "supertrend", "banknifty"],
     "summary": "A one-to-fifteen-minute playbook for BANKNIFTY and NIFTY options: who is in control (VWAP), which way (EMA 9/21), where the stop goes (Supertrend), and when not to trade (ADX).",
     "body": """
<p>Scalping index options is not about speed. It is about taking only the trades where four simple things agree, and leaving the rest.</p>
<h2>Who is in control: VWAP</h2>
<p>The session VWAP is the average price everyone paid today. Above it, buyers are in control; below it, sellers. Longs above VWAP and shorts below is the first filter, and it removes half of all bad trades on its own.</p>
<h2>Which way: EMA 9 over 21</h2>
<p>The fast EMA over the slow one confirms direction on the timeframe you trade. The cross itself is late; use it as a filter, not a trigger.</p>
<h2>Where the stop goes: Supertrend 7/2</h2>
<p>Supertrend gives a trailing line that flips with the trend. It is the natural stop for a scalp and the natural exit when it flips, so you never have to decide where to get out under pressure.</p>
<h2>When not to trade: ADX</h2>
<p>Below 18 there is no trend, and scalping a range with options is paying theta to be whipsawed. Sit out.</p>
<h2>The option leg</h2>
<p>Buy the ATM or first OTM option in the direction of the signal; delta near 0.5 keeps the position responsive without paying for too much gamma. Target 1.5 times the risk; scalps that need more than that were not scalps.</p>
<h2>Automated</h2>
<p>The __P__ SCALPER engine scores VWAP, EMA, Supertrend and RSI momentum every closed candle, damps the score when ADX is low, and prints LONG, SHORT and EXIT with the Supertrend stop and the 1.5R target on the chart, on the web and as a Pine Script with alerts.</p>
""".replace("__P__", VIP)},
    {"slug": "dealer-gamma-gex-explained", "title": "Dealer gamma (GEX): why the market pins on some days and chases on others", "tags": ["gex", "gamma exposure", "dealer positioning"],
     "summary": "Option dealers hedge what they sell you. Whether that hedging dampens or amplifies moves depends on one number, and it explains most expiry-day behaviour.",
     "body": """
<p>When you buy an option, a market maker sold it and hedged it with the underlying. Those hedges are mechanical, and in aggregate they move the market.</p>
<h2>Positive gamma pins</h2>
<p>When dealers are net long gamma (customers sold them calls), they sell into rallies and buy dips to stay delta-neutral. That hedging leans against every move; the index pins near the strikes with the most gamma. Sellers love these days.</p>
<h2>Negative gamma chases</h2>
<p>When dealers are net short gamma (customers bought protection), they must buy as the market rises and sell as it falls. Their hedging pushes the move further. Breakouts run, gaps extend, and short premium bleeds.</p>
<h2>The flip level</h2>
<p>Summing dealer gamma across strikes gives a curve that crosses zero at some price: the gamma flip. Above it the market is in pinning mode, below it in chasing mode. Knowing which side of the flip you are on is worth more than most indicators.</p>
<h2>Where to see it</h2>
<p>The terminal's GEX panel computes dealer gamma by strike from open interest in rupee crores per 1% move for NIFTY and BANKNIFTY, marks the flip, and the alert engine can wake you when the flip moves. Read it with the OI build-up tags from OISCAN and the structure drawn by the __P__ and the day's behaviour stops being mysterious.</p>
""".replace("__P__", VIP)},
]
