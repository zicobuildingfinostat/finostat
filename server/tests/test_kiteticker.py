import os, struct, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import kiteticker as kt

ok=True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ")+name+("" if cond else f"  <- {extra}"))
    ok = ok and cond

def envelope(*packets):
    out = struct.pack(">H", len(packets))
    for p in packets:
        out += struct.pack(">H", len(p)) + p
    return out

# --- token/segment helpers -------------------------------------------------
NIFTY50 = 256265           # 256265 & 0xFF == 9 -> indices
print("=== segment + divisor ===")
check("NIFTY 50 token is an index", kt.is_index(NIFTY50), kt.segment_of(NIFTY50))
check("index divisor is 100", kt.divisor_for(NIFTY50)==100.0)
cds_token = (1000<<8)|kt.SEG_CDS
check("CDS divisor is 1e7", kt.divisor_for(cds_token)==10_000_000.0)
bcd_token = (1000<<8)|kt.SEG_BCD
check("BCD divisor is 1e4", kt.divisor_for(bcd_token)==10_000.0)
nfo_token = (1000<<8)|kt.SEG_NFO
check("NFO divisor is 100", kt.divisor_for(nfo_token)==100.0)
check("NFO is tradable", not kt.is_index(nfo_token))

# --- LTP packet ------------------------------------------------------------
print("\n=== ltp packet (8 bytes) ===")
p = struct.pack(">Ii", nfo_token, 24816_47//1)   # 2481647 paise = 24816.47
t = kt.parse_packet(p)
check("8-byte packet parses as ltp", t and t["mode"]=="ltp", t)
check("price scaled by 100", t and abs(t["last_price"]-24816.47)<1e-6, t and t["last_price"])

# --- index quote packet (28 bytes) ----------------------------------------
print("\n=== index quote packet (28 bytes) ===")
# order after ltp is HIGH, LOW, OPEN, CLOSE
p = struct.pack(">Iiiiiii", NIFTY50, 2481647, 2495000, 2470000, 2480000, 2475000, 0)
check("packet is 28 bytes", len(p)==28, len(p))
t = kt.parse_packet(p)
check("mode is quote", t["mode"]=="quote", t["mode"])
check("not tradable (index)", t["tradable"] is False)
check("high=24950 (not misread as open)", abs(t["ohlc"]["high"]-24950.0)<1e-6, t["ohlc"])
check("low=24700",   abs(t["ohlc"]["low"]-24700.0)<1e-6, t["ohlc"])
check("open=24800",  abs(t["ohlc"]["open"]-24800.0)<1e-6, t["ohlc"])
check("close=24750", abs(t["ohlc"]["close"]-24750.0)<1e-6, t["ohlc"])
exp = (24816.47-24750.0)*100/24750.0
check("change computed from close", abs(t["change"]-exp)<1e-6, (t["change"],exp))

# --- tradable quote packet (44 bytes) -------------------------------------
print("\n=== tradable quote packet (44 bytes) ===")
# order after the counters is OPEN, HIGH, LOW, CLOSE
p = struct.pack(">Iiiiiiiiiii", nfo_token, 13250, 75, 13100, 480000, 12000, 9000,
                13000, 14500, 11000, 12800)
check("packet is 44 bytes", len(p)==44, len(p))
t = kt.parse_packet(p)
check("mode is quote", t["mode"]=="quote")
check("last_price=132.50", abs(t["last_price"]-132.50)<1e-6, t["last_price"])
check("open=130.00",  abs(t["ohlc"]["open"]-130.0)<1e-6, t["ohlc"])
check("high=145.00",  abs(t["ohlc"]["high"]-145.0)<1e-6, t["ohlc"])
check("low=110.00",   abs(t["ohlc"]["low"]-110.0)<1e-6, t["ohlc"])
check("close=128.00", abs(t["ohlc"]["close"]-128.0)<1e-6, t["ohlc"])
check("volume carried", t["volume_traded"]==480000, t["volume_traded"])

# --- full packet (184 bytes) ----------------------------------------------
print("\n=== full packet (184 bytes) ===")
body = struct.pack(">Iiiiiiiiiii", nfo_token, 13250, 75, 13100, 480000, 12000, 9000,
                   13000, 14500, 11000, 12800)
body += struct.pack(">iiiii", 1787000000, 55000, 60000, 50000, 1787000001)
for i in range(5):   # buy depth
    body += struct.pack(">iiHH", 100+i, 13200-i*5, 3, 0)
for i in range(5):   # sell depth
    body += struct.pack(">iiHH", 200+i, 13300+i*5, 4, 0)
check("packet is 184 bytes", len(body)==184, len(body))
t = kt.parse_packet(body)
check("mode is full", t["mode"]=="full", t["mode"])
check("oi carried", t["oi"]==55000, t["oi"])
check("5 buy + 5 sell depth levels", len(t["depth"]["buy"])==5 and len(t["depth"]["sell"])==5)
check("best bid = 132.00", abs(t["depth"]["buy"][0]["price"]-132.0)<1e-6, t["depth"]["buy"][0])
check("best ask = 133.00", abs(t["depth"]["sell"][0]["price"]-133.0)<1e-6, t["depth"]["sell"][0])

# --- envelope --------------------------------------------------------------
print("\n=== envelope framing ===")
idx = struct.pack(">Iiiiiii", NIFTY50, 2481647, 2495000, 2470000, 2480000, 2475000, 0)
ltp = struct.pack(">Ii", nfo_token, 13250)
msg = envelope(idx, ltp, body)
ticks = kt.parse_binary(msg)
check("3 packets decoded from one message", len(ticks)==3, len(ticks))
check("packet order preserved", [x["mode"] for x in ticks]==["quote","ltp","full"], [x["mode"] for x in ticks])
check("heartbeat (1 byte) yields no ticks", kt.parse_binary(b"\x00")==[])
check("empty payload yields no ticks", kt.parse_binary(b"")==[])
check("truncated envelope degrades, no crash", len(kt.parse_binary(envelope(idx,ltp)[:-4]))==1,
      kt.parse_binary(envelope(idx,ltp)[:-4]))
check("unknown packet length skipped", kt.parse_binary(envelope(b"x"*17))==[])

# --- outbound --------------------------------------------------------------
print("\n=== outbound messages ===")
check("subscribe json", json.loads(kt.subscribe_message([1,2]))=={"a":"subscribe","v":[1,2]})
check("mode json", json.loads(kt.mode_message("full",[1]))=={"a":"mode","v":["full",[1]]})

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
