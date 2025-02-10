FROM alpine:3.18

# Установка пакетов
RUN     apk update && \
        apk upgrade && \
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
        update-ca-certificates && \
        rm -f /etc/fail2ban/jail.d/sshd.conf \
        /etc/fail2ban/jail.d/sshd-ddos.conf \
        /etc/fail2ban/jail.d/alpine-sshd.conf \
        /etc/fail2ban/jail.conf && \
        pip install --no-cache-dir flask
RUN     apk add --no-cache logrotate
RUN     mkdir -p /etc/logrotate.d

# Копируем скрипт в контейрнер
COPY run.sh /run.sh
COPY jail.local /etc/fail2ban/jail.local
COPY homeassistant.conf /etc/fail2ban/filter.d/homeassistant.conf
COPY homeassistant-logrotate /etc/logrotate.d/homeassistant
COPY app.py /app.py

RUN chmod +x /run.sh

# Указываем, какой файл запускать на старте контейнера
CMD ["/run.sh"]