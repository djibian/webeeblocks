# Debugger ONLY: never use this image to launch the subject Webots campaign.
FROM ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca
USER root
LABEL org.opencontainers.image.base.digest="sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca"
LABEL org.opencontainers.image.description="Post-mortem GDB only; subject R2025a image remains unchanged"
# Network acquisition is restricted to this one-time provisioning build.
RUN set -eu; \
    if [ -f /etc/apt/sources.list ]; then sed -i 's@http://archive.ubuntu.com@https://archive.ubuntu.com@g; s@http://security.ubuntu.com@https://security.ubuntu.com@g' /etc/apt/sources.list; fi; \
    apt-get -o Acquire::Retries=2 update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --no-remove gdb; \
    /usr/bin/gdb --version; \
    rm -rf /var/lib/apt/lists/*
