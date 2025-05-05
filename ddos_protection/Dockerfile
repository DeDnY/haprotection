# syntax=docker/dockerfile:1

##########################################
# 1) Сборка builder-этапа с выходом в сеть
##########################################
FROM alpine:3.18 AS builder

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
      fail2ban

##########################################
# 2) Финальный образ — просто наследуем builder
##########################################
FROM builder

# Копируем ваш скрипт и конфиги
COPY run.sh                   /run.sh
COPY jail.local               /etc/fail2ban/jail.local
COPY homeassistant.conf       /etc/fail2ban/filter.d/homeassistant.conf
COPY homeassistant-logrotate  /etc/logrotate.d/homeassistant
COPY app.py                   /app.py

# Скрипту нужен execute-флаг
RUN chmod +x /run.sh

# Запускаем ваш run.sh как PID 1
CMD [ "/run.sh" ]
