#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Uruchom instalator jako root: sudo bash deploy/install-auto-update.sh"
    exit 1
fi

readonly REPO_DIR="/opt/ChrzaszczBOT"

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    echo "Brak repozytorium w ${REPO_DIR}"
    exit 1
fi

if [[ ! -f /etc/chrzaszczbot.env ]]; then
    echo "Brak /etc/chrzaszczbot.env z tokenem Discorda"
    exit 1
fi

if [[ ! -x "${REPO_DIR}/.venv/bin/python" ]]; then
    echo "Brak środowiska Python w ${REPO_DIR}/.venv"
    exit 1
fi

install -m 0644 "${REPO_DIR}/deploy/chrzaszczbot.service" /etc/systemd/system/chrzaszczbot.service
install -m 0755 "${REPO_DIR}/deploy/chrzaszczbot-update.sh" /usr/local/sbin/chrzaszczbot-update
install -m 0644 "${REPO_DIR}/deploy/chrzaszczbot-update.service" /etc/systemd/system/chrzaszczbot-update.service
install -m 0644 "${REPO_DIR}/deploy/chrzaszczbot-update.timer" /etc/systemd/system/chrzaszczbot-update.timer

systemctl daemon-reload
systemctl enable --now chrzaszczbot.service
systemctl enable --now chrzaszczbot-update.timer

echo "Bot i timer zostały uruchomione. Następna aktualizacja:"
systemctl list-timers chrzaszczbot-update.timer --no-pager
