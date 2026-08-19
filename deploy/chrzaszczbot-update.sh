#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_DIR="/opt/ChrzaszczBOT"
readonly VENV_DIR="${REPO_DIR}/.venv"

log() {
    echo "[chrzaszczbot-update] $*"
}

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    log "Brak repozytorium w ${REPO_DIR}"
    exit 1
fi

cd "${REPO_DIR}"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    log "Repozytorium zawiera lokalne zmiany; aktualizacja przerwana"
    exit 1
fi

git fetch --quiet origin main

current_commit="$(git rev-parse HEAD)"
remote_commit="$(git rev-parse origin/main)"

if [[ "${current_commit}" == "${remote_commit}" ]]; then
    log "Bot jest aktualny (${current_commit:0:7})"
    exit 0
fi

if ! git merge-base --is-ancestor "${current_commit}" "${remote_commit}"; then
    log "origin/main nie jest aktualizacją fast-forward; potrzebna interwencja ręczna"
    exit 1
fi

check_dir="$(mktemp -d /tmp/chrzaszczbot-check.XXXXXX)"
cleanup() {
    git worktree remove --force "${check_dir}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "Testowanie wersji ${remote_commit:0:7}"
git worktree add --quiet --detach "${check_dir}" "${remote_commit}"
python3 -m venv "${check_dir}/.venv"
"${check_dir}/.venv/bin/pip" install --quiet --disable-pip-version-check -r "${check_dir}/requirements.txt"
(
    cd "${check_dir}"
    .venv/bin/python -m unittest -q
    .venv/bin/python -m py_compile main.py pepper_scraper.py
)

log "Testy zakończone powodzeniem; wdrażanie"
git merge --quiet --ff-only "${remote_commit}"
"${VENV_DIR}/bin/pip" install --quiet --disable-pip-version-check -r requirements.txt
systemctl restart chrzaszczbot.service
log "Wdrożono wersję ${remote_commit:0:7}"
