"""Minimal DNS client over UDP, standard library only."""
import os
import socket
import struct
import time

TYPES = {"A": 1, "AAAA": 28, "HTTPS": 65, "CNAME": 5, "MX": 15, "TXT": 16, "SVCB": 64}
RCODES = {0: "NOERROR", 2: "SERVFAIL", 3: "NXDOMAIN", 5: "REFUSED"}


def build(name, qtype="A", qid=None):
    qid = int.from_bytes(os.urandom(2), "big") if qid is None else qid
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)  # RD set
    q = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.rstrip(".").split(".") if p) + b"\x00"
    return qid, header + q + struct.pack(">HH", TYPES.get(qtype, 1), 1)


def query(name, qtype="A", server="127.0.0.1", port=53, timeout=2.0):
    """Returns (rcode_name, ancount, elapsed_ms) or (None, 0, elapsed_ms) on timeout."""
    qid, pkt = build(name, qtype)
    fam = socket.AF_INET6 if ":" in server else socket.AF_INET
    t0 = time.monotonic()
    with socket.socket(fam, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        try:
            s.sendto(pkt, (server, port))
            while True:
                data, _ = s.recvfrom(4096)
                if len(data) >= 12 and struct.unpack(">H", data[:2])[0] == qid:
                    break
        except (socket.timeout, OSError):
            return None, 0, (time.monotonic() - t0) * 1000
    flags, _, an = struct.unpack(">HHH", data[2:8])
    return RCODES.get(flags & 0xF, str(flags & 0xF)), an, (time.monotonic() - t0) * 1000
