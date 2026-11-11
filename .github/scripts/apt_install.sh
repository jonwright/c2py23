#!/usr/bin/env bash
# .github/scripts/apt_install.sh
#
# Robust apt install for GitHub Actions runners.
#
# Background: the runner's /etc/apt/apt-mirrors.txt lists an
# azure.archive.ubuntu.com mirror first, with archive.ubuntu.com and
# security.ubuntu.com as fallbacks.  When the azure host is unresolvable,
# `apt-get update` only warns ("Some index files failed to download") and
# still exits 0, then `apt-get install` retries each package for ~20 s per
# attempt until the whole job hits its timeout and dies without running any
# test.
#
# This script:
#   * fails fast: wraps the network phases (update, package download) in
#     `timeout`; the unpack/configure phase runs from the local cache with
#     no timeout, so dpkg is never killed half way
#   * retries up to 3 attempts with a backoff between them
#   * rewrites apt-mirrors.txt (removing the azure line(s)) before attempt 2
#   * exits 0 only when every requested package is installed (checked by
#     `dpkg -s`), never merely when apt-get update reported success
#   * prints a GitHub `::error::` annotation on final failure and exits 1
#
# Usage: .github/scripts/apt_install.sh pkg1 pkg2 ...
#
# Environment:
#   APT_INSTALL_DRY_RUN=1   print the commands instead of running them
#   APT_MIRRORS_FILE=<path>  mirror file to rewrite (default /etc/apt/apt-mirrors.txt)
#
# Note: sudo is used only when not already root.

set -u

# --------------------------------------------------------------------------
# Timing budget (worst case for MAX_ATTEMPTS attempts)
#
#   update timeout        : 40 s   (a healthy update finishes far sooner)
#   download timeout      : 60 s   (a healthy download finishes far sooner)
#   backoff between tries : 8 s
#
# Worst case for the network phases = 3*(40+60) + 2*8 = 316 s.  The local
# unpack/configure runs once, after a successful download, and is not
# timed; the whole healthy step (update + download + unpack) takes about
# 20 s on the runners.  The workflows give the step 6 minutes (pure apt)
# or 8 minutes (apt + virtualenv + pip).
# --------------------------------------------------------------------------
UPDATE_TIMEOUT=40
DOWNLOAD_TIMEOUT=60
BACKOFF_SECS=8
MAX_ATTEMPTS=3

# apt options applied to every apt-get call.
# APT::Update::Error-Mode=any makes `apt-get update` return non-zero when any
# index fails, on apt versions that honour it; on older apt it is silently
# ignored, so the install result below is still the final judge.
APT_OPTS=(
  -o Acquire::Retries=2
  -o Acquire::http::Timeout=15
  -o Acquire::https::Timeout=15
  -o Acquire::ForceIPv4=true
  -o DPkg::Lock::Timeout=60
  -o APT::Update::Error-Mode=any
)

APT_MIRRORS_FILE="${APT_MIRRORS_FILE:-/etc/apt/apt-mirrors.txt}"
DRY_RUN="${APT_INSTALL_DRY_RUN:-}"

if [ "$(id -u)" -eq 0 ]; then
  PRE=()
else
  PRE=(sudo)
fi

log() {
  printf '%s\n' "$*"
}

