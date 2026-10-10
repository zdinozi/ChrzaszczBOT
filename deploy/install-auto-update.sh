#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Uruchom instalator jako root: sudo bash deploy/install-auto-update.sh"
    exit 1
fi

readonly REPO_DIR="/opt/ChrzaszczBOT"
readonly DEPLOY_MODE="${DEPLOY_MODE:-github}"
if [[ "${DEPLOY_MODE}" != github && "${DEPLOY_MODE}" != timer ]]; then
    echo "DEPLOY_MODE musi mieć wartość github lub timer"
    exit 1
fi

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    echo "Brak repozytorium w ${REPO_DIR}"
    exit 1
fi

if [[ ! -f /etc/chrzaszczbot.env ]]; then
    echo "Brak /etc/chrzaszczbot.env z tokenem Discorda"
    exit 1
fi

for command in python3 git systemctl flock; do
    if ! command -v "${command}" >/dev/null 2>&1; then
        echo "Brak polecenia ${command}. Zainstaluj wymagania opisane w readme.md."
        exit 1
    fi
done

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Wymagany Python 3.10 lub nowszy")'

cd "${REPO_DIR}"
if [[ ! -x "${REPO_DIR}/.venv/bin/python" ]]; then
    python3 -m venv "${REPO_DIR}/.venv"
fi
"${REPO_DIR}/.venv/bin/python" -m pip install --disable-pip-version-check -r requirements.txt
"${REPO_DIR}/.venv/bin/python" -m unittest -q
"${REPO_DIR}/.venv/bin/python" -m py_compile main.py pepper_scraper.py
chmod 0600 /etc/chrzaszczbot.env

install -m 0644 "${REPO_DIR}/deploy/chrzaszczbot.service" /etc/systemd/system/chrzaszczbot.service
install -m 0755 "${REPO_DIR}/deploy/chrzaszczbot-update.sh" /usr/local/sbin/chrzaszczbot-update
install -m 0755 "${REPO_DIR}/deploy/chrzaszczbot-deploy.sh" /usr/local/sbin/chrzaszczbot-deploy
install -m 0644 "${REPO_DIR}/deploy/chrzaszczbot-update.service" /etc/systemd/system/chrzaszczbot-update.service
install -m 0644 "${REPO_DIR}/deploy/chrzaszczbot-update.timer" /etc/systemd/system/chrzaszczbot-update.timer

systemctl daemon-reload
systemctl enable chrzaszczbot.service
systemctl restart chrzaszczbot.service
if [[ "${DEPLOY_MODE}" == timer ]]; then
    systemctl enable --now chrzaszczbot-update.timer
    systemctl list-timers chrzaszczbot-update.timer --no-pager
else
    systemctl disable --now chrzaszczbot-update.timer
    echo "Bot uruchomiony. Wdrażanie przez GitHub Actions; timer wyłączony."
fi
