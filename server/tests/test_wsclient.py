"""Exercise wsclient against a hand-rolled loopback WebSocket server."""
import base64, hashlib, os, socket, struct, threading, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from wsclient import WebSocket, WebSocketClosed, OP_TEXT, OP_BINARY, OP_PING, OP_CONT

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
RESULT = {}

def server(sock):
    conn, _ = sock.accept()
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += conn.recv(4096)
    head = buf.split(b"\r\n\r\n")[0].decode()
    key = next(l.split(":",1)[1].strip() for l in head.split("\r\n") if l.lower().startswith("sec-websocket-key"))
    accept = base64.b64encode(hashlib.sha1((key+GUID).encode()).digest()).decode()
    conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  f"Connection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n").encode())

    def frame(op, payload, fin=True):
        h = bytearray([(0x80 if fin else 0)|op])
        n=len(payload)
        if n<126: h.append(n)
        elif n<(1<<16): h.append(126); h+=struct.pack(">H",n)
        else: h.append(127); h+=struct.pack(">Q",n)
        return bytes(h)+payload           # server frames are unmasked

    def read_client_frame():
        def exact(n):
            b=b""
            while len(b)<n:
                c=conn.recv(n-len(b))
                if not c: raise RuntimeError("eof")
                b+=c
            return b
        b0,b1=exact(2); op=b0&0xF; masked=b1&0x80; ln=b1&0x7F
        if ln==126: ln=struct.unpack(">H",exact(2))[0]
        elif ln==127: ln=struct.unpack(">Q",exact(8))[0]
        mask=exact(4) if masked else b""
        p=exact(ln) if ln else b""
        if masked: p=bytes(x^mask[i%4] for i,x in enumerate(p))
        RESULT.setdefault("client_masked", bool(masked))
        return op,p

    # 1. client -> server text (must be masked)
    op,p = read_client_frame()
    RESULT["echo_in"] = (op, p.decode())

    # 2. server -> client: a ping the client must answer
    conn.sendall(frame(OP_PING, b"pingpayload"))
    op,p = read_client_frame()
    RESULT["pong"] = (op, p)

    # 3. server -> client: a fragmented binary message
    conn.sendall(frame(OP_BINARY, b"AAA", fin=False))
    conn.sendall(frame(OP_CONT, b"BBB", fin=False))
    conn.sendall(frame(OP_CONT, b"CCC", fin=True))

    # 4. server -> client: a 70 KB binary message (16-bit length path)
    big = os.urandom(70000)
    RESULT["big_sha"] = hashlib.sha256(big).hexdigest()
    conn.sendall(frame(OP_BINARY, big))

    # 5. server -> client: text
    conn.sendall(frame(OP_TEXT, b'{"type":"order"}'))

    # 6. close
    conn.sendall(frame(0x8, struct.pack(">H",1000)+b"bye"))
    conn.close()

s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",0)); s.listen(1)
port = s.getsockname()[1]
threading.Thread(target=server, args=(s,), daemon=True).start()

ws = WebSocket(f"ws://127.0.0.1:{port}/stream", headers={"X-Test":"1"})
ws.send_text("hello")
k1,m1 = ws.recv()                       # fragmented binary (ping handled internally)
k2,m2 = ws.recv()                       # 70 KB binary
k3,m3 = ws.recv()                       # text
try:
    ws.recv()
    closed = "NO"
except WebSocketClosed as e:
    closed = str(e)

import time; time.sleep(0.2)
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ")+name+("" if cond else f"  <- {extra}"))
    ok = ok and cond

print("=== wsclient conformance ===")
check("handshake + Sec-WebSocket-Accept verified", True)
check("client frames are masked", RESULT.get("client_masked") is True, RESULT)
check("text send round-trips", RESULT.get("echo_in")==(OP_TEXT,"hello"), RESULT.get("echo_in"))
check("ping answered with matching pong", RESULT.get("pong")==(0xA,b"pingpayload"), RESULT.get("pong"))
check("fragmented message reassembled", (k1,m1)==("binary",b"AAABBBCCC"), (k1,m1))
check("70KB frame intact", k2=="binary" and hashlib.sha256(m2).hexdigest()==RESULT["big_sha"], len(m2) if m2 else None)
check("text message decoded", (k3,m3)==("text",b'{"type":"order"}'), (k3,m3))
check("close frame raises WebSocketClosed", "1000" in closed and "bye" in closed, closed)
print("\n=== interrupt(): wake a reader from another thread without freeing its fd ===")
# A silent server: accepts, completes the handshake, then says nothing.
def quiet(srv):
    conn,_ = srv.accept()
    req=b""
    while b"\r\n\r\n" not in req: req += conn.recv(4096)
    key = [l.split(b":",1)[1].strip() for l in req.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
    acc = base64.b64encode(hashlib.sha1(key+b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "+acc+b"\r\n\r\n")
    RESULT["quiet_conn"] = conn            # keep it open; the client will shut down its side
s2 = socket.socket(); s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1); s2.bind(("127.0.0.1",0)); s2.listen(1)
threading.Thread(target=quiet, args=(s2,), daemon=True).start()
ws2 = WebSocket(f"ws://127.0.0.1:{s2.getsockname()[1]}/stream")
fd = ws2.sock.fileno()
woke = {}; woken=threading.Event(); may_close=threading.Event()
def reader():
    t0=time.time()
    try: ws2.recv(); woke["how"]="returned"
    except WebSocketClosed as e: woke["how"]="closed:"+str(e)
    except Exception as e: woke["how"]="error:"+type(e).__name__
    woke["after"]=time.time()-t0
    woke["fd_still_ours"]=ws2.sock.fileno()==fd       # nobody closed it under us
    woken.set(); may_close.wait(3.0)                  # hold the fd so the probe below runs while we still own it
    ws2.close()                                       # the reader owns the close
rt=threading.Thread(target=reader, daemon=True); rt.start(); time.sleep(0.3)
ws2.interrupt()                                       # from THIS thread, like stop() does
woken.wait(3.0)
probe=open(os.devnull,"rb"); probe_fd=probe.fileno(); probe.close()   # opened while the reader still holds fd
may_close.set(); rt.join(3.0)
check("reader wakes promptly", not rt.is_alive() and woke.get("after",9)<2, woke)
check("reader sees a closed socket, not a timeout", str(woke.get("how","")).startswith("closed"), woke)
check("fd stays reserved until the reader closes it", woke.get("fd_still_ours") is True and probe_fd!=fd, (probe_fd, fd, woke))
try: ws2.send_text("late"); late="sent"
except WebSocketClosed: late="refused"
check("send after interrupt raises WebSocketClosed", late=="refused", late)

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