# Do a command: either print it (dry run) or run it.  Command words are
# passed as individual arguments so sudo / timeout / apt options never rely
# on word splitting.
do_cmd() {
  if [ "$DRY_RUN" = "1" ]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

# Remove the azure mirror line(s) from the apt mirror list, keeping
# archive.ubuntu.com / security.ubuntu.com.  Keep a .orig backup.
rewrite_mirrors() {
  local mf="$1"
  if [ -z "$mf" ] || [ ! -f "$mf" ]; then
    log "apt_install: $mf not present; mirror rewrite skipped"
    return 0
  fi
  if ! grep -q 'azure' "$mf"; then
    log "apt_install: no azure mirror line found in $mf; nothing to rewrite"
    return 0
  fi
  if [ ! -e "${mf}.orig" ]; then
    "${PRE[@]}" cp "$mf" "${mf}.orig"
    log "apt_install: backed up $mf to ${mf}.orig"
  fi
  # The file is root-owned on the runners: filter as the caller, write
  # through tee under sudo.
  local kept
  kept=$(grep -v -i 'azure' "$mf")
  if [ -n "$kept" ]; then
    printf '%s\n' "$kept" | "${PRE[@]}" tee "$mf" >/dev/null
    log "apt_install: removed azure mirror line(s) from $mf; kept archive.ubuntu.com / security.ubuntu.com"
  else
    log "apt_install: rewrite would leave an empty mirror list; left $mf unchanged"
  fi
}

PKGS=("$@")
if [ "${#PKGS[@]}" -lt 1 ]; then
  log "apt_install: usage: apt_install.sh pkg1 pkg2 ..."
  exit 2
fi

log "apt_install: installing packages: ${PKGS[*]}"
log "apt_install: attempts=$MAX_ATTEMPTS update_timeout=${UPDATE_TIMEOUT}s download_timeout=${DOWNLOAD_TIMEOUT}s backoff=${BACKOFF_SECS}s"
log "apt_install: mirror file: $APT_MIRRORS_FILE"
if [ "$DRY_RUN" = "1" ]; then
  log "apt_install: APT_INSTALL_DRY_RUN=1: commands are printed, not executed"
fi

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  log ""
  log "-- attempt $attempt/$MAX_ATTEMPTS --"

  # Before the 2nd attempt, drop the azure mirror so the remaining fallbacks
  # (archive.ubuntu.com / security.ubuntu.com) are tried.
  if [ "$attempt" -eq 2 ]; then
    rewrite_mirrors "$APT_MIRRORS_FILE"
  fi

  do_cmd "${PRE[@]}" timeout "$UPDATE_TIMEOUT" apt-get "${APT_OPTS[@]}" update
  update_rc=$?
  log "apt_install: apt-get update returned $update_rc"

  # Network phase: fetch the .debs into the cache.  Safe to kill.
  do_cmd "${PRE[@]}" timeout "$DOWNLOAD_TIMEOUT" apt-get "${APT_OPTS[@]}" install -y --no-install-recommends --download-only "${PKGS[@]}"
  install_rc=$?
  log "apt_install: apt-get install --download-only returned $install_rc"

  # Local phase: unpack and configure from the cache.  No timeout, so dpkg
  # is never interrupted.
  if [ "$install_rc" -eq 0 ]; then
    do_cmd "${PRE[@]}" apt-get "${APT_OPTS[@]}" install -y --no-install-recommends --no-download "${PKGS[@]}"
    install_rc=$?
    log "apt_install: apt-get install --no-download returned $install_rc"
  fi

  # dpkg -s is the final judge: every requested package must be installed.
  all_installed=1
  if [ "$DRY_RUN" = "1" ]; then
    all_installed=0
    log "apt_install: dry run installs nothing; treating attempt as failed to exercise the retry/mirror path"
  else
    for pkg in "${PKGS[@]}"; do
      if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        all_installed=0
        log "apt_install: package not installed: $pkg"
      fi
    done
  fi

  if [ "$install_rc" -eq 0 ] && [ "$all_installed" -eq 1 ]; then
    log "apt_install: all packages installed successfully"
    exit 0
  fi

  if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
    log "apt_install: attempt $attempt failed; backing off ${BACKOFF_SECS}s"
    if [ "$DRY_RUN" = "1" ]; then
      do_cmd sleep "$BACKOFF_SECS"
    else
      sleep "$BACKOFF_SECS"
    fi
  fi
  attempt=$((attempt + 1))
done

printf '%s\n' "::error::apt could not install the packages after ${MAX_ATTEMPTS} attempts (network/mirror problem)"
exit 1
