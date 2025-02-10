#!/usr/bin/env bash
set -e

# Обработка аргумента --stats (для телеграм бота)
if [[ "$1" == "--stats" ]]; then
        log_statistics
        exit 0
fi

# Функция сбора статистики
log_statistics()
{
        echo "---- [$(date '+%Y-%m-%d %H:%M:%S')] Статистика ----"

        # Количество попыток входа
        if [ -f "/config/home-assistant.log" ];then
                LOG_ATTEMPTS=$(grep -c "Login attempt" /config/home-assistant.log)
                echo "Всего попыток входа: $LOG_ATTEMPTS"
        else
                echo "Лог Home Assistant не найден."
        fi

        # Топ по подключениям (nftables)
        echo "активные подключения:"
        nft list meter inet ddos ddos_meter 2>/dev/null | grep -E "ip saddr|packets" | column -t
        ss -ntu | tail -n +2 | awk '{print $5}' | cut -d: -f1 | sort | uniq -C

        # Забаненные IP
        echo "Забаненные IP:"
        nft list set inet ddos blocked_ips 2>/dev/null
}

echo "Запуск скрипта run.sh..."

# Настройка cron для очиски Fail2ban
echo "0 0 * * * sqlite3 /var/lib/fail2ban/fail2ban.sqlite3 'DELETE FROM bans WHERE timeosban <(strftime(\"%s\", >

# Файл, в котором Supervisor хранит наши options:
CONFIG_PATH="/data/options.json"
DDOS_THRESHOLD=$(jq -r '.ddos_threshold' $CONFIG_PATH)
MAX_RETRY=$(jq -r '.max_retry' $CONFIG_PATH)
BAN_TIME=$(jq -r '.ban_time' $CONFIG_PATH)

echo "Настройки:"
echo "- Лимит подключений: $DDOS_THRESHOLD/мин"
echo "- Макс. попыток входа: $MAX_RETRY"
echo "- Время блокировки: $BAN_TIME сек"

# Проверка на лог файл
if [ -f /etc/logrotate.d/homeassistant ]; then
        echo "Конфигурация logrotate найдена."
else
        echo "Создание конфигурации logrotate..."
        echo "/config/homeassistant.log { daily rotate 7 compress missigok notifempty }" > /etc/logrotate.d/home>
fi
# 1. Настраиваем fail2ban (пропатчим jail.local)
sed -i "s/^maxretry =.*/maxretry = ${MAX_RETRY}/" /etc/fail2ban/jail.local || true
sed -i "s/^bantime =.*/bantime = ${BAN_TIME}/" /etc/fail2ban/jail.local || true


# 2. Запустим fail2ban
echo "Запускаем fail2ban..."
fail2ban-server -f --logtarget=STDOUT &


# 3. Настроим рейт-лимит nftables
echo "Настраиваем nftables..."
nft flush ruleset

nft add table inet ddos
nft add set inet ddos blocked_ips "{ type ipv4_addr; flags timeout; }"
nft add chain inet ddos input "{ type filter hook input priority 0; policy accept; }"

# Пропускаем роутер и свой IP
nft add rule inet ddos input ip saddr 192.168.0.1 accept
nft add rule inet ddos input ip saddr 192.168.0.57 accept

# Правило для уже заблокированных IP из fail2ban
nft add rule inet ddos input ip saddr @blocked_ips drop

# Rate limit: максимум $DDOS_THRESHOLD подключений в минуту с одного IP
nft add rule inet ddos input ct state new \
        meter ddos_meter { ip saddr limit rate ${DDOS_THRESHOLD}/minute burst 5 packets} \
        accept
nft add rule inet ddos input ct state new \
        add @blocked_ips { ip saddr timeout ${BAN_TIME}s } dropnft list ruleset

# Разрешаем остальные подключения
nft add rule inet ddos input tcp dport 8123 accept

echo "Запуск Flask-веб-интерфейса..."
python3 /app.py &

# 5. Запуск бесконечного цикла, чтобы конейнер не завершался
echo "Server ready"
while true; do
        sleep 600
        log_statistics
        fail2ban-client status homeassistant
done