#!/bin/sh
set -eu

GARAGE_BIN="${GARAGE_BIN:-/garage}"
GARAGE_CONFIG="${GARAGE_CONFIG:-/etc/garage.toml}"

OUT_DIR="/data/garage"
ENV_FILE="$OUT_DIR/s3.env"

mkdir -p "$OUT_DIR"

if [ -f "$ENV_FILE" ]; then
  echo "s3.env already exists; skipping init"
  exit 0
fi

echo "Waiting for Garage..."
until "$GARAGE_BIN" -c "$GARAGE_CONFIG" status >/dev/null 2>&1; do
  sleep 0.2
done

node_id=$(
  "$GARAGE_BIN" -c "$GARAGE_CONFIG" status \
    | awk '/^==== HEALTHY NODES ====/{ok=1; next} ok && $1 ~ /^[0-9a-f]/ {print $1; exit}'
)

if [ -z "$node_id" ]; then
  echo "Failed to detect Garage node id" >&2
  "$GARAGE_BIN" -c "$GARAGE_CONFIG" status >&2 || true
  exit 1
fi

cur_ver=$(
  "$GARAGE_BIN" -c "$GARAGE_CONFIG" layout show 2>/dev/null \
    | awk -F': ' '/^Current layout version:/ {print $2; exit}' || true
)
cur_ver="${cur_ver:-0}"

if [ "$cur_ver" = "0" ]; then
  echo "Bootstrapping Garage layout"
  "$GARAGE_BIN" -c "$GARAGE_CONFIG" layout assign -z dc1 -c 1G "$node_id" || true
  "$GARAGE_BIN" -c "$GARAGE_CONFIG" layout apply --version 1 || true
else
  echo "Garage layout already applied (version $cur_ver)"
fi

bucket="dataforge-test"
"$GARAGE_BIN" -c "$GARAGE_CONFIG" bucket create "$bucket" >/dev/null 2>&1 || true

key_name="dataforge-test-rw"
key_out="$OUT_DIR/key-create.txt"

if ! "$GARAGE_BIN" -c "$GARAGE_CONFIG" key create "$key_name" >"$key_out" 2>/dev/null; then
  key_name="dataforge-test-rw-$(date +%s)"
  "$GARAGE_BIN" -c "$GARAGE_CONFIG" key create "$key_name" >"$key_out"
fi

access_key=$(awk -F': ' '/^Key ID:/ {print $2; exit}' "$key_out")
secret_key=$(awk -F': ' '/^Secret key:/ {print $2; exit}' "$key_out")

if [ -z "$access_key" ] || [ -z "$secret_key" ]; then
  echo "Failed to parse key output" >&2
  cat "$key_out" >&2
  exit 1
fi

"$GARAGE_BIN" -c "$GARAGE_CONFIG" bucket allow \
  --read --write --owner \
  "$bucket" \
  --key "$key_name" \
  >/dev/null

umask 077
cat >"$ENV_FILE" <<EOF
export AWS_ACCESS_KEY_ID=$access_key
export AWS_SECRET_ACCESS_KEY=$secret_key
export AWS_DEFAULT_REGION=garage
EOF

echo "Wrote $ENV_FILE"
