#!/usr/bin/env python3
from flask import Flask, render_template, redirect, url_for, jsonify
import subprocess, threading, time, datetime, collections

app = Flask(__name__)

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
    """Parse nft meter for active IPs & packet counts."""
    rv = []
    try:
        out = subprocess.check_output(
            ["nft","list","meter","inet","ddos","ddos_meter"],
            stderr=subprocess.DEVNULL
        ).decode()
        for line in out.splitlines():
            parts = line.strip().split()
            # expect: ip saddr 1.2.3.4 packets 123 ...
            if len(parts) >= 5 and parts[0] != "meter" and "packets" in parts:
                ip = parts[2]
                pkt = parts[-1]
                rv.append({"ip": ip, "packets": pkt})
    except:
        pass
    return rv

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
    subprocess.call([
        "nft","add","element","inet","ddos","blocked_ips",
        "{", f"ip saddr {ip}", "timeout", "600s", "}"
    ])
    return redirect(url_for("index"))

@app.route("/unban/<ip>")
def unban(ip):
    subprocess.call([
        "nft","delete","element","inet","ddos","blocked_ips",
        "{", ip, "}"
    ])
    return redirect(url_for("index"))

@app.route("/api/metrics")
def metrics():
    return jsonify({
        "timestamps": list(timestamps),
        "ddos":       list(ddos_counts),
        "brute":      list(brute_counts),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
