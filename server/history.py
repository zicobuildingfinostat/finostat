"""Historical replay and expiry-day backtests on Upstox's expired-contract archive.

Every past expiry (NIFTY and SENSEX weekly, BANKNIFTY/FINNIFTY/MIDCPNIFTY monthly, back to
October 2024) has 1-minute candles for every strike, plus 1-minute index candles. Replay
rebuilds the ATM±5 chain minute by minute for a chosen expiry day; the backtester enters a
structure at a chosen minute on each expiry day and exits at another, with the intraday
path for adverse excursion. Fetched candles are cached for good (they never change), so the
first run of a study is slow (one REST call per contract-day) and every later run is instant.
Jobs run on a thread and are polled; results are memoised per expiry so adding a new
expiry only fetches the new day.
"""
from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
from datetime import datetime, timedelta, timezone

import upstox_rest as ur

log = logging.getLogger("finostat.history")
IST = timezone(timedelta(hours=5, minutes=30))

STRATEGIES = {
    "short_straddle": ("Short straddle", "sell ATM CE + PE"),
    "long_straddle": ("Long straddle", "buy ATM CE + PE"),
    "short_strangle": ("Short strangle", "sell CE ATM+w, PE ATM−w"),
    "long_strangle": ("Long strangle", "buy CE ATM+w, PE ATM−w"),
    "iron_fly": ("Iron fly", "short straddle, long wings at ±w"),
    "iron_condor": ("Iron condor", "short strangle at ±w, long wings at ±2w"),
}


def legs_for(strategy: str, atm: int, step: int, wings: int) -> list[tuple[str, int, int]]:
    """(right, strike, side) with side +1 long / −1 short."""
    w = max(1, wings) * step
    if strategy == "short_straddle":
        return [("CE", atm, -1), ("PE", atm, -1)]
    if strategy == "long_straddle":
        return [("CE", atm, 1), ("PE", atm, 1)]
    if strategy == "short_strangle":
        return [("CE", atm + w, -1), ("PE", atm - w, -1)]
    if strategy == "long_strangle":
        return [("CE", atm + w, 1), ("PE", atm - w, 1)]
    if strategy == "iron_fly":
        return [("CE", atm, -1), ("PE", atm, -1), ("CE", atm + w, 1), ("PE", atm - w, 1)]
    if strategy == "iron_condor":
        return [("CE", atm + w, -1), ("PE", atm - w, -1), ("CE", atm + 2 * w, 1), ("PE", atm - 2 * w, 1)]
    raise ValueError("unknown strategy")


def _minute(ts_iso: str) -> str:
    return ts_iso[11:16]


def _series(candles: list[list]) -> dict[str, float]:
    """minute 'HH:MM' -> close."""
    return {_minute(c[0]): float(c[4]) for c in candles if c and c[0]}


def _at(series: dict[str, float], minute: str, minutes: list[str]) -> float | None:
    """Close at `minute`, else the last close before it (illiquid strikes skip minutes)."""
    if minute in series:
        return series[minute]
    prev = [m for m in minutes if m <= minute and m in series]
    return series[prev[-1]] if prev else None


class Job:
    def __init__(self, key: str):
        self.key, self.status, self.progress, self.error, self.result = key, "running", 0.0, None, None
        self.started = time.time()

    def view(self) -> dict:
        return {"status": self.status, "progress": round(self.progress, 3), "error": self.error, "result": self.result,
                "elapsed": round(time.time() - self.started, 1)}


