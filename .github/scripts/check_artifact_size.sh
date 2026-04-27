#!/usr/bin/env bash
# Verify that an installer artifact exists and is at least MIN_MB megabytes.
#
# Usage: check_artifact_size.sh <glob> [min_mb=100]
set -euo pipefail

PATTERN="${1:?usage: $0 <glob> [min_mb]}"
MIN_MB="${2:-100}"

# shellcheck disable=SC2086
FILE=$(ls $PATTERN 2>/dev/null | head -1)
if [ -z "$FILE" ]; then
  echo "FAIL: no file matched $PATTERN"
  exit 1
fi

SIZE_MB=$(du -m "$FILE" | cut -f1)
echo "$FILE: ${SIZE_MB} MB"
if [ "$SIZE_MB" -lt "$MIN_MB" ]; then
  echo "FAIL: $FILE too small (${SIZE_MB} MB < ${MIN_MB} MB)"
  exit 1
fi
echo "OK: $FILE size is reasonable"
