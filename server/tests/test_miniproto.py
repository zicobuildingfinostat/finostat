"""miniproto decoding, checked against hand-computed bytes and an independent encoder."""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import miniproto as mp

ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    ok = ok and cond

# --- an encoder written independently of the decoder under test -------------
def vi(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out

def f_double(field, value): return vi((field << 3) | 1) + struct.pack("<d", value)
def f_varint(field, value): return vi((field << 3) | 0) + vi(value)
def f_bytes(field, raw):    return vi((field << 3) | 2) + vi(len(raw)) + raw
def f_str(field, s):        return f_bytes(field, s.encode())
def f_msg(field, raw):      return f_bytes(field, raw)
def map_entry(field, key, value_msg): return f_bytes(field, f_str(1, key) + f_msg(2, value_msg))

print("=== varints (hand-computed) ===")
check("0x01 -> 1", mp.read_varint(b"\x01", 0) == (1, 1))
# 300 encodes as 0xAC 0x02 -- the canonical protobuf doc example
check("0xAC 0x02 -> 300", mp.read_varint(b"\xac\x02", 0) == (300, 2), mp.read_varint(b"\xac\x02", 0))
check("multi-byte offset advances", mp.read_varint(b"\xff\xff\x03", 0) == (65535, 3), mp.read_varint(b"\xff\xff\x03",0))
try:
    mp.read_varint(b"\x80", 0); trunc = False
except mp.ProtoError:
    trunc = True
check("truncated varint raises", trunc)

print("\n=== wire types (hand-computed key bytes) ===")
# field 1, wire 1 (fixed64) -> key byte 0x09
raw = b"\x09" + struct.pack("<d", 24816.47)
d = mp.decode(raw)
check("key byte 0x09 = field 1 / fixed64", 1 in d, d)
check("double round-trips", abs(mp.as_double(d, 1) - 24816.47) < 1e-9, mp.as_double(d, 1))
# field 2, wire 0 (varint) -> key byte 0x10
d = mp.decode(b"\x10\xac\x02")
check("key byte 0x10 = field 2 / varint = 300", mp.as_int(d, 2) == 300, d)
# field 3, wire 2 (length) -> key byte 0x1a
d = mp.decode(b"\x1a\x05hello")
check("key byte 0x1a = field 3 / string", mp.as_str(d, 3) == "hello", d)

print("\n=== LTPC (real schema: ltp=1, ltt=2, ltq=3, cp=4) ===")
ltpc = f_double(1, 132.55) + f_varint(2, 1787000000) + f_varint(3, 75) + f_double(4, 128.00)
d = mp.decode(ltpc)
check("ltp", abs(mp.as_double(d, 1) - 132.55) < 1e-9, mp.as_double(d, 1))
check("cp (close) read from field 4", abs(mp.as_double(d, 4) - 128.00) < 1e-9, mp.as_double(d, 4))
check("ltq", mp.as_int(d, 3) == 75)

print("\n=== FeedResponse with map<string, Feed> ===")
# Feed.ltpc is field 1; FeedResponse.feeds is the map at field 2
feed_nifty = f_msg(1, f_double(1, 24816.47) + f_double(4, 24750.00))
feed_opt   = f_msg(1, f_double(1, 132.55)   + f_double(4, 128.00))
resp = (f_varint(1, 1)                                    # type = live_feed
        + map_entry(2, "NSE_INDEX|Nifty 50", feed_nifty)
        + map_entry(2, "NSE_FO|50978", feed_opt)
        + f_varint(3, 1787000123))
d = mp.decode(resp)
check("type = live_feed (1)", mp.as_int(d, 1) == 1, mp.as_int(d, 1))
feeds = mp.as_map(d, 2)
check("map decoded 2 entries", len(feeds) == 2, list(feeds))
check("map keys preserved", "NSE_INDEX|Nifty 50" in feeds and "NSE_FO|50978" in feeds, list(feeds))
n = mp.as_message(feeds["NSE_INDEX|Nifty 50"], 1)
check("nested Feed.ltpc.ltp", abs(mp.as_double(n, 1) - 24816.47) < 1e-9, n)
check("nested Feed.ltpc.cp",  abs(mp.as_double(n, 4) - 24750.00) < 1e-9, n)
o = mp.as_message(feeds["NSE_FO|50978"], 1)
check("option ltp", abs(mp.as_double(o, 1) - 132.55) < 1e-9, o)
check("currentTs", mp.as_int(d, 3) == 1787000123)

print("\n=== robustness ===")
check("empty message decodes to {}", mp.decode(b"") == {})
check("unknown field numbers are kept, not fatal", 99 in mp.decode(f_varint(99, 7)))
check("missing field -> default", mp.as_double({}, 1, 0.0) == 0.0)
check("as_str on missing -> ''", mp.as_str({}, 1) == "")
try:
    mp.decode(b"\x1a\xff\x01ab"); bad = False
except mp.ProtoError:
    bad = True
check("truncated length-delimited raises", bad)
check("repeated field yields a list", len(mp.decode(f_varint(1,1)+f_varint(1,2)+f_varint(1,3))[1]) == 3)

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
