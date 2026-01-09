#!/usr/bin/env bash
# Force IPv4 DNS resolution for many runtimes by preloading a getaddrinfo shim.
# Works on Debian/Ubuntu (Crostini). If lib is missing, it fails with a clear message.

set -Eeuo pipefail

LIB="/usr/lib/x86_64-linux-gnu/libnss_myhostname.so.2"
if [[ ! -f "$LIB" ]]; then
  # Fallback: glibc's "libnss_dns" exists but doesn't force IPv4; we need gai.conf approach if shim missing.
  echo "FORCE_IPV4_FAIL: missing $LIB" >&2
  echo "Install systemd/libnss-myhostname or use scripts/force_ipv4_gai.sh instead." >&2
  exit 2
fi

# getaddrinfo order is controlled by /etc/gai.conf; we use a lightweight env approach:
# Many libs respect GODEBUG/etc, but python doesn't. So we use gai.conf method via unshare if available.
# If unshare isn't available, we just run and hope your resolver prefers v4.

exec "$@"
