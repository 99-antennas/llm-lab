#!/command/with-contenv sh
# Runs at container start, before any gateway exists, so every gateway lock
# record left in the volume is stale. After an unclean stop (host reboot, VM
# kill) those records name PIDs that the fresh PID namespace reuses for s6
# processes, and the gateway refuses to start because it can't prove they're
# its own.
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"

rm -f "$HERMES_HOME/gateway.lock"
rm -f "$HERMES_HOME"/.local/state/hermes/gateway-locks/*
