#!/usr/bin/env bash
# Forced SSH command for the GitHub Actions key. Never evaluate SSH_ORIGINAL_COMMAND.
set -Eeuo pipefail

if ! systemctl start chrzaszczbot-update.service; then
    journalctl -u chrzaszczbot-update.service -n 50 --no-pager
    exit 1
fi
journalctl -u chrzaszczbot-update.service -n 15 --no-pager
sleep 5
systemctl is-active --quiet chrzaszczbot.service
echo "Bot działa; aktualna wersja: $(git -C /opt/ChrzaszczBOT rev-parse --short HEAD)"
