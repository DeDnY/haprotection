#!/usr/bin/env python3
import re
import subprocess
import threading
import time
import datetime
import collections
from flask import Flask, render_template, redirect, url_for, jsonify

app = Flask(__name__, static_folder="static", template_folder="templates")

# ─── In-memory ring buffer for last 120 samples (~1h @ 30s) ───
MAX_SAMPLES = 120
timestamps = collections.deque(maxlen=MAX_SAMPLES)
ddos_counts = collections.deque(maxlen=MAX_SAMPLES)
brute_counts = collections.deque(maxlen=MAX_SAMPLES)

def sample_metrics():
    """Background sampler: polls nft and fail2ban every 30s."""
    while True:
        now = datetime.datetime.utcnow().isoformat()
        # 1) DDoS: sum packets from meter
        try:
            out = subprocess.check_output(
                ["nft","list","meter","inet","ddos","ddos_meter"],
                stderr=subprocess.DEVNULL
            ).decode()
            # lines: "… packets 1234"
            ddos = sum(int(line.split()[-1])
                       for line in out.splitlines()
                       if "packets" in line or "pkts" in line)
        except:
            ddos = 0

        # 2) Brute: total failures from fail2ban
        try:
            status = subprocess.check_output(
                ["fail2ban-client","status","homeassistant"],
                stderr=subprocess.DEVNULL
            ).decode()
            brute = 0
            for line in status.splitlines():
                if line.strip().startswith("Failures"):
                    brute = int(line.split()[-1])
        except:
            brute = 0

        timestamps.append(now)
        ddos_counts.append(ddos)
        brute_counts.append(brute)

        time.sleep(30)

threading.Thread(target=sample_metrics, daemon=True).start()

def get_active_ips():
    rv = {}

    # 1) “New” connections from nft meter
    try:
        out = subprocess.check_output(
            ["nft","list","meter","inet","ddos","ddos_meter"],
            stderr=subprocess.DEVNULL
        ).decode()
        m = re.search(r"elements\s*=\s*\{([^}]*)\}", out)
        if m:
            for part in m.group(1).split(","):
                txt = part.strip()
                if not txt:
                    continue
                # если есть двоеточие – там count, иначе это просто dynamic entry
                if ":" in txt:
                    ip_str, cnt_str = txt.split(":", 1)
                    ip  = ip_str.strip()
                    cnt = int(cnt_str.strip())
                else:
                    # строка вида "192.168.0.20 limit rate 600/minute"
                    ip  = txt.split()[0]
                    cnt = 0
                rv[ip] = {"packets": cnt, "established": 0}
    except Exception:
        pass

    # 2) “Established” TCP sessions to port 8123
    try:
        # -H hides header, -n numeric, -t tcp, state established
        ss_out = subprocess.check_output(
            ["ss","-H","-tn","state","established"]
        ).decode().splitlines()

        for line in ss_out:
            cols = line.split()
            # Local address:port is cols[3], Peer address:port is cols[4]
            local, peer = cols[3], cols[4]
            # If this socket is to port 8123 (on either side)
            if local.endswith(":8123") or peer.endswith(":8123"):
                # remote IP is whichever side is NOT :8123
                remote = peer if local.endswith(":8123") else local
                ip = remote.rsplit(":",1)[0]
                if ip in rv:
                    rv[ip]["established"] += 1
                else:
                    rv[ip] = { "packets": 0, "established": 1 }
    except Exception:
        pass

    # Convert to list for templating
    return [
        { "ip": ip, "packets": data["packets"], "established": data["established"] }
        for ip, data in rv.items()
    ]

def get_blocked_ips():
    """List IPs currently in the blocked_ips set."""
    rv = []
    try:
        out = subprocess.check_output(
            ["nft","list","set","inet","ddos","blocked_ips"],
            stderr=subprocess.DEVNULL
        ).decode()
        # look for lines like: "element inet ddos blocked_ips { 1.2.3.4 timeout ... }"
        for line in out.splitlines():
            if "element inet ddos blocked_ips" in line:
                tokens = line.replace("{","").replace("}","").split()
                # tokens[-4] = IP (e.g. "1.2.3.4")
                if len(tokens) >= 4:
                    rv.append(tokens[-4])
    except:
        pass
    return rv

@app.route("/")
def index():
    act = get_active_ips()
    blk = get_blocked_ips()
    return render_template("index.html", active_ips=act, blocked_ips=blk)

@app.route("/ban/<ip>")
def ban(ip):
    subprocess.call(["nft","add","element","inet","ddos","blocked_ips", "{", ip, f"timeout {BAN_TIME}s", "}"])
    return redirect(url_for("index"))

@app.route("/unban/<ip>")
def unban(ip):
    subprocess.call(["nft","delete","element","inet","ddos","blocked_ips", "{", ip, "}"])
    return redirect(url_for("index"))

@app.route("/api/metrics")
def metrics():
    return jsonify({
        "timestamps": list(timestamps),
        "ddos":       list(ddos_counts),
        "brute":      list(brute_counts),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
