# syntax=docker/dockerfile:1

#####################################################
# 1) builder: собираем все зависимости с выходом в сеть
#####################################################
ARG BUILD_FROM="ghcr.io/dedny/ha-ddos-builder:latest"
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

# Собираем всё, что понадобится, в единый архив
RUN tar czf /bundle.tar.gz \
      /etc/fail2ban \
      /etc/logrotate.d \
      /etc/ssl/certs \
      /usr/bin \
      /usr/bin \
      /usr/sbin \
      /usr/local/sbin \
      /usr/lib \
      /lib \
      /sbin

#####################################################
# 2) final: Home Assistant Supervisor билдит только это
#####################################################
FROM ${BUILD_FROM}

# Распаковываем зависимости, установленные на builder-этапе
# Копируем всё из builder-образа (он уже содержит APK-пакеты)
# — no tarball dance needed, просто наследуем filesystem.

# Копируем ваше приложение и конфиги
COPY run.sh                   /run.sh
COPY jail.local               /etc/fail2ban/jail.local
COPY homeassistant.conf       /etc/fail2ban/filter.d/homeassistant.conf
COPY homeassistant-logrotate  /etc/logrotate.d/homeassistant
COPY app.py                   /app.py

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
