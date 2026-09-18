FROM ghcr.io/home-assistant/base:3.22

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
    io.hass.name="Cloudflare Multi-DDNS" \
    io.hass.description="Update multiple Cloudflare DNS records" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3

COPY app.py /app/app.py
COPY www /app/www
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
