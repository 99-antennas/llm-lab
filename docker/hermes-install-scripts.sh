#!/command/with-contenv sh
# Cron jobs may only run scripts from $HERMES_HOME/scripts, which lives in the volume, so
# refresh this repo's scripts there on every start.
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"

install -d -o hermes -g hermes "$HERMES_HOME/scripts" "$HERMES_HOME/workspace/retreat-planning"
install -o hermes -g hermes -m 0644 /opt/hermes-gsm/scripts/*.py "$HERMES_HOME/scripts/"
