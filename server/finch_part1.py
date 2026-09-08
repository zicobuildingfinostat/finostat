"""Finch chapters 1-6. HTML fragments; live widgets are <div data-live="..."> blocks."""

def _ex(k, s, inner, r="live"):
    return f'<div class="example"><div class="hd"><span class="k">{k}</span><span class="s">{s}</span><span class="r">{r}</span></div><div class="bd">{inner}</div></div>'

CHAPTERS = [
{"slug": "start-here", "level": "orientation", "title": "Start here: what F&O is and how to use Finch",
 "summary": "Derivatives in one page, why retail traders lose, how this course is built on today's live market, and what you'll be able to do by the end.",
 "body": """
<h2>What a derivative is</h2>
<p>A <strong>derivative</strong> is a contract whose value is <em>derived</em> from something else — an index like NIFTY 50, a stock like RELIANCE, a commodity, a currency. You never own the underlying thing; you own an agreement about its price. In India the two derivatives that matter for a retail trader are <strong>futures</strong> and <strong>options</strong>, traded together on the exchange's F&amp;O segment. Futures are obligations; options are choices. That single distinction runs through everything that follows.</p>
<p>Here is the market this course is taught on. These numbers are live — reload in an hour and they will have moved.</p>
""" + _ex("LIVE", "THE MARKET RIGHT NOW", '<div data-live="spot"></div>') + """
<h2>Why derivatives exist at all</h2>
<p>Derivatives were invented for <strong>hedging</strong> — transferring risk to someone willing to carry it. A farmer locks in a price for a harvest months away; an exporter fixes the rupees a dollar invoice will fetch; a fund that owns ₹200 crore of NIFTY stocks buys puts before a budget. In every case someone with an exposure pays someone else to absorb the uncertainty.</p>
<p>The person absorbing it is often a <strong>speculator</strong> — someone with no underlying exposure, trading purely on a view. Speculators are not villains: without them the farmer finds no counterparty. But it is worth being honest about which side you are on. As a retail F&amp;O trader you are almost always the speculator, and you are trading against institutions, market makers and algorithms whose edge is speed, capital and information. That is not a reason not to trade. It is the reason to <em>understand</em> before you trade.</p>
<aside class="warn"><b>The number nobody advertises</b><p>SEBI's own study of FY22–FY24 found that about <strong>93% of individual F&amp;O traders lost money</strong>, and the losses were concentrated in the most active, least experienced accounts. The typical loser was buying cheap out-of-the-money options in the last days before expiry. By the end of this course you will understand precisely why that trade is designed to lose — and what the people on the other side of it are doing.</p></aside>
<h2>The Indian F&amp;O landscape in a few facts</h2>
<ul>
<li><strong>Index derivatives dominate.</strong> NIFTY 50, BANKNIFTY, FINNIFTY on NSE and SENSEX on BSE account for the overwhelming majority of contracts traded. Index options are cash-settled: no shares ever change hands.</li>
<li><strong>Stock derivatives exist for roughly 200 large stocks</strong> (the “F&amp;O list”). Since 2019 they are <em>physically settled</em>: hold an in-the-money stock option through expiry and you will receive or must deliver actual shares. Chapter 9 covers why that matters.</li>
<li><strong>You trade in lots, not shares.</strong> Every contract has a fixed lot size set by the exchange (below, live, for NIFTY). The lot is the smallest quantity you can trade, and your profit or loss is always <em>premium change × lot</em>.</li>
<li><strong>Expiries are weekly and monthly.</strong> Index options currently expire weekly on a fixed weekday (NSE's NIFTY on Tuesdays and BSE's SENSEX on Thursdays at the time of writing — the terminal always shows the actual dates), stock options monthly.</li>
</ul>
""" + _ex("LIVE", "NIFTY CONTRACT SPECS", '<div data-live="lot"></div>') + """
<h2>How Finch is built</h2>
<p>Every chapter has two kinds of content. The <strong>prose</strong> explains a concept the way a good desk mentor would, with worked numbers. The <strong>live blocks</strong> — the dark panels marked LIVE — are pulled from the same feed and option chains the Finostat terminal runs on. They are not illustrations; they are today's market. When a chapter says “right now the ATM straddle costs ₹X, which implies a move of ±Y%”, X and Y are real and were computed the moment the page loaded.</p>
<p>The chapters build on each other. If you are brand new, read them in order: derivatives → futures → options basics → reading a chain → pricing → Greeks → volatility → expiry → strategies → risk → mistakes. If you already trade, jump to <a href="/finch/the-greeks">the Greeks</a> or <a href="/finch/implied-volatility">implied volatility</a>; those two chapters are where most self-taught traders have gaps.</p>
<h3>What you'll be able to do at the end</h3>
<ul>
<li>Read an option chain and say, from the numbers alone, what the market expects to happen by expiry.</li>
<li>Explain why a ₹5 option “doubled” and still lost you money.</li>
<li>Choose a strategy from a view — direction, magnitude, timing, volatility — rather than from a tip.</li>
<li>Size a position so a bad week is survivable, which is the whole game.</li>
</ul>
<p><a class="cta" href="/finch/derivatives-101">Begin with Derivatives 101 →</a></p>
"""},

{"slug": "derivatives-101", "level": "foundation", "title": "Derivatives 101: forwards, futures and options",
 "summary": "The three contracts, the difference between an obligation and a right, and the vocabulary — underlying, expiry, lot, margin — you will use every day.",
 "body": """
<h2>The forward: a promise with a price</h2>
<p>Suppose you agree today to buy 65 NIFTY-worth of index exposure from me in two weeks at 23,700, whatever the index does in between. That is a <strong>forward</strong>. If NIFTY is at 24,200 on the day, you buy from me at 23,700 and are 500 points × 65 = ₹32,500 better off; I am the same amount worse off. If NIFTY is at 23,200, the reverse. Neither of us paid anything today; we simply exchanged a promise. A forward is a <em>zero-sum bet on the price at a fixed date</em>.</p>
<p>Forwards have two problems: you have to trust me to pay, and you cannot get out early because the contract is private. Exchanges solved both.</p>
<h2>The future: a forward, standardised and guaranteed</h2>
<p>A <strong>futures contract</strong> is a forward with three changes. The terms are <em>standardised</em> (fixed lot, fixed expiry dates, fixed underlying), so the contract is fungible and you can exit by selling to anyone. The exchange's clearing corporation stands between every buyer and seller, so counterparty risk disappears. And profits and losses are settled <em>every day</em> — “marked to market” — so nobody accumulates a debt they cannot pay. To trade one you post a <strong>margin</strong>, a deposit sized to cover a bad day or two, and the exchange tops it up from you or pays you out nightly.</p>
<table><thead><tr><th>Feature</th><th>Forward</th><th>Future</th></tr></thead><tbody>
<tr><td>Where traded</td><td>Privately</td><td>Exchange</td></tr><tr><td>Terms</td><td>Negotiated</td><td>Standardised</td></tr>
<tr><td>Counterparty risk</td><td>Yes</td><td>None (clearing corp)</td></tr><tr><td>Settlement</td><td>At expiry</td><td>Daily mark-to-market + expiry</td></tr>
<tr><td>Exit before expiry</td><td>Hard</td><td>Sell any time</td></tr></tbody></table>
<h2>The option: a right, not an obligation</h2>
<p>Now change one thing. Instead of <em>promising</em> to buy at 23,700, you pay me ₹180 per share today for the <em>right</em> to buy at 23,700 in two weeks if you want to. If NIFTY is at 24,200 you exercise: worth 500, cost 180, net +320. If NIFTY is at 23,200 you simply don't; you lose the 180 and nothing more. That is a <strong>call option</strong>. The ₹180 is the <strong>premium</strong>; 23,700 is the <strong>strike</strong>; the date is the <strong>expiry</strong>. A <strong>put option</strong> is the mirror: the right to <em>sell</em> at the strike.</p>
<p>The person who sold you that right — the <strong>writer</strong> — keeps the ₹180 whatever happens, and in exchange takes on the obligation to deliver if you exercise. Buyer: limited loss, unlimited upside, pays. Writer: limited gain, potentially large loss, is paid. Every option trade has one of each.</p>
<aside class="tip"><b>The one sentence to remember</b><p>A future is a bet on <em>where</em> price will be. An option is a bet on where price will be <em>and how much you paid for the chance to be right</em>. Most beginners lose not because their direction was wrong but because they overpaid for the option — the market moved their way and they still lost money. Chapter 6 shows exactly how.</p></aside>
<h2>Vocabulary you'll use every day</h2>
<table><thead><tr><th>Term</th><th>Meaning</th></tr></thead><tbody>
<tr><td>Underlying</td><td>What the contract is on: NIFTY 50, BANKNIFTY, a stock.</td></tr>
<tr><td>Lot size</td><td>Number of underlying units per contract. Fixed by the exchange; revised periodically. Your P&amp;L is always per-share change × lot.</td></tr>
<tr><td>Expiry</td><td>The date the contract settles. Weekly for index options, monthly for stocks. After expiry the contract does not exist.</td></tr>
<tr><td>Strike</td><td>The price at which an option can be exercised. Strikes are spaced at a fixed step (NIFTY: 50 points).</td></tr>
<tr><td>Premium</td><td>The price of an option, quoted per share. A “₹180 call” costs ₹180 × lot.</td></tr>
<tr><td>Margin</td><td>Collateral the exchange holds against a futures or short-option position. Option <em>buyers</em> pay the full premium and post no margin.</td></tr>
<tr><td>Open interest (OI)</td><td>Number of contracts currently open. Rises when new positions are created, falls when they are closed.</td></tr>
<tr><td>Long / short</td><td>Long = you bought (you profit if price rises / the option gains). Short = you sold first (you profit if it falls / decays).</td></tr>
</tbody></table>
<p>Here are those terms on today's NIFTY contract — the lot, the strike step and the nearest expiry, straight from the exchange's instrument master:</p>
""" + _ex("LIVE", "TODAY'S NIFTY CONTRACT", '<div data-live="lot"></div>') + """
<h2>What settles how</h2>
<p><strong>Index derivatives</strong> are cash-settled: at expiry the difference between the strike (or futures price) and the index's final settlement value is simply credited or debited. <strong>Stock derivatives</strong> are physically settled: an in-the-money stock option at expiry becomes an actual delivery of shares, with the full contract value changing hands. A ₹10,000 option position can turn into a ₹15 lakh delivery obligation on expiry day. Chapter 9 is entirely about this.</p>
<p>Next: <a href="/finch/futures">how futures are priced and margined</a>, with the live NIFTY level.</p>
"""},

{"slug": "futures", "level": "foundation", "title": "Futures: price, basis, margin and mark-to-market",
 "summary": "Why the future trades above spot, what basis tells you, how SPAN margin and daily settlement work, and the arithmetic of a one-lot NIFTY futures trade.",
 "body": """
<h2>Why the future is not the spot price</h2>
<p>If NIFTY is at 23,650 today, why would its one-month future trade at, say, 23,760? Because holding the future instead of the underlying <em>saves you money</em>: you don't have to tie up ₹15 lakh buying 65 units of the index. That saved capital earns interest. So the fair future price is spot plus the <strong>cost of carry</strong> — the interest on the money you didn't spend — minus any dividends you forgo:</p>
<p><code>F = S × (1 + r × t) − dividends</code>&nbsp; where <em>r</em> is the risk-free rate and <em>t</em> the time to expiry in years.</p>
<p>At 6.5% for one month on 23,650 that is roughly 23,650 × 0.065 / 12 ≈ <strong>128 points</strong>. If the future trades more than that above spot, the market is paying to be long — mild bullishness, or a squeeze. If it trades <em>below</em> fair value, or even below spot (“backwardation”), someone is paying to be short: hedgers dumping futures, dividend season, or fear.</p>
""" + _ex("LIVE", "COST OF CARRY ON TODAY'S SPOT", '<div data-live="spot"></div><p>Fair one-month futures premium at 6.5%: spot × 0.065 / 12. For NIFTY that is about 0.54% above spot — roughly 128 points at 23,650. Compare it with the actual futures quote on your broker: the gap between the two is the <em>basis</em>.</p>', "live spot") + """
<h2>Basis and what it tells you</h2>
<p><strong>Basis</strong> = futures price − spot. It converges to zero at expiry (the future settles at the spot value), so it shrinks a little every day. A basis wider than fair value means demand to be long; narrower means demand to be short. Traders watch the basis on BANKNIFTY and on individual stocks around results: a stock future flipping to a discount before earnings is a tell that large holders are hedging.</p>
<h2>Margin: how much a lot really costs</h2>
<p>A NIFTY futures lot at 23,650 controls about ₹15.4 lakh of index. You do not pay that. You post <strong>SPAN + exposure margin</strong>, typically 12–15% of contract value for an index (higher for volatile stocks), so roughly <strong>₹1.9–2.3 lakh</strong> per lot. That is your leverage: a 1% move in NIFTY (236 points × 65 = ₹15,340) is about 7% of your margin. A 3% down day — they happen a few times a year — is a fifth of your capital gone in a session.</p>
<aside class="warn"><b>Margin is not your maximum loss</b><p>Margin is the exchange's deposit, not a cap on what you can lose. If NIFTY gaps 5% against you overnight the loss is 5% of ₹15.4 lakh = ₹77,000, whether or not your margin covered it. Your broker will square you off and pursue the shortfall. This is why Chapter 11 sizes positions by <em>worst plausible loss</em>, never by margin.</p></aside>
<h2>Mark-to-market: settling every night</h2>
<p>Suppose you buy one NIFTY future at 23,700 on Monday. Monday's close is 23,760: ₹60 × 65 = ₹3,900 is credited to your account that night. Tuesday closes at 23,640: ₹120 × 65 = ₹7,800 is debited. You never see a single “final” P&amp;L; it arrives in daily pieces, and if the debits drain your margin below the maintenance level you get a <strong>margin call</strong> — top up or be squared off. Futures P&amp;L is brutally linear: every point is ₹65, up or down, forever, until you exit.</p>
<h3>A complete one-lot example</h3>
<table><thead><tr><th>Day</th><th>Close</th><th>Change</th><th>MTM (× 65)</th><th>Running P&amp;L</th></tr></thead><tbody>
<tr><td>Mon (buy 23,700)</td><td>23,760</td><td>+60</td><td>+₹3,900</td><td>+₹3,900</td></tr>
<tr><td>Tue</td><td>23,640</td><td>−120</td><td>−₹7,800</td><td>−₹3,900</td></tr>
<tr><td>Wed</td><td>23,900</td><td>+260</td><td>+₹16,900</td><td>+₹13,000</td></tr>
<tr><td>Thu (sell 23,880)</td><td>—</td><td>−20</td><td>−₹1,300</td><td><strong>+₹11,700</strong></td></tr></tbody></table>
<p>Total: (23,880 − 23,700) × 65 = ₹11,700, before brokerage, STT (on the sell side), exchange charges and GST — which for a round trip on one lot come to a few hundred rupees.</p>
<h2>When futures are the right tool</h2>
<p>Futures are the cleanest way to express a <em>directional</em> view with <em>no time decay</em> and no volatility exposure: you are right if price goes your way, full stop. They are the wrong tool when you want limited risk, when you expect a range rather than a trend, or when you have a view on volatility rather than direction. For those, you need options — next chapter.</p>
"""},

{"slug": "options-basics", "level": "foundation", "title": "Options basics: calls, puts, moneyness and what a premium is made of",
 "summary": "Calls and puts from both sides, in/at/out-of-the-money, intrinsic versus time value, and the live NIFTY chain to see it all in real prices.",
 "body": """
<h2>Calls and puts, from both sides</h2>
<p>A <strong>call</strong> is the right to <em>buy</em> the underlying at the strike by expiry. A <strong>put</strong> is the right to <em>sell</em> at the strike. Each has a buyer and a writer, giving four basic positions:</p>
<table><thead><tr><th>Position</th><th>You want</th><th>Max loss</th><th>Max gain</th><th>Pays / receives</th></tr></thead><tbody>
<tr><td>Long call</td><td>Price up, fast</td><td>Premium paid</td><td>Unlimited</td><td>Pays</td></tr>
<tr><td>Long put</td><td>Price down, fast</td><td>Premium paid</td><td>Strike − 0 (large)</td><td>Pays</td></tr>
<tr><td>Short call</td><td>Price flat or down</td><td>Unlimited</td><td>Premium received</td><td>Receives</td></tr>
<tr><td>Short put</td><td>Price flat or up</td><td>Strike − 0 (large)</td><td>Premium received</td><td>Receives</td></tr></tbody></table>
<p>Notice the asymmetry. Buyers have small, known losses and open-ended gains; writers the reverse. Yet, as Chapter 6 will show, writers win <em>more often</em> — because buyers pay for that open-ended gain up front, and most of the time it does not arrive.</p>
<h2>Moneyness: where the strike sits relative to spot</h2>
<ul>
<li><strong>In the money (ITM)</strong>: exercising now would be worth something. A call with strike below spot; a put with strike above spot.</li>
<li><strong>At the money (ATM)</strong>: strike closest to spot. Highest time value, highest gamma, the centre of the chain.</li>
<li><strong>Out of the money (OTM)</strong>: exercising now is worthless. A call above spot; a put below. All of its premium is hope.</li>
</ul>
<p>Look at the live chain. Read the CE column downward: calls get cheaper as the strike rises above spot because each one needs a bigger rally to pay. Read the PE column upward for the mirror image.</p>
""" + _ex("LIVE", "NIFTY CHAIN · ATM ± 3", '<div data-live="chain"></div>') + """
<h2>What the premium is made of</h2>
<p>Every option premium is two things added together:</p>
<p><code>Premium = Intrinsic value + Time value</code></p>
<p><strong>Intrinsic value</strong> is what the option would be worth if exercised this instant: for a call, <em>max(spot − strike, 0)</em>; for a put, <em>max(strike − spot, 0)</em>. It is never negative. An OTM option has zero intrinsic value by definition.</p>
<p><strong>Time value</strong> is everything else — the price of the <em>possibility</em> that the option ends up (more) in the money before expiry. It depends on how long is left, how much the underlying tends to move (volatility), and how far the strike is from spot. Time value is highest at the money and decays to exactly zero at expiry. This decay is <strong>theta</strong>, and it is the reason option writing is a business.</p>
<h3>Worked example on a live chain</h3>
<p>Take the ATM row above. Say spot is 23,635 and the ATM strike is 23,650. The 23,650 call is 15 points OTM, so its intrinsic value is zero and <em>the entire premium is time value</em>. The 23,650 put is 15 points ITM: intrinsic value 15, and whatever the put trades above 15 is time value. You will find the call and put time values are nearly identical — they must be, or an arbitrage exists (that identity is <strong>put–call parity</strong>, and it is why the terminal's NET column, which measures the gap, hovers near zero).</p>
<aside class="tip"><b>The ₹5 option trap, explained in one line</b><p>A 23,900 call at ₹5 with two days left has zero intrinsic value and ₹5 of time value that will be ₹0 on Tuesday afternoon unless NIFTY rallies 265 points. It is not “cheap”. It is a lottery ticket priced by professionals who know the odds. Sometimes it pays 20×. Usually — SEBI's 93% — it pays 0×.</p></aside>
<h2>Exercise, assignment and squaring off</h2>
<p>In practice you almost never <em>exercise</em> an option in India — you <strong>square off</strong>: sell what you bought, or buy back what you sold, before expiry, and pocket the difference in premium. Exercise only happens automatically at expiry for ITM options. For index options that means a cash credit or debit. For stock options it means physical delivery, with its own traps (Chapter 9).</p>
<h2>Your first mental model</h2>
<p>Think of an option premium as <em>rent</em> on exposure. A buyer rents upside (or downside) for a period and pays rent up front; time decay is the rent being consumed. A writer is the landlord: collects rent, carries the building's risk. Neither is right or wrong — but you should always know which one you are, and what rent is being charged today. The next chapter teaches you to read that off the chain.</p>
"""},

{"slug": "reading-the-chain", "level": "foundation", "title": "Reading the option chain: LTP, OI, IV, PCR and what the market is telling you",
 "summary": "Every column of an option chain explained, how to find support and resistance from open interest, what the put-call ratio does and doesn't mean, and the live NIFTY chain to practise on.",
 "body": """
<h2>The chain is a map of expectations</h2>
<p>An option chain lists, for one underlying and one expiry, every strike with its call on the left and put on the right. Beginners see a wall of numbers; professionals see where the market thinks price will and won't go, how much fear is priced in, and where the big positions sit. Here is the live NIFTY chain around the money, with the columns Finostat computes for you:</p>
""" + _ex("LIVE", "NIFTY CHAIN · ATM ± 3", '<div data-live="chain"></div>') + """
<h2>The columns</h2>
<table><thead><tr><th>Column</th><th>What it is</th><th>How to read it</th></tr></thead><tbody>
<tr><td>LTP</td><td>Last traded price of that option.</td><td>The premium, per share. Multiply by lot for the rupee cost.</td></tr>
<tr><td>IV</td><td>Implied volatility: the annualised volatility the premium implies (Chapter 8).</td><td>Higher = market expects bigger moves = options are expensive. Compare across strikes and against India VIX.</td></tr>
<tr><td>Δ (delta)</td><td>How much the premium moves per 1-point move in the underlying (Chapter 7).</td><td>Also a rough probability of finishing ITM: a 0.25-delta call is priced as a ~25% shot.</td></tr>
<tr><td>OI</td><td>Open interest: contracts currently outstanding at that strike.</td><td>Big call OI above spot = a ceiling writers are defending. Big put OI below = a floor.</td></tr>
<tr><td>Volume</td><td>Contracts traded today.</td><td>Where the action is. High volume with rising OI = new positions; high volume with falling OI = unwinding.</td></tr>
<tr><td>Change in OI</td><td>Today's change.</td><td>Fresh call writing at a strike after a rally = resistance being built in real time.</td></tr></tbody></table>
<h2>Support and resistance from open interest</h2>
<p>Option writers are, on aggregate, the better-capitalised side. When a strike has a very large <em>call</em> OI, a lot of money is betting NIFTY will stay <em>below</em> it by expiry, and those writers will hedge and defend as price approaches. So the strike with the highest call OI above spot acts as <strong>resistance</strong>; the highest put OI below spot acts as <strong>support</strong>. This is not magic — it is where the most losses would occur if price broke through, so it is where the most effort goes into stopping it.</p>
<p>The corollary is <strong>max pain</strong>: the strike at which the total value of all open options is lowest at expiry — the price that hurts option <em>buyers</em> the most. Expiries have a documented tendency to drift toward it in the final hours. Treat it as a mild gravitational pull, not a target.</p>
<aside class="tip"><b>Reading a “wall”</b><p>If NIFTY is at 23,650 and the 24,000 call carries three times the OI of any nearby strike, the market's working assumption is that 24,000 holds this week. A strategy that sells the 24,000 call (an iron condor's upper wing, say) is aligned with that assumption; buying the 24,000 call is a bet the crowd is wrong. Both are fine trades — but know which one you are making.</p></aside>
<h2>The put-call ratio (PCR)</h2>
<p>PCR = total put OI ÷ total call OI. Above 1, more puts are open than calls — usually read as a <em>hedged</em>, somewhat fearful market; below 0.7, complacency. Its use is <strong>contrarian at extremes</strong>: a very high PCR often precedes a bounce (everyone is already hedged), a very low one precedes a dip. In the middle of its range it tells you almost nothing. Beginners quote it constantly; desks glance at it once a day.</p>
<h2>Implied volatility across strikes</h2>
<p>Look at the IV column top to bottom. It is not flat. Out-of-the-money puts (below spot) almost always carry higher IV than out-of-the-money calls: the market pays more for crash protection than for rally participation. That tilt is the <strong>skew</strong>, and its shape across all strikes is the <strong>smile</strong>. Chapter 8 goes deep; for now, just notice it in the live numbers.</p>
""" + _ex("LIVE", "IV BY STRIKE · THE SMILE", '<div data-live="smile"></div>') + """
<h2>A reading routine</h2>
<ol>
<li>Find the ATM strike. Note the straddle (ATM call + ATM put): that is the market's expected move to expiry in points (Chapter 6).</li>
<li>Find the highest call OI above and highest put OI below spot: the expected range's edges.</li>
<li>Compare ATM IV to India VIX and to last week: are options cheap or rich today?</li>
<li>Check the skew: is the market paying up for downside? That tells you what it fears.</li>
<li>Only now form a view — and pick a strategy that is <em>priced</em> attractively for that view, not just one that “feels” right.</li>
</ol>
<p>Next: the maths behind those premiums, kept honest and intuitive — <a href="/finch/option-pricing">option pricing and the expected move</a>.</p>
"""},

{"slug": "option-pricing", "level": "core", "title": "Option pricing: what drives a premium, and the expected move hidden in the straddle",
 "summary": "The five inputs to an option's price, Black-Scholes in plain language, why time decay accelerates, and how to read the market's forecast off the live ATM straddle.",
 "body": """
<h2>Five inputs, one price</h2>
<p>Every option pricing model — including the one Finostat uses to compute the IV and greeks you see on the chain — starts from the same five inputs:</p>
<table><thead><tr><th>Input</th><th>Call premium rises when it…</th><th>Put premium rises when it…</th></tr></thead><tbody>
<tr><td>Spot price</td><td>rises</td><td>falls</td></tr><tr><td>Strike</td><td>is lower</td><td>is higher</td></tr>
<tr><td>Time to expiry</td><td>is longer</td><td>is longer</td></tr><tr><td>Volatility</td><td>rises</td><td>rises</td></tr>
<tr><td>Interest rate</td><td>rises (slightly)</td><td>falls (slightly)</td></tr></tbody></table>
<p>Four of the five you can look up. The fifth — <strong>volatility</strong> — is the only genuine unknown, which is why options are really <em>volatility</em> instruments dressed up as directional ones. Chapter 8 is entirely about it.</p>
<h2>Black-Scholes without the calculus</h2>
<p>The Black-Scholes formula answers one question: <em>if the underlying wanders randomly with a given volatility, what is the average payout of this option at expiry, discounted to today?</em> The intuition is a bell curve of possible expiry prices centred near spot, whose width is set by volatility × √time. A call's value is the average of (expiry price − strike) over the part of the curve above the strike. Move the strike up and less of the curve counts; widen the curve (more vol, more time) and more of it counts.</p>
<p>Two consequences that matter for trading:</p>
<ul>
<li><strong>Time value grows with the square root of time, not linearly.</strong> A 4-week option is worth about twice a 1-week option, not four times. Equivalently, decay is slow far from expiry and violent in the final days.</li>
<li><strong>ATM options are pure volatility.</strong> Their value is almost entirely time value, and it is almost exactly proportional to volatility. That makes the ATM straddle a direct readout of the market's expected move.</li>
</ul>
<h2>The expected move: reading the market's forecast</h2>
<p>Add the ATM call and ATM put premiums together and you get the <strong>straddle</strong>. A very good rule of thumb: <em>the straddle price is the market's one-standard-deviation expected move to expiry</em>. If it costs 240 points, the market is pricing NIFTY to finish within ±240 of spot about two-thirds of the time. Here it is, live:</p>
""" + _ex("LIVE", "ATM STRADDLE → IMPLIED MOVE", '<div data-live="straddle"></div>') + """
<p>This number is the single most useful thing on the chain. It tells you whether a strategy's breakevens sit inside or outside what the market already expects. Selling a strangle with breakevens narrower than the implied move is betting the market is overestimating volatility; buying a straddle is betting it is underestimating. Neither is automatically right — the market's forecast is decent but not perfect — but you should always know which side of it you are on.</p>
<h2>Why theta accelerates</h2>
<p>Because time value scales with √time, the decay per day (theta) scales with 1/√time. With 16 days left an ATM option loses about 1/32 of its value per day; with 4 days left, about 1/8; on the last day, almost all of it. This is the mechanism behind the “cheap options before expiry” trap in Chapter 1: the buyer is paying for a day whose time value is evaporating at the fastest rate of the option's life.</p>
""" + _ex("LIVE", "TODAY'S ATM GREEKS", '<div data-live="greeks"></div>') + """
<h2>A complete worked example</h2>
<p>Say NIFTY is 23,635, the 23,650 call trades at ₹150 with 7 days to go, and you buy one lot (65). You pay ₹9,750. Three scenarios at expiry:</p>
<table><thead><tr><th>NIFTY at expiry</th><th>Call worth</th><th>P&amp;L per share</th><th>P&amp;L per lot</th></tr></thead><tbody>
<tr><td>23,500 (down)</td><td>0</td><td>−150</td><td>−₹9,750</td></tr>
<tr><td>23,800 (up 165)</td><td>150</td><td>0</td><td>₹0 — right on direction, still flat</td></tr>
<tr><td>24,000 (up 365)</td><td>350</td><td>+200</td><td>+₹13,000</td></tr></tbody></table>
<p>Read the middle row twice. NIFTY rose 165 points — 0.7%, a decent week — and you made nothing, because you paid 150 for the right to participate. That is what “right on direction, wrong on price” means, and it is the most common way beginners lose. The cure is not to stop buying options; it is to buy them when the premium is low relative to the move you expect, which requires understanding volatility. That is Chapter 8, after the Greeks.</p>
"""},
]
