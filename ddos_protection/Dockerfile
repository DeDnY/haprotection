# syntax=docker/dockerfile:1
####################################################
# Финальный образ — сразу ставим всё необходимое
####################################################
FROM alpine:3.18

# 1) Устанавливаем все зависимости (включая nft и fail2ban)
RUN apk update && apk upgrade && \
    apk add --no-cache \
      bash \
      nftables \
      iproute2 \
      python3 \
      py3-pip \
      curl \
      jq \
      ca-certificates \
      logrotate \
      fail2ban && \
    pip3 install flask


# 2) Копируем скрипт и конфиги адд-она
COPY run.sh                   /run.sh
COPY jail.local               /etc/fail2ban/jail.local
COPY homeassistant.conf       /etc/fail2ban/filter.d/homeassistant.conf
COPY homeassistant-logrotate  /etc/logrotate.d/homeassistant
COPY app.py                   /app.py
COPY templates                /templates

# 3) Делаем run.sh исполняемым
RUN chmod +x /run.sh

# 4) Запускаем run.sh как PID 1
CMD [ "/run.sh" ]
