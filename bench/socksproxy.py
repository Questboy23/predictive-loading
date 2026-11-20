"""Benchmark SOCKS5 proxy (standard library, asyncio). Browsers and curl send
hostnames to it, so it is the only place names get resolved. That lets one
unprivileged process switch the resolver between:
  off: system resolver (getaddrinfo -> mDNSResponder -> network DNS)
  on:  Unbound + predictor on 127.0.0.1:<unbound_port>
and add Wi-Fi round-trip time:
  - each new TCP connection waits one RTT (handshake over the slow hop)
  - each forwarded chunk waits RTT/2 in its direction (order kept per direction)
  - a DNS lookup that left the machine (took > 1 ms) waits one RTT
Control port (port+1), one line per command: "MODE on|off", "RTT <ms>", "DROP", "STATS".

Usage: python3 bench/socksproxy.py PORT UNBOUND_PORT
"""
import asyncio
import json
import os
import socket
import struct
import sys
import time

STATE = {"mode": "off", "rtt": 0.0, "dns": [], "writers": set()}


def parse_answers(data):
    """IPv4/IPv6 addresses from a DNS response."""
    qd, an = struct.unpack(">HH", data[4:8])
    i = 12

    def skip_name(i):
        while True:
            n = data[i]
            if n == 0:
                return i + 1
            if n & 0xC0 == 0xC0:
                return i + 2
            i += n + 1

    for _ in range(qd):
        i = skip_name(i) + 4
    out = []
    for _ in range(an):
        i = skip_name(i)
        t, _, _, ln = struct.unpack(">HHIH", data[i:i + 10])
        i += 10
        if t == 1 and ln == 4:
            out.append(socket.inet_ntop(socket.AF_INET, data[i:i + 4]))
        elif t == 28 and ln == 16:
            out.append(socket.inet_ntop(socket.AF_INET6, data[i:i + 16]))
        i += ln
    return out


async def unbound_lookup(name, port, host="127.0.0.1"):
    loop = asyncio.get_running_loop()
    for qtype in (1, 28):
        qid = int.from_bytes(os.urandom(2), "big")
        q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + b"".join(
            bytes([len(p)]) + p.encode() for p in name.split(".") if p) + b"\x00" + struct.pack(">HH", qtype, 1)
        fut = loop.create_future()

        class P(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                if data[:2] == q[:2] and not fut.done():
                    fut.set_result(data)

        tr, _ = await loop.create_datagram_endpoint(P, remote_addr=(host, port))
        tr.sendto(q)
        try:
            data = await asyncio.wait_for(fut, 5)
        except asyncio.TimeoutError:
            data = None
        tr.close()
        if data:
            addrs = parse_answers(data)
            if addrs:
                return addrs
    return []


async def resolve(name, unbound_port):
    t0 = time.perf_counter()
    if STATE["mode"] == "on":
        addrs = await unbound_lookup(name, unbound_port)
    elif os.environ.get("PL_BENCH_OFF_DNS"):  # Mac tool live: system DNS is our Unbound, so ask the network resolver directly
        addrs = await unbound_lookup(name, 53, os.environ["PL_BENCH_OFF_DNS"])
    else:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(name, None, type=socket.SOCK_STREAM)
            addrs = [i[4][0] for i in infos]
        except socket.gaierror:
            addrs = []
    ms = (time.perf_counter() - t0) * 1000
    if ms > 1.0 and STATE["rtt"]:
        await asyncio.sleep(STATE["rtt"] / 1000)
        ms += STATE["rtt"]
    STATE["dns"].append([STATE["mode"], round(ms, 3)])
    return addrs


async def pipe(reader, writer, delay):
    q = asyncio.Queue()

    async def pump():
        while True:
            t, chunk = await q.get()
            if chunk is None:
                break
            wait = t + delay - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            writer.write(chunk)
            await writer.drain()

    task = asyncio.create_task(pump())
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            await q.put((time.monotonic(), chunk))
    except (ConnectionError, OSError):
        pass
    await q.put((0, None))
    try:
        await task
    except (ConnectionError, OSError):
        pass
    try:
        writer.close()
    except Exception:  # nosec B110: closing an already broken socket
        pass


async def handle(reader, writer, unbound_port):
    STATE["writers"].add(writer)
    try:
        head = await reader.readexactly(2)
        await reader.readexactly(head[1])
        writer.write(b"\x05\x00")
        ver, cmd, _, atyp = await reader.readexactly(4)
        if atyp == 3:
            host = (await reader.readexactly((await reader.readexactly(1))[0])).decode()
        elif atyp == 1:
            host = socket.inet_ntop(socket.AF_INET, await reader.readexactly(4))
        else:
            host = socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
        port = struct.unpack(">H", await reader.readexactly(2))[0]
        if cmd != 1:
            writer.write(b"\x05\x07\x00\x01" + b"\x00" * 6)
            return
        addrs = [host] if atyp != 3 else await resolve(host, unbound_port)
        up_r = up_w = None
        for a in addrs:
            try:
                up_r, up_w = await asyncio.wait_for(asyncio.open_connection(a, port), 10)
                break
            except (OSError, asyncio.TimeoutError):
                continue
        if up_w is None:
            writer.write(b"\x05\x04\x00\x01" + b"\x00" * 6)
            return
        if STATE["rtt"]:
            await asyncio.sleep(STATE["rtt"] / 1000)
        writer.write(b"\x05\x00\x00\x01" + b"\x00" * 6)
        STATE["writers"].add(up_w)
        half = STATE["rtt"] / 2000
        await asyncio.gather(pipe(reader, up_w, half), pipe(up_r, writer, half))
        STATE["writers"].discard(up_w)
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
        pass
    finally:
        STATE["writers"].discard(writer)
        try:
            writer.close()
        except Exception:  # nosec B110: closing an already broken socket
            pass


async def control(reader, writer):
    line = (await reader.readline()).decode().split()
    out = "ok"
    if line and line[0] == "MODE":
        STATE["mode"] = line[1]
    elif line and line[0] == "RTT":
        STATE["rtt"] = float(line[1])
    elif line and line[0] == "DROP":
        for w in list(STATE["writers"]):
            try:
                w.close()
            except Exception:  # nosec B110
                pass
        STATE["writers"].clear()
    elif line and line[0] == "STATS":
        out = json.dumps(STATE["dns"])
        STATE["dns"] = []
    writer.write((out + "\n").encode())
    await writer.drain()
    writer.close()


async def main(port, unbound_port):
    srv = await asyncio.start_server(lambda r, w: handle(r, w, unbound_port), "127.0.0.1", port)
    ctl = await asyncio.start_server(control, "127.0.0.1", port + 1)
    async with srv, ctl:
        await asyncio.gather(srv.serve_forever(), ctl.serve_forever())


def send(port, cmd):
    with socket.create_connection(("127.0.0.1", port + 1), timeout=10) as s:
        s.sendall((cmd + "\n").encode())
        return s.makefile().readline().strip()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), int(sys.argv[2])))
