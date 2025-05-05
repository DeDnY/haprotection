import subprocess
import re
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
  <title>DDoS Protection</title>
</head>
<body>
  <h1>Мини‐AdGuard для IP (nftables)</h1>

  <h2>Клиенты (активные IP)</h2>
  <p>Отображаем IP, которые зафиксированы в meter ddos_meter:</p>
  <table border="1">
    <tr><th>IP</th><th>Packets</th><th>Действие</th></tr>
    {% for ip, packets in active_ips.items() %}
      <tr>
        <td>{{ ip }}</td>
        <td>{{ packets }}</td>
        <td>
          {% if ip in blocked_ips %}
            <b>Уже заблокирован</b>
          {% else %}
            <form action="{{ url_for('block_ip') }}" method="post" style="display:inline;">
              <input type="hidden" name="ip" value="{{ ip }}">
              <button type="submit">Заблокировать</button>
            </form>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
  </table>

  <h2>Заблокированные IP</h2>
  <table border="1">
    <tr><th>IP</th><th>Действие</th></tr>
    {% for ip in blocked_ips %}
      <tr>
        <td>{{ ip }}</td>
        <td>
          <form action="{{ url_for('unblock_ip') }}" method="post" style="display:inline;">
            <input type="hidden" name="ip" value="{{ ip }}">
            <button type="submit">Разблокировать</button>
          </form>
        </td>
      </tr>
    {% endfor %}
  </table>

  <hr/>
  <p>Всего заблокировано: {{ blocked_ips|length }} IP</p>
</body>
</html>
"""

@app.route("/")
def index():
    # 1) Собираем список активных IP (из meter ddos_meter)
    active_ips = get_all_connections()

    # 2) Собираем список заблокированных IP (из nft set blocked_ips)
    blocked_ips = get_blocked_ips()

    return render_template_string(TEMPLATE,
                                 active_ips=active_ips,
                                 blocked_ips=blocked_ips)

@app.route("/block", methods=["POST"])
def block_ip():
    ip = request.form.get("ip")
    if ip:
        # Добавляем IP в nft set blocked_ips (без timeout -> блокировка "навсегда")
        cmd = ["nft", "add", "element", "inet", "ddos", "blocked_ips", f"{{ {ip} }}"]
        subprocess.call(cmd)
    return redirect(url_for("index"))

@app.route("/unblock", methods=["POST"])
def unblock_ip():
    ip = request.form.get("ip")
    if ip:
        # Удаляем IP из nft set blocked_ips
        cmd = ["nft", "delete", "element", "inet", "ddos", "blocked_ips", f"{{ {ip} }}"]
        subprocess.call(cmd)
    return redirect(url_for("index"))

def get_all_connections():

#Возвращает словарь { 'ip': count_of_connections },
#анализируя 'ss -ntu'.
        import subprocess
        output = subprocess.check_output(["ss", "-ntu"]).decode("utf-8", "ignore")
        lines = output.splitlines()[1:]
        from collections import Counter
        ip_counts = Counter()

        for line in lines:
                parts = line.split()
                if len(parts) >=5:
                        remote = parts[4]
                        ip_port = remote.rsplit(":", 1)
                        if len(ip_port) ==2:
                                ip = ip_port[0]
                                ip_counts[ip] += 1
        return dict(ip_counts)

def get_blocked_ips():
    """
    Вызывает 'nft list set inet ddos blocked_ips'
    и парсит 'elements = { 1.2.3.4 timeout 300s, 5.6.7.8 }' и т.п.
    Возвращает set(['1.2.3.4', '5.6.7.8', ...]).
    """
    blocked = set()
    try:
        output = subprocess.check_output(
            ["nft", "list", "set", "inet", "ddos", "blocked_ips"]
        ).decode("utf-8", "ignore")
    except subprocess.CalledProcessError:
        return blocked

    # Ищем блок "elements = { ... }"
    # Пример: elements = { 192.168.0.10, 1.2.3.4 timeout 300s }
    in_elements_block = False

    for line in output.splitlines():
        line = line.strip()

        if line.startswith("elements = {"):
            in_elements_block = True
            # Могут быть IP прямо на этой строке
            line = line.replace("elements = {", "")
        if in_elements_block:
            # Пока не встретим '}'
            if "}" in line:
                # обрезаем до '}'
                idx = line.index("}")
                chunk = line[:idx]
                in_elements_block = False
            else:
             chunk = line

            # Удаляем лишние пробелы, запятые
            chunk = chunk.replace("}", "").strip()
            # Может быть несколько IP через запятую
            parts = [p.strip() for p in chunk.split(",") if p.strip()]
            for p in parts:
                # p может быть '192.168.0.10' или '192.168.0.10 timeout 119s'
                m = re.match(r'^([\d\.]+)', p)
                if m:
                    blocked.add(m.group(1))

    return blocked

if __name__ == "__main__":
    # Запустим Flask-сервер на 0.0.0.0:8080
    app.run(host="0.0.0.0", port=8080, debug=True)
