#!/usr/bin/env bash
# Prefer IPv4 over IPv6 by writing /etc/gai.conf (Crostini-safe).
# Reversible via scripts/disable_ipv4_preference.sh

set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Need sudo. Re-run: sudo bash scripts/enable_ipv4_preference.sh" >&2
  exit 2
fi

GAI="/etc/gai.conf"
BK="/etc/gai.conf.bak.algonovax"

if [[ -f "$GAI" && ! -f "$BK" ]]; then
  cp -a "$GAI" "$BK"
fi

# Ensure file exists
touch "$GAI"

# Remove any previous algonovax block
perl -0777 -i -pe 's/\n# BEGIN ALGONOVAX IPV4 PREFERENCE\n.*?\n# END ALGONOVAX IPV4 PREFERENCE\n//gs' "$GAI"

cat >> "$GAI" <<'BLOCK'

# BEGIN ALGONOVAX IPV4 PREFERENCE
# Prefer IPv4-mapped addresses over IPv6 (fixes Binance.US -71012 "IPv6 not supported")
precedence ::ffff:0:0/96  100
# END ALGONOVAX IPV4 PREFERENCE
BLOCK

echo "OK: wrote IPv4 preference to /etc/gai.conf"
echo "Verify: getent ahosts api.binance.us | head"
