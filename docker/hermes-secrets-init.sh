#!/command/with-contenv sh
set -eu

# Early in boot the GSM client has crashed (SIGSEGV) before networking settled;
# retry rather than starting the gateway with missing or stale secrets.
attempt=1
until env PYTHONPATH=/opt/hermes-gsm \
    /opt/hermes-gsm-venv/bin/python /opt/hermes-gsm/docker/hermes-secrets-init.py; do
    if [ "$attempt" -ge 5 ]; then
        echo "hermes-secrets-init: failed after $attempt attempts" >&2
        exit 1
    fi
    echo "hermes-secrets-init: attempt $attempt failed; retrying in 3s" >&2
    attempt=$((attempt + 1))
    sleep 3
done
