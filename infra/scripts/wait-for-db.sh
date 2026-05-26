# Aguarda o Postgres ficar disponível antes de prosseguir.

set -euo pipefail

HOST="${1:-${POSTGRES_HOST:-postgres}}"
PORT="${2:-${POSTGRES_PORT:-5432}}"
TIMEOUT="${3:-60}"

echo "[wait-for-db] Aguardando ${HOST}:${PORT} (timeout ${TIMEOUT}s)..."

start_time=$(date +%s)
while ! nc -z "${HOST}" "${PORT}" 2>/dev/null; do
    elapsed=$(( $(date +%s) - start_time ))
    if [ "${elapsed}" -ge "${TIMEOUT}" ]; then
        echo "[wait-for-db] ERRO: timeout após ${TIMEOUT}s aguardando ${HOST}:${PORT}"
        exit 1
    fi
    sleep 1
done

echo "[wait-for-db] ${HOST}:${PORT} pronto após ${elapsed}s."