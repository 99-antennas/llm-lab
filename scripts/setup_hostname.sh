#!/usr/bin/env bash
set -euo pipefail

LAB_HOST="${LAB_HOST:-llm-lab}"
LINE="127.0.0.1  $LAB_HOST"
HOSTS_FILE="/etc/hosts"

echo "This will add the following line to $HOSTS_FILE:"
echo "  $LINE"
echo
read -r -p "Proceed? [y/N] " ans
case "$ans" in
  y|Y) ;;
  *) echo "Canceled."; exit 0;;
esac

if grep -qE "^[#\s]*127\.0\.0\.1\s+$LAB_HOST(\s|$)" "$HOSTS_FILE"; then
  echo "Entry already present."
  exit 0
fi

echo "Requesting sudo to update $HOSTS_FILE..."
sudo sh -c "printf '\n$LINE\n' >> '$HOSTS_FILE'"

echo "Done."
echo "Test with: ping -c 1 $LAB_HOST"
