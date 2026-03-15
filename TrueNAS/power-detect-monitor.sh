#!/bin/bash

# Configuration
TARGET_URL="http://www.x.wabb.it:1999"
DEBUG=false

log_message() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')]: $1"
}

while getopts "d" opt; do
  case $opt in
    d) DEBUG=true
    ;;
    *) echo "Usage: $0 [-d]" >&2
       exit 1
    ;;
  esac
done

STATUS=$(curl -sf --max-time 3 "$TARGET_URL")
CURL_EXIT=$?

if [[ $CURL_EXIT -ne 0 ]]; then
  echo "curl of '$TARGET_URL' failed with code $CURL_EXIT" 1>&2
  exit 2
fi

# Check if the response contains the shutdown trigger
if [[ "$STATUS" == "shutdown" ]]; then
  if [[ $DEBUG == true ]]; then
    log_message "[DEBUG]: 'shutdown' detected"
  else
    log_message "'shutdown' detected"
    midclt call system.shutdown || poweroff
  fi
fi

exit 0
