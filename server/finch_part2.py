"""Finch chapters 7-12 and the glossary."""

def _ex(k, s, inner, r="live"):
    return f'<div class="example"><div class="hd"><span class="k">{k}</span><span class="s">{s}</span><span class="r">{r}</span></div><div class="bd">{inner}</div></div>'

CHAPTERS = [
{"slug": "the-greeks", "level": "core", "title": "The Greeks: delta, gamma, theta and vega, with live numbers",
 "summary": "What each Greek measures, how to use it before you trade rather than after, and the live ATM greeks so you can see the sizes on today's market.",
 "body": """
<h2>Why Greeks exist</h2>
<p>An option's price depends on five things at once, so “will this option make money?” has no single answer. The Greeks break the question into parts: <em>how much do I make or lose if only the underlying moves? if only a day passes? if only volatility changes?</em> Each Greek is a sensitivity — a rate of change of the premium with respect to one input, everything else held still. Finostat computes them from the live premiums; here are today's, at the money:</p>
""" + _ex("LIVE", "ATM GREEKS · NIFTY", '<div data-live="greeks"></div>') + """
<h2>Delta: direction</h2>
<p><strong>Delta</strong> is the change in premium for a 1-point change in the underlying. Calls have delta between 0 and 1, puts between −1 and 0. An ATM option is about ±0.5; deep ITM approaches ±1 (it moves like the underlying); far OTM approaches 0 (it barely reacts). Three practical uses:</p>
<ul>
<li><strong>Equivalent exposure.</strong> A 0.5-delta call on one lot behaves like being long half a lot of futures. Ten lots of 0.10-delta calls are one lot of exposure — with the same time decay as ten lots.</li>
<li><strong>Rough probability.</strong> Delta approximates the chance the option expires ITM. A 0.20-delta call is priced as a one-in-five shot. Selling it collects premium for a four-in-five chance of keeping it — and a one-in-five chance of a large loss.</li>
<li><strong>Hedging.</strong> Market makers who sell you a 0.5-delta call buy 0.5 lots of futures to be flat. As price moves their delta changes and they rebalance — which is where gamma comes in.</li>
</ul>
<h2>Gamma: how fast delta changes</h2>
<p><strong>Gamma</strong> is the change in delta per 1-point move. It is largest at the money and near expiry, tiny far from either. Long options have positive gamma: as the underlying moves your way, your delta grows and you make money faster; as it moves against you, delta shrinks and you lose more slowly. That convexity is what you are paying for. Short options have negative gamma: your losses accelerate and your gains decelerate. On expiry day ATM gamma explodes — a 100-point move can take a 0.5-delta option to 0.9 or 0.1 in minutes. Writers who are short that gamma call it “gamma risk”; it is why expiry-day short straddles look free for weeks and then aren't.</p>
<h2>Theta: time</h2>
<p><strong>Theta</strong> is the premium lost per calendar day, all else equal. It is negative for long options and positive for short ones — the writer's income. It is highest at the money, and it accelerates toward expiry (Chapter 6). Look at the live theta above and multiply by the lot: that is the rupee cost of holding one ATM contract overnight while nothing happens. Weekends count: an option bought Friday afternoon is worth less on Monday morning with the index unchanged.</p>
<aside class="tip"><b>Theta and gamma are the same trade, seen from two sides</b><p>You cannot have positive gamma without paying theta, or collect theta without being short gamma. Every options position is a choice of <em>which one you would rather be paid for</em>: the buyer is paid for movement and pays for time; the writer is paid for time and pays for movement. A strategy is “good” when the market is charging less for the side you want than that side turns out to be worth.</p></aside>
<h2>Vega: volatility</h2>
<p><strong>Vega</strong> is the change in premium for a 1-percentage-point change in implied volatility. It is largest at the money and for longer-dated options. Long options are long vega — they gain when the market gets more nervous, even with no move in price. This is why buying options before a big event and selling right after can lose money even when the event goes your way: IV collapses after the uncertainty resolves (“vol crush”), and vega takes back what delta gave. Chapter 8 covers it.</p>
<h2>Rho, briefly</h2>
<p><strong>Rho</strong> is sensitivity to interest rates. For weekly and monthly options it is negligible; ignore it until you trade long-dated contracts.</p>
<h2>Using Greeks before the trade, not after</h2>
<p>Every strategy in the builder shows the position's net Greeks. Before entering, ask: what is my delta (am I secretly directional?), what is my theta (what does a flat day cost or pay?), what is my vega (what happens if fear rises or falls?), and where does gamma bite? A short iron condor with theta of +₹150/day and vega of −₹200/point is a bet that time passes quietly. A long straddle with theta −₹400/day is a bet that something happens within a few days. Reading those numbers is the difference between a strategy and a hope.</p>
<p><a class="cta ghost" href="/dashboard#p-builder">See the net Greeks of any strategy in the builder →</a></p>
"""},

{"slug": "implied-volatility", "level": "core", "title": "Implied volatility: the price of fear, India VIX, skew and vol crush",
 "summary": "What IV actually is, how it differs from realised volatility, how to tell if options are cheap or expensive today, and why buying before events is so often a losing trade.",
 "body": """
<h2>What implied volatility is</h2>
<p>Take a live premium, plug it into the pricing model, and solve backwards for the one input you cannot observe. The result is <strong>implied volatility</strong>: the annualised standard deviation of returns the market is charging for. An IV of 12% on NIFTY says the market is pricing moves consistent with the index wandering ±12% over a year — which, scaled by √time, is about ±0.75% a day or ±1.7% a week. IV is not a forecast of direction. It is the <em>price of movement</em>.</p>
""" + _ex("LIVE", "IV BY STRIKE · TODAY", '<div data-live="smile"></div>') + """
<h2>Implied versus realised</h2>
<p><strong>Realised (historical) volatility</strong> is what the underlying actually did — measured from past returns. IV is what options say it will do. The gap between them is the whole option-writing business: on average, across years and markets, IV runs a little above subsequent realised volatility. Writers are paid a premium for absorbing the risk that it won't. When realised turns out higher than implied — a crash, a shock result — writers lose, sometimes catastrophically; that is the tail they were paid for.</p>
<p>Practical version: if NIFTY has been moving ±80 points a day and the straddle prices ±180 for the week, options are rich relative to recent behaviour. If it has been moving ±200 a day and the straddle prices ±180, they are cheap. Neither guarantees anything, but it tells you which side has the odds.</p>
<h2>India VIX</h2>
<p><strong>India VIX</strong> is NSE's index of NIFTY 30-day implied volatility, computed from the option chain. It is the quickest read on whether options are expensive today. Typical ranges: low teens in calm markets, 20s in nervous ones, 30+ in crises. Watch it on the live tape above every chapter. Two rules of thumb: a rising VIX makes every long option position worth more and every short one worth less, regardless of direction; and VIX tends to spike fast and fall slowly, so the best time to <em>sell</em> premium is right after a spike, the best time to <em>buy</em> is deep in a calm.</p>
<h2>IV percentile and rank</h2>
<p>A 15% IV is high for NIFTY and absurdly low for a small-cap stock. To compare, use <strong>IV percentile</strong>: the fraction of the past year's days on which IV was lower than today's. At the 90th percentile, options are expensive by the underlying's own standards — a writer's environment. At the 10th, cheap — a buyer's. This is the single best filter for “what kind of strategy should I even be considering today?”</p>
<h2>Skew and the smile</h2>
<p>If the pricing model were literally true, every strike would show the same IV. It doesn't, because markets know that crashes are faster and bigger than rallies. Out-of-the-money puts therefore trade at higher IV than equidistant calls: the <strong>skew</strong>. Plotted across strikes the IVs form a tilted <strong>smile</strong> — the live block above. What it tells you:</p>
<ul>
<li>A steep skew means crash protection is expensive: put buyers are paying up. Strategies that <em>sell</em> downside puts (bull put spreads, put ratio spreads) are collecting that premium.</li>
<li>A flattening skew after a fall often marks exhaustion: the hedgers have hedged.</li>
<li>On stocks before results, the smile bulges symmetrically — pure event uncertainty.</li>
</ul>
<h2>Vol crush: the event trap</h2>
<p>Before a budget, an RBI decision, a company's results, IV rises: uncertainty is high and everyone wants optionality. The moment the news is out, uncertainty collapses and IV with it — often by a third in minutes. An option bought the day before at 40% IV is repriced at 25% after, and can lose money <em>even if the news moved the stock in your favour</em>: delta gave, vega took more. This is the most reliably expensive lesson in retail options. If you want to trade an event, either buy well before IV builds, or structure the trade so vega is neutral (a spread), or be the seller of the crush — with defined risk, because “the move was bigger than implied” is the other way events resolve.</p>
<aside class="warn"><b>Sanity check before any trade</b><p>Ask: is IV high or low for this underlying right now (percentile)? Is there an event inside my expiry? Which way does vega hit me if I'm wrong about vol? If you cannot answer all three, you are not ready to put the trade on. That is not a rule for beginners; desks do it every single time.</p></aside>
<p>Next: the mechanics that turn a paper P&amp;L into real money — <a href="/finch/expiry-and-settlement">expiry and settlement</a>.</p>
"""},

{"slug": "expiry-and-settlement", "level": "core", "title": "Expiry and settlement: cash vs physical, the STT trap, and expiry-day behaviour",
 "summary": "What happens to your position when the contract dies, why in-the-money stock options can cost you lakhs in delivery, the STT rule that ambushes small profits, and how the last hours actually trade.",
 "body": """
<h2>The calendar</h2>
<p>Index options in India currently expire <strong>weekly</strong> — one weekday per exchange (NSE's NIFTY contracts on Tuesdays, BSE's SENSEX on Thursdays at the time of writing; the rules have changed more than once, so trust the dates on the chain, not this sentence). Stock options expire <strong>monthly</strong> on the last Tuesday of the month. On expiry day trading stops at 15:30 IST and the contract settles against the underlying's closing value, computed from the last half hour's weighted average for index and stocks.</p>
""" + _ex("LIVE", "THE NEAREST NIFTY EXPIRY", '<div data-live="lot"></div>', "live") + """
<h2>Cash settlement: index options</h2>
<p>Hold an ITM index option through expiry and you receive its intrinsic value in cash: a 23,600 call with NIFTY settling at 23,700 pays ₹100 × 65 = ₹6,500 automatically. An OTM option simply expires worthless; nothing further happens. Simple — with one tax wrinkle below.</p>
<h2>Physical settlement: stock options</h2>
<p>Since October 2019 every stock derivative on NSE is <strong>physically settled</strong>. Hold an ITM stock option through expiry and it becomes a delivery: a long call means you <em>buy</em> the full lot of shares at the strike; a long put means you <em>sell</em> them (so you must own them, or be short-delivered with penalties); a short call means you must <em>deliver</em> the shares; a short put means you must <em>buy</em> them. A RELIANCE 1,300 call on a 500-share lot that finishes ITM is a ₹6.5 lakh purchase, and your broker will demand the money — typically by raising margin to the full value in the last few sessions before expiry.</p>
<aside class="warn"><b>The rule that prevents this</b><p>Never carry a stock option that could finish in the money into the last expiry session unless you have the cash or the shares and actually want the delivery. Square off on the day before, or earlier. Most brokers now force-close such positions on expiry afternoon anyway — at whatever price is available, which is rarely a good one.</p></aside>
<h2>The STT trap on exercised options</h2>
<p>Securities Transaction Tax on options is charged on the <em>premium</em> when you sell. But when an ITM option is <em>exercised</em> at expiry — which is what happens if you just hold it — STT is charged on the option's full <strong>intrinsic value</strong> instead, at a much higher effective amount. A call that is ₹50 in the money on which you made a ₹5 profit can see that profit entirely consumed by STT on the ₹50 of intrinsic value. Rule: if an option is ITM near expiry, <em>sell it in the market</em> rather than letting it exercise. Also note that since October 2024 STT on option sales is 0.1% of premium, not the old 0.0625%: trading costs on frequent option selling are meaningfully higher than a few years ago.</p>
<h2>How expiry day actually trades</h2>
<ul>
<li><strong>Time value goes to zero by 15:30.</strong> An ATM straddle that cost ₹120 at 9:15 might be ₹40 by noon with the index unchanged. Long-option buyers watching their premium melt by the minute are the theta that writers are collecting.</li>
<li><strong>Gamma is extreme.</strong> A 50-point move swings ATM deltas from 0.3 to 0.7. Writers hedging that gamma can create sharp, self-feeding moves in the last hour — the “expiry-day whipsaw”.</li>
<li><strong>Max pain gravity.</strong> Price often settles near the strike that leaves the most option value worthless. Not reliable enough to trade alone, common enough to respect.</li>
<li><strong>Liquidity drains at far strikes.</strong> Spreads widen; exiting a position at a fair price gets harder. Don't be forced to trade at 15:20.</li>
</ul>
<h2>Rollover</h2>
<p>To keep a view alive past expiry you <strong>roll</strong>: close the expiring contract and open the next one. For futures this crystallises the basis (Chapter 3) — you pay the new month's carry. For options you re-pay time value. Rolling is a new trade, not a continuation; re-evaluate it as one.</p>
<p>Next: strategies — built and priced on the live chain — in <a href="/finch/strategies">Chapter 10</a>.</p>
"""},

{"slug": "strategies", "level": "applied", "title": "Strategies for beginners, priced live: spreads, straddles, condors and butterflies",
 "summary": "Eight structures you will actually use, each with the view it expresses, its risk shape, and its real cost on today's NIFTY chain — with one click to open it in the builder.",
 "body": """
<h2>How to choose a strategy</h2>
<p>A strategy is a view turned into a payoff. Before picking one, write down your view in four parts: <strong>direction</strong> (up, down, sideways, don't know), <strong>magnitude</strong> (big, small), <strong>timing</strong> (this week, this month), and <strong>volatility</strong> (is IV high or low right now, Chapter 8). Every structure below is the natural fit for some combination. Each one is priced live on today's NIFTY chain; the numbers are per lot.</p>
<h2>1. Bull call spread — moderately bullish, defined risk</h2>
<p>Buy a call, sell a higher call. The short call pays for part of the long one, capping your gain at the width of the spread but cutting the cost and the theta bleed. Use when you expect a moderate rise and IV is not cheap. Max loss = debit paid; max profit = width − debit.</p>
""" + _ex("LIVE", "BULL CALL SPREAD · NIFTY", '<div data-live="strategy" data-preset="bull-call-spread"></div>') + """
<h2>2. Bear put spread — moderately bearish, defined risk</h2>
<p>The mirror: buy a put, sell a lower put. Expresses a measured fall without paying full price for downside protection (which, given skew, is usually expensive).</p>
""" + _ex("LIVE", "BEAR PUT SPREAD · NIFTY", '<div data-live="strategy" data-preset="bear-put-spread"></div>') + """
<h2>3. Long straddle — big move, either way</h2>
<p>Buy the ATM call and put. You profit if NIFTY closes beyond either breakeven — spot ± straddle cost — by expiry. It is the purest bet that the market is <em>under</em>pricing movement. It loses to theta every quiet day, and to vol crush after events. Use when IV percentile is low and you expect a catalyst the market hasn't priced.</p>
""" + _ex("LIVE", "LONG STRADDLE · NIFTY", '<div data-live="strategy" data-preset="long-straddle"></div>') + """
<h2>4. Short strangle — sideways, collecting premium (undefined risk)</h2>
<p>Sell an OTM call and an OTM put. You keep both premiums if NIFTY expires between the strikes; beyond either, losses grow without limit. The most popular retail “income” strategy and the one that ends the most accounts, because a 3% gap does not care about your monthly average. If you trade it, size it as if that gap will happen — Chapter 11.</p>
""" + _ex("LIVE", "SHORT STRANGLE · NIFTY", '<div data-live="strategy" data-preset="short-strangle"></div>') + """
<h2>5. Iron condor — sideways, defined risk</h2>
<p>A short strangle with wings bought further out. The wings cost part of the credit but cap the loss at width − credit, and slash the margin. This is how to express “range-bound this week” without the tail. Compare its max loss to the strangle above: that difference is the price of sleeping.</p>
""" + _ex("LIVE", "IRON CONDOR · NIFTY", '<div data-live="strategy" data-preset="iron-condor"></div>') + """
<h2>6. Iron fly — pinned to a strike, defined risk</h2>
<p>Sell the ATM straddle, buy wings. Highest credit of the range strategies, narrowest profit zone: you are betting NIFTY expires very close to the strike. Best on expiry day itself when time value is high and there are only hours of movement left.</p>
""" + _ex("LIVE", "IRON FLY · NIFTY", '<div data-live="strategy" data-preset="iron-fly"></div>') + """
<h2>7. Long butterfly — cheap bet on a pin</h2>
<p>Buy one call below, sell two at the target strike, buy one above. Tiny debit, large payoff if price expires exactly at the middle strike, nothing if it drifts far. Think of it as a lottery ticket with better odds than a naked OTM option because you are selling time value to fund it. The BFLY column on the Finostat sheet is this structure's live cost at every strike.</p>
""" + _ex("LIVE", "CALL BUTTERFLY · NIFTY", '<div data-live="strategy" data-preset="butterfly"></div>') + """
<h2>8. Ratio spread — slow drift, with a tail</h2>
<p>Buy one call, sell two further out. Often a small net credit; maximum profit if price drifts up to the short strike; unlimited loss above it because one call is naked. Professional structure for “up a little, not a lot” when skew makes the higher strike rich. Not for the first month.</p>
""" + _ex("LIVE", "CALL RATIO 1×2 · NIFTY", '<div data-live="strategy" data-preset="ratio-spread"></div>') + """
<h2>Matching view to structure</h2>
<table><thead><tr><th>Your view</th><th>IV today</th><th>Structure</th></tr></thead><tbody>
<tr><td>Up, moderately</td><td>high</td><td>Bull call spread (or bull put spread)</td></tr>
<tr><td>Up, a lot, soon</td><td>low</td><td>Long call, or long straddle if unsure of direction</td></tr>
<tr><td>Down, moderately</td><td>any</td><td>Bear put spread</td></tr>
<tr><td>Sideways</td><td>high</td><td>Iron condor; iron fly on expiry day</td></tr>
<tr><td>Big move, unsure which way</td><td>low</td><td>Long straddle / strangle</td></tr>
<tr><td>Pin at a level</td><td>any</td><td>Butterfly</td></tr></tbody></table>
<p>Every one of these can be opened, edited leg by leg, and re-priced live in the terminal's builder — including on any F&amp;O stock, not just the index.</p>
<p><a class="cta" href="/dashboard#p-builder">Open the strategy builder →</a></p>
"""},

{"slug": "risk-and-position-sizing", "level": "applied", "title": "Risk and position sizing: the part that decides whether you're still here in a year",
 "summary": "Worst-case sizing, why margin is the wrong yardstick, stops that work for options and ones that don't, liquidity, events, and a pre-trade checklist.",
 "body": """
<h2>Survival first</h2>
<p>Trading edge compounds only if you survive to use it. A strategy with a 70% win rate and a 20% chance of ruin per year is a strategy that ruins you within five years with near certainty. Everything in this chapter is about pushing that ruin probability toward zero while keeping the edge intact.</p>
<h2>Size by worst plausible loss, not by margin</h2>
<p>Margin (Chapter 3) is the exchange's estimate of a bad day or two. It is not your loss limit. For every position, compute the loss at a move the market has actually produced — NIFTY has gapped 4–5% overnight several times in the last decade; individual stocks 20% on results. For defined-risk structures that is simply the max loss the builder shows. For undefined ones (short strangles, naked options, futures) it is the loss at a 4–5% adverse gap, which is often <em>five to ten times</em> the margin.</p>
<aside class="tip"><b>The rule</b><p>Risk no more than <strong>1–2% of trading capital</strong> per trade at the worst plausible outcome, and no more than about 5–6% across all open positions. With ₹5 lakh, a trade whose worst case is ₹25,000 is at the edge. An iron condor with a max loss of ₹2,400 per lot lets you trade ten lots inside that rule; a short strangle with a plausible ₹60,000 gap loss per lot means <em>zero</em> lots on that capital, whatever the margin says.</p></aside>
<p>Put numbers on it with today's chain. Below is a live iron condor: its max loss is fixed and known before entry, so the 2% rule turns directly into a lot count. The short strangle in Chapter 10 has the same strikes without the wings — same credit give or take, and a max loss the model calls <em>unlimited</em>; there, the number you size by is what a 4–5% gap would do.</p>
""" + _ex("LIVE", "DEFINED RISK · IRON CONDOR", '<div data-live="strategy" data-preset="iron-condor"></div>') + """
<h2>Stops that work, and ones that don't</h2>
<ul>
<li><strong>Price stops on the underlying</strong> work: “if NIFTY trades 23,400 I'm out.” They express your thesis being wrong.</li>
<li><strong>Premium-based stops on short options</strong> work if wide: “buy back if the option doubles.” Rule of thumb for premium sellers: exit at 2× the credit, take profit at 50% of it. The asymmetry is deliberate.</li>
<li><strong>Tight premium stops on long options</strong> do not work: theta and bid-ask noise trigger them constantly. A long option's stop is its size — buy only what you can afford to lose entirely.</li>
<li><strong>No stop protects against a gap.</strong> Overnight risk is sized, not stopped. Defined-risk structures are the only real overnight protection.</li>
</ul>
<h2>Liquidity and slippage</h2>
<p>NIFTY and BANKNIFTY weeklies are the most liquid options on earth; most stock options are not. Look at the bid-ask spread before you trade: a ₹2 spread on a ₹10 option is 20% round-trip cost before anything happens. Rules: trade strikes with visible OI and volume, use limit orders, avoid the first and last ten minutes of the day for anything but the index, and never let a position grow to a size you could not exit in one order.</p>
<h2>Events</h2>
<p>Know every scheduled event inside your expiry: RBI policy, the Union Budget, US Fed decisions, index-heavyweight results, and for stocks their own results dates. Either your position is designed for the event (a vega-neutral spread, a small defined-risk straddle) or it should not be open through it. Unscheduled events — geopolitical shocks — are what the 1–2% rule is for.</p>
<h2>A pre-trade checklist</h2>
<ol>
<li>What is my view in four parts (direction, magnitude, timing, vol)? If I can't state it, no trade.</li>
<li>Is IV high or low for this underlying (percentile)? Does the structure I've chosen want that?</li>
<li>Where are the breakevens versus the implied move (the live straddle)? Am I inside or outside what the market expects?</li>
<li>What is the worst plausible loss in rupees, and is it under 2% of capital?</li>
<li>What is my exit for right, for wrong, and for “nothing happened”?</li>
<li>Any events inside the expiry? Is this a stock option that could be physically settled?</li>
<li>Can I exit this size in one order at a fair price?</li>
</ol>
<p>Seven questions, sixty seconds. They would have prevented most of the losses in SEBI's 93%.</p>
<p>Finally: <a href="/finch/mistakes-and-glossary">the mistakes everyone makes once, and the glossary</a>.</p>
"""},

{"slug": "mistakes-and-glossary", "level": "applied", "title": "The mistakes everyone makes once, and a glossary",
 "summary": "Twelve beginner errors with the reason each one costs money, and a working glossary of every term used in Finch.",
 "body": """
<h2>Twelve mistakes, and why each costs money</h2>
<ol>
<li><strong>Buying cheap OTM options near expiry.</strong> You are buying the fastest-decaying asset that exists at the moment it decays fastest. It works often enough to feel like skill.</li>
<li><strong>Judging a trade by whether direction was right.</strong> Options have three other axes — time, vol, price paid. Chapter 6's middle row: right on direction, flat on P&amp;L.</li>
<li><strong>Selling naked options for “monthly income”.</strong> The income is real; so is the one gap that returns eighteen months of it. Define the risk or size for the gap.</li>
<li><strong>Buying options into an event.</strong> Vol crush. If the move isn't bigger than implied, vega takes back what delta gave.</li>
<li><strong>Averaging down a losing long option.</strong> Adding theta bleed to theta bleed. Long options are sized once, at entry.</li>
<li><strong>Holding ITM stock options into expiry.</strong> Physical delivery and STT on intrinsic value. Square off the day before.</li>
<li><strong>Trading on margin capacity instead of loss capacity.</strong> Margin is a deposit, not a limit. A 4% gap doesn't check your margin first.</li>
<li><strong>Ignoring the bid-ask spread on illiquid strikes.</strong> A 20% spread is a 20% loss on entry. The chain's OI column is a liquidity map; use it.</li>
<li><strong>Revenge trading after a loss.</strong> The second trade is sized by anger, not by the checklist. Close the terminal.</li>
<li><strong>Not knowing your net Greeks.</strong> “Neutral” condors with 0.3 delta are directional. The builder shows the net; read it.</li>
<li><strong>Confusing a high win rate with an edge.</strong> A strategy that wins 90% of the time with 1:15 payoff loses money. Expectancy = win% × avg win − loss% × avg loss.</li>
<li><strong>Trading every day.</strong> Most days the market is priced fairly and there is nothing to do. Edges are occasional; the checklist exists to say no.</li>
</ol>
<h2>Where to go from here</h2>
<p>Read the chain every morning for a month before trading — write down the straddle, the OI walls, the IV, and what you expect; then see what happened. Paper-trade the builder's structures with real prices and honest sizing. When you do trade, start with one lot of a defined-risk spread on the index, and keep a journal with the seven checklist answers for every trade. The traders who last are not the ones with the best calls; they are the ones who can show you a year of journal entries.</p>
""" + _ex("LIVE", "THE MARKET YOU'LL PRACTISE ON", '<div data-live="spot"></div>') + """
<h2>Glossary</h2>
<dl class="glossary">
<dt>ATM / ITM / OTM</dt><dd>At, in, out of the money: strike near, favourably past, or unfavourably away from spot.</dd>
<dt>Assignment</dt><dd>The writer being required to fulfil the option (cash for index, delivery for stocks) at expiry.</dd>
<dt>Basis</dt><dd>Futures price minus spot. Converges to zero at expiry.</dd>
<dt>Breakeven</dt><dd>The underlying price at expiry where a position's P&amp;L is exactly zero.</dd>
<dt>Cost of carry</dt><dd>Interest saved (less dividends forgone) by holding a future instead of the underlying; sets the fair basis.</dd>
<dt>Delta / Gamma / Theta / Vega / Rho</dt><dd>Sensitivities of premium to spot, to spot again, to time, to implied volatility, to interest rates.</dd>
<dt>Expiry</dt><dd>The date a contract settles and ceases to exist.</dd>
<dt>Extrinsic (time) value</dt><dd>Premium beyond intrinsic value; decays to zero at expiry.</dd>
<dt>Implied volatility (IV)</dt><dd>The annualised volatility a premium implies under the pricing model; the price of movement.</dd>
<dt>India VIX</dt><dd>NSE's index of NIFTY 30-day implied volatility.</dd>
<dt>Intrinsic value</dt><dd>What an option would pay if exercised now; never negative.</dd>
<dt>IV percentile</dt><dd>Share of the past year's days with IV below today's; “cheap or expensive by its own standards”.</dd>
<dt>Lot</dt><dd>The exchange-fixed number of underlying units per contract.</dd>
<dt>Margin (SPAN + exposure)</dt><dd>Collateral held by the exchange against futures and short options.</dd>
<dt>Mark-to-market</dt><dd>Daily cash settlement of futures gains and losses.</dd>
<dt>Max pain</dt><dd>The expiry price at which the total value of open options is smallest.</dd>
<dt>Open interest (OI)</dt><dd>Contracts outstanding at a strike; a map of where positions and liquidity sit.</dd>
<dt>PCR</dt><dd>Put-call ratio of open interest; a contrarian sentiment gauge at extremes.</dd>
<dt>Physical settlement</dt><dd>Delivery of actual shares for ITM stock derivatives at expiry (since 2019).</dd>
<dt>Premium</dt><dd>The price of an option, per share.</dd>
<dt>Put–call parity</dt><dd>Call − put = spot − discounted strike, for the same strike and expiry; the reason call and put time values match.</dd>
<dt>Skew / smile</dt><dd>The pattern of IV across strikes: puts richer than calls (skew), wings richer than the middle (smile).</dd>
<dt>Square off</dt><dd>Closing a position by an opposite trade rather than holding to expiry.</dd>
<dt>Straddle / strangle</dt><dd>Call plus put at the same strike / at different strikes; the market's implied move when at the money.</dd>
<dt>STT</dt><dd>Securities Transaction Tax; on options, 0.1% of premium when sold, and on intrinsic value when exercised at expiry.</dd>
<dt>Vol crush</dt><dd>The collapse of implied volatility once an event's uncertainty resolves.</dd>
</dl>
<p><a class="cta" href="/dashboard">Open the terminal →</a> <a class="cta ghost" href="/finch">Back to all chapters</a></p>
"""},
]