class History:
    def __init__(self, client: ur.Client, store: ur.CandleStore):
        self.client, self.store = client, store
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    # -- archive access (cached) ------------------------------------------
    def days(self, u: str) -> list[str]:
        k = f"EXPIRIES|{u}"
        hit = self.store.meta_get(k, 12 * 3600)
        if hit is not None:
            return hit
        days = self.client.expired_expiries(u)
        self.store.meta_put(k, days)
        return days

    def contracts(self, u: str, day: str) -> dict:
        """{'lot': int, 'step': int, 'keys': {'CE:24500': expired_key, ...}}"""
        k = f"CONTRACTS|{u}|{day}"
        hit = self.store.meta_get(k, 365 * 86400)
        if hit is not None:
            return hit
        rows = self.client.expired_contracts(u, day)
        keys, lot, strikes = {}, 0, set()
        for r in rows:
            try:
                strike = int(round(float(r.get("strike_price", 0))))
            except (TypeError, ValueError):
                continue
            keys[f"{r.get('instrument_type')}:{strike}"] = r.get("instrument_key")
            lot = lot or int(r.get("lot_size") or 0)
            strikes.add(strike)
        ss = sorted(strikes)
        step = min((b - a for a, b in zip(ss, ss[1:]) if b > a), default=ur.STEP.get(u, 50))
        out = {"lot": lot, "step": step, "keys": keys}
        self.store.meta_put(k, out)
        return out

    def candles(self, key: str, day: str) -> list[list]:
        hit = self.store.get(key, day)
        if hit is not None:
            return hit
        rows = self.client.expired_candles(key, day)
        self.store.put(key, day, rows)
        return rows

    def index_day(self, u: str, day: str) -> list[list]:
        k = f"IDX|{u}"
        hit = self.store.get(k, day)
        if hit is not None:
            return hit
        rows = self.client.index_candles(u, day)
        if rows:
            self.store.put(k, day, rows)
        return rows

    # -- jobs -----------------------------------------------------------------
    def _job(self, key: str, fn) -> dict:
        cached = self.store.meta_get(key, 10 * 365 * 86400)
        if cached is not None:
            return {"status": "done", "progress": 1.0, "error": None, "result": cached, "cached": True}
        with self._lock:
            job = self._jobs.get(key)
            if job is not None and job.status == "error" and time.time() - job.started > 15:
                job = self._jobs.pop(key, None) and None          # let the user retry a failed study
            if job is None:
                job = Job(key)
                self._jobs[key] = job

                def run():
                    try:
                        job.result = fn(job)
                        job.status = "done"
                        job.progress = 1.0
                        if job.result is not None:
                            self.store.meta_put(key, job.result)
                    except Exception as exc:               # noqa: BLE001 - surfaced to the panel
                        log.warning("history job %s failed: %s", key, exc)
                        job.status, job.error = "error", str(exc)[:200]
                threading.Thread(target=run, name="history-job", daemon=True).start()
        return job.view()

    # -- replay -----------------------------------------------------------------
    def replay(self, u: str, day: str, half: int = 5) -> dict:
        key = f"REPLAY|{u}|{day}|{half}"

        def build(job: Job) -> dict:
            idx = self.index_day(u, day)
            if not idx:
                raise RuntimeError("no index candles for that day")
            ctr = self.contracts(u, day)
            step, lot = ctr["step"], ctr["lot"]
            open_px = float(idx[0][1])
            atm = int(round(open_px / step) * step)
            strikes = [atm + i * step for i in range(-half, half + 1)]
            series: dict[str, dict[str, float]] = {}
            need = [(r, k) for k in strikes for r in ("CE", "PE") if ctr["keys"].get(f"{r}:{k}")]
            for i, (r, k) in enumerate(need):
                series[f"{r}:{k}"] = _series(self.candles(ctr["keys"][f"{r}:{k}"], day))
                job.progress = (i + 1) / (len(need) + 1)
            minutes = [_minute(c[0]) for c in idx]
            frames = []
            for c in idx:
                m = _minute(c[0])
                spot = float(c[4])
                live_atm = int(round(spot / step) * step)
                rows = [[k, _at(series.get(f"CE:{k}", {}), m, minutes), _at(series.get(f"PE:{k}", {}), m, minutes)] for k in strikes]
                ce = _at(series.get(f"CE:{live_atm}", {}), m, minutes)
                pe = _at(series.get(f"PE:{live_atm}", {}), m, minutes)
                frames.append({"t": m, "spot": spot, "atm": live_atm, "straddle": round(ce + pe, 2) if (ce is not None and pe is not None) else None, "rows": rows})
            return {"underlying": u, "day": day, "step": step, "lot": lot, "atm_open": atm, "strikes": strikes, "frames": frames,
                    "open": open_px, "close": float(idx[-1][4]), "high": max(float(c[2]) for c in idx), "low": min(float(c[3]) for c in idx)}
        return self._job(key, build)

    # -- backtest ---------------------------------------------------------------
    def backtest(self, u: str, strategy: str, entry: str, exit_: str, n: int = 52, wings: int = 2) -> dict:
        if strategy not in STRATEGIES:
            raise ValueError("unknown strategy")
        days = self.days(u)
        today = datetime.now(IST).strftime("%Y-%m-%d")
        days = [d for d in days if d < today][-max(1, min(n, 400)):]
        params = f"{strategy}|{entry}|{exit_}|{wings}"
        key = "BT|" + hashlib.sha1(f"{u}|{params}|{','.join(days)}".encode()).hexdigest()[:16]

        def one_day(day: str) -> dict | None:
            dkey = f"BTD|{u}|{day}|{params}"
            hit = self.store.meta_get(dkey, 10 * 365 * 86400)
            if hit is not None:
                return hit
            idx = self.index_day(u, day)
            if not idx:
                return None
            ctr = self.contracts(u, day)
            step, lot = ctr["step"], ctr["lot"]
            minutes = [_minute(c[0]) for c in idx]
            spot_series = _series(idx)
            spot_in = _at(spot_series, entry, minutes)
            if spot_in is None:
                return None
            atm = int(round(spot_in / step) * step)
            legs = legs_for(strategy, atm, step, wings)
            leg_series = []
            for right, strike, side in legs:
                k = ctr["keys"].get(f"{right}:{strike}")
                if not k:
                    return None
                leg_series.append((right, strike, side, _series(self.candles(k, day))))
            path_minutes = [m for m in minutes if entry <= m <= exit_]
            if not path_minutes:
                return None
            entry_px = {}
            for right, strike, side, s in leg_series:
                p = _at(s, entry, minutes)
                if p is None:
                    return None
                entry_px[(right, strike)] = p
            credit = -sum(side * entry_px[(r, k)] for r, k, side, _ in leg_series)      # net premium received (+) or paid (−)
            pnl_path = []
            for m in path_minutes:
                v = 0.0
                for right, strike, side, s in leg_series:
                    p = _at(s, m, minutes)
                    if p is None:
                        p = entry_px[(right, strike)]
                    v += side * (p - entry_px[(right, strike)])
                pnl_path.append(round(v, 2))
            pnl_pts = pnl_path[-1]
            spot_out = _at(spot_series, path_minutes[-1], minutes) or spot_in
            row = {"day": day, "atm": atm, "spot_in": round(spot_in, 1), "spot_out": round(spot_out, 1), "move_pct": round((spot_out - spot_in) / spot_in * 100, 2),
                   "credit": round(credit, 2), "pnl_pts": round(pnl_pts, 2), "pnl": round(pnl_pts * lot, 0), "lot": lot,
                   "mae": round(min(pnl_path), 2), "mfe": round(max(pnl_path), 2), "exit_at": path_minutes[-1],
                   "legs": [{"right": r, "strike": k, "side": side, "entry": entry_px[(r, k)]} for r, k, side, _ in leg_series]}
            self.store.meta_put(dkey, row)
            return row

        def build(job: Job) -> dict:
            rows = []
            for i, day in enumerate(days):
                try:
                    r = one_day(day)
                except ur.RestError as exc:
                    log.warning("backtest %s %s: %s", u, day, exc)
                    r = None
                if r:
                    rows.append(r)
                job.progress = (i + 1) / len(days)
            if not rows:
                raise RuntimeError("no usable expiry days")
            pnls = [r["pnl"] for r in rows]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]
            eq, acc, peak, dd = [], 0.0, 0.0, 0.0
            for p in pnls:
                acc += p
                peak = max(peak, acc)
                dd = min(dd, acc - peak)
                eq.append(round(acc, 0))
            gp, gl = sum(wins), -sum(losses)
            mean = sum(pnls) / len(pnls)
            sd = math.sqrt(sum((p - mean) ** 2 for p in pnls) / len(pnls)) if len(pnls) > 1 else 0.0
            stats = {"n": len(rows), "win_rate": round(len(wins) / len(rows) * 100, 1), "avg": round(mean, 0), "median": round(sorted(pnls)[len(pnls) // 2], 0),
                     "total": round(sum(pnls), 0), "best": round(max(pnls), 0), "worst": round(min(pnls), 0),
                     "profit_factor": round(gp / gl, 2) if gl > 0 else None, "max_drawdown": round(dd, 0),
                     "sharpe_like": round(mean / sd * math.sqrt(len(pnls)), 2) if sd > 0 else None,
                     "avg_mae_pts": round(sum(r["mae"] for r in rows) / len(rows), 1), "lot": rows[-1]["lot"],
                     "first": rows[0]["day"], "last": rows[-1]["day"]}
            return {"underlying": u, "strategy": strategy, "label": STRATEGIES[strategy][0], "entry": entry, "exit": exit_, "wings": wings,
                    "rows": rows, "equity": eq, "stats": stats}
        return self._job(key, build)
