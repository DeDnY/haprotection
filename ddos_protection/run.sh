#!/usr/bin/env bash
set -e

# -----------------------------------------------------------------------------
# 0) Функция сбора статистики (для --stats)
# -----------------------------------------------------------------------------
log_statistics() {
    echo "---- [$(date '+%Y-%m-%d %H:%M:%S')] Статистика ----"
    echo "Активные счётчики:"
    if nft list meter inet ddos ddos_meter >/dev/null 2>&1; then
        nft list meter inet ddos ddos_meter | grep -E "ip saddr|packets"
    else
        echo "  (счетчик ddos_meter не найден)"
    fi

    echo "Забаненные IP:"
    if nft list set inet ddos blocked_ips >/dev/null 2>&1; then
        nft list set inet ddos blocked_ips
    else
        echo "  (нет заблокированных IP)"
    fi
}


echo "=== Запуск run.sh ==="

# -----------------------------------------------------------------------------
# 1) Параметры из options.json
# -----------------------------------------------------------------------------
CONFIG_PATH="/data/options.json"
DDOS_THRESHOLD=$(jq -r '.ddos_threshold' "$CONFIG_PATH")
MAX_RETRY=$(jq -r '.max_retry' "$CONFIG_PATH")
BAN_TIME=$(jq -r '.ban_time' "$CONFIG_PATH")

echo "Параметры:"
echo "- DDOS_THRESHOLD: $DDOS_THRESHOLD (макс. новых подключений в минуту с одного IP)"
echo "- MAX_RETRY: $MAX_RETRY (макс. попыток входа)"
echo "- BAN_TIME: $BAN_TIME сек (время бана)"

# -----------------------------------------------------------------------------
# 2) Настройка fail2ban
# -----------------------------------------------------------------------------
echo "Настраиваем fail2ban..."
sed -i "s/^maxretry =.*/maxretry = ${MAX_RETRY}/" /etc/fail2ban/jail.local || true
sed -i "s/^bantime =.*/bantime = ${BAN_TIME}/" /etc/fail2ban/jail.local || true
fail2ban-server -f --logtarget=STDOUT &

# -----------------------------------------------------------------------------
# 3) Настройка nftables
# -----------------------------------------------------------------------------
echo "Настраиваем nftables защиту (таблица ddos)..."
# Удаляем только свою таблицу (если есть), не трогаем остальное
nft delete table inet ddos 2>/dev/null || true

# Создаём таблицу и структуры
nft add table inet ddos
nft add set inet ddos blocked_ips '{ type ipv4_addr; flags timeout; }'
nft add chain inet ddos input '{ type filter hook input priority 0; policy accept; }'
nft add chain inet ddos output '{ type filter hook output priority 0; policy accept; }'

# Разрешаем loopback и DNS (порт 53) на любом интерфейсе
nft add rule inet ddos input iif "lo" accept
nft add rule inet ddos input udp dport 53 accept
nft add rule inet ddos input tcp dport 53 accept
nft add rule inet ddos output udp sport 53 accept
nft add rule inet ddos output tcp sport 53 accept

# Ограничиваем правила только внешним интерфейсом eno1
# Пропускаем трафик от роутера и от самой машины (например, IP 192.168.0.1 и 192.168.0.57)
nft add rule inet ddos input iif "eno1" ip saddr { 192.168.0.1,192.168.0.57 } accept

# Блокируем уже забаненные IP
nft add rule inet ddos input iif "eno1" ip saddr @blocked_ips drop

# Rate-limit: не более $DDOS_THRESHOLD новых подключений в минуту с одного IP
nft add rule inet ddos input iif "eno1" ct state new \
    meter ddos_meter { ip saddr limit rate ${DDOS_THRESHOLD}/minute burst 5 packets } \
    accept

# При превышении — добавляем IP в set blocked_ips на $BAN_TIME секунд и дропаем
nft add rule inet ddos input iif "eno1" ct state new \
    add @blocked_ips { ip saddr timeout ${BAN_TIME}s } drop

# Разрешаем доступ к порту Home Assistant (8123) и веб-интерфейсу аддона (5000)
nft add rule inet ddos input iif "eno1" tcp dport 8123 accept
nft add rule inet ddos input iif "eno1" tcp dport 5000 accept

echo "nftables готов."

# -----------------------------------------------------------------------------
# 4) Запуск Flask-сервиса
# -----------------------------------------------------------------------------
echo "Запуск Flask-веб-интерфейса..."
python3 /app.py &

# -----------------------------------------------------------------------------
# 5) Ждём, чтобы контейнер не завершился
# -----------------------------------------------------------------------------
echo "Сервер готов. Входим в бесконечный цикл."
while true; do
    sleep 600
    log_statistics
    fail2ban-client status homeassistant
done
