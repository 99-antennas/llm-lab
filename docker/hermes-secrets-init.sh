#!/command/with-contenv sh
set -eu

exec env PYTHONPATH=/opt/hermes-gsm \
    /opt/hermes-gsm-venv/bin/python /opt/hermes-gsm/docker/hermes-secrets-init.py
