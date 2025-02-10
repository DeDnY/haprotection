# haprotection
HAProtection (Home Assistant DDoS/BruteForce Protection)
HAProtection — это Home Assistant Add-on, позволяющий защитить ваш сервер от DDoS-атак и перебора пароля. Он использует:

nftables (meter) для рейт-лимита новых соединений,
Fail2ban для брутфорс-попыток,
Flask для веб-интерфейса (мини–AdGuard-подобный), где вы можете смотреть список активных IP, заблокированных IP и разблокировать их вручную.
Возможности
Автоматический блок IP, которые создают слишком много «новых» соединений (configurable threshold).
Fail2ban анализирует неудачные логины Home Assistant, блокируя подозрительные IP.
Веб-интерфейс (Flask) на порту 8080:
Список «Активных IP» (замеченных в рейт-лимите),
«Заблокированные IP» (можно вручную «Разблокировать»),
Кнопка «Заблокировать» для любого IP (manual ban).
Белый список (whitelist) для роутера или локального IP, чтобы не блокировать свои же устройства.
Состав проекта
Dockerfile — сборка контейнера на базе Alpine, ставим bash, nftables, python3, fail2ban, flask.
run.sh — скрипт запуска:
Настраивает nftables (включая рейт-лимит и whitelist),
Запускает Fail2ban,
Запускает Flask (app.py) и оставляет контейнер в бесконечном цикле.
app.py — код Flask, отображает веб-интерфейс (порт 8080).
Показывает «Активные IP», «Заблокированные IP», даёт кнопки «Block/Unblock».
config.yaml — конфигурация Home Assistant Add-on (version, slug, host_network, privileged).
jail.local и homeassistant.conf (Fail2ban) — правила для брутфорса (неудачные логины).

Установка
Клонируйте репозиторий:
bash

git clone https://github.com/DeDnI/haprotectiya.git
cd haprotection
Постройте образ:
bash

docker build -t ddos_protection .

Запустите контейнер:
bash
docker run --net=host --privileged ddos_protection
--net=host и --privileged нужны, чтобы nftables мог менять правила.

Откройте http://<сервер>:8080 в браузере, увидите веб-UI.
Использование
Настройка порога
В config.yaml (или /data/options.json), укажите:

yaml

ddos_threshold: 500
max_retry: 5
ban_time: 600
ddos_threshold (int) — лимит «новых» соединений в минуту для одного IP. При превышении — авто-блок.
ban_time (int) — время (в секундах), на которое IP уходит в blocked_ips через nftables.
max_retry (int) — для Fail2ban: сколько неудачных логинов до бана.
Стресс-тест (HTTP)
Из другой машины:

bash

ab -n 10000 -c 100 http://<server>:8080/
Если порог ddos_threshold небольшой, IP попадёт в бан. В веб-UI увидите IP в «Заблокированные».

Стресс-тест (SYN-флуд)
Из macOS/Ubuntu:

bash
hping3 --flood --syn -p 8080 <server_ip>
Пакеты посыплются, nft meter превысит порог — IP будет добавлен в blocked_ips.

Как это работает
При старте run.sh выполняется:
nft flush ruleset — очистка правил,
Создание таблицы inet ddos, цепочки input (policy accept), набора blocked_ips,
«Белый список» (router IP и server IP),
Два правила:
meter ddos_meter { ip saddr limit rate X/minute } accept
add @blocked_ips ... drop (если лимит превышен),
Fail2ban стартует, слушает /config/home-assistant.log (ошибки логина). При max_retry=5 брутфорсе банит IP через blocked_ips.
Flask (app.py) поднимает веб-сервер на порт 8080, парсит nft list meter (для «Клиенты») и nft list set blocked_ips (для «Заблокированные»).

Авторы
@DeDnY
This project is licensed under the MIT License.

Авторы
@DeDnI (Если хотите указать своё имя или ник)
