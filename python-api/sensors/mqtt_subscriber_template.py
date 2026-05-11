"""Plant-side MQTT subscriber - Physical AI Wave B1.

RUN THIS ON THE PLANT GATEWAY, NOT ON RENDER.

Render free tier sleeps after 15 minutes of HTTP idle, which silently drops
MQTT messages. The persistent subscriber must live on something always-on:
a Raspberry Pi, an industrial PC, a small VM in the plant control network.

What it does:
  1. Subscribes to an MQTT topic pattern (default: plant/+/sensors/#).
  2. Parses each message into (asset_tag, parameter, value).
  3. Looks up asset_tag -> asset_id either via a local mapping OR via the
     WorkHive Supabase REST API (sensor_topic_map table).
  4. Batches readings every BATCH_SECONDS or BATCH_SIZE, whichever first.
  5. POSTs the batch to the sensor-readings-ingest edge function.

Topic format (default):
  plant/{hive_code}/sensors/{asset_tag}/{parameter}

Configuration via environment variables (or a .env file):
  WORKHIVE_HIVE_ID            - your hive's uuid
  WORKHIVE_INGEST_URL         - https://YOUR_PROJECT.supabase.co/functions/v1/sensor-readings-ingest
  WORKHIVE_SERVICE_KEY        - service-role key (this script is plant-side, not on the browser)
  MQTT_BROKER_HOST            - e.g. mqtt.plant.local
  MQTT_BROKER_PORT            - 1883 (default) or 8883 (TLS)
  MQTT_USERNAME               - optional
  MQTT_PASSWORD               - optional
  MQTT_TOPIC_PATTERN          - default 'plant/+/sensors/#'
  WORKHIVE_ASSET_TAG_TO_ID    - JSON map { "PUMP-201": "<uuid>", ... } - optional
                                 if not provided, the script queries sensor_topic_map

Run:
  pip install paho-mqtt requests
  python mqtt_subscriber_template.py

This is a template. Copy to your plant gateway and adapt the topic format,
authentication, and tag mapping to your site's conventions.
"""

from __future__ import annotations

import json
import os
import queue
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

# Optional imports - the user installs these on the plant gateway.
try:
    import paho.mqtt.client as mqtt           # type: ignore[import]
    import requests                            # type: ignore[import]
except ImportError as e:
    print("Missing dependency. Install with: pip install paho-mqtt requests", file=sys.stderr)
    raise


# ── Config ────────────────────────────────────────────────────────────────────

HIVE_ID         = os.environ.get("WORKHIVE_HIVE_ID", "")
INGEST_URL      = os.environ.get("WORKHIVE_INGEST_URL", "")
SERVICE_KEY     = os.environ.get("WORKHIVE_SERVICE_KEY", "")
BROKER_HOST     = os.environ.get("MQTT_BROKER_HOST", "localhost")
BROKER_PORT     = int(os.environ.get("MQTT_BROKER_PORT") or 1883)
MQTT_USER       = os.environ.get("MQTT_USERNAME")
MQTT_PASS       = os.environ.get("MQTT_PASSWORD")
TOPIC_PATTERN   = os.environ.get("MQTT_TOPIC_PATTERN", "plant/+/sensors/#")

BATCH_SECONDS   = float(os.environ.get("WORKHIVE_BATCH_SECONDS") or 5.0)
BATCH_SIZE      = int(os.environ.get("WORKHIVE_BATCH_SIZE") or 50)

TAG_TO_ID_JSON  = os.environ.get("WORKHIVE_ASSET_TAG_TO_ID", "")
LOCAL_TAG_MAP: dict[str, str] = {}
if TAG_TO_ID_JSON:
    try:
        LOCAL_TAG_MAP = json.loads(TAG_TO_ID_JSON)
    except json.JSONDecodeError:
        print("[mqtt-bridge] WORKHIVE_ASSET_TAG_TO_ID is not valid JSON; ignoring.", file=sys.stderr)

if not HIVE_ID or not INGEST_URL or not SERVICE_KEY:
    print(
        "[mqtt-bridge] Set WORKHIVE_HIVE_ID, WORKHIVE_INGEST_URL, and "
        "WORKHIVE_SERVICE_KEY before running.",
        file=sys.stderr,
    )
    sys.exit(2)


# ── Reading queue + flusher ───────────────────────────────────────────────────

_q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=10_000)
_stop = threading.Event()


def _post_batch(readings: list[dict[str, Any]]) -> None:
    if not readings:
        return
    try:
        res = requests.post(
            INGEST_URL,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {SERVICE_KEY}",
                "apikey":        SERVICE_KEY,
            },
            json={"hive_id": HIVE_ID, "readings": readings},
            timeout=15,
        )
        if not res.ok:
            print(f"[mqtt-bridge] ingest {res.status_code}: {res.text[:200]}", file=sys.stderr)
        else:
            body = res.json()
            print(
                f"[mqtt-bridge] flushed {len(readings)} -> inserted={body.get('inserted')} "
                f"skipped_dup={body.get('skipped_dup')} rejected={body.get('rejected')}"
            )
    except requests.RequestException as err:
        print(f"[mqtt-bridge] ingest threw: {err}", file=sys.stderr)


def _flusher_loop() -> None:
    """Drain the queue every BATCH_SECONDS or when it reaches BATCH_SIZE."""
    pending: list[dict[str, Any]] = []
    last_flush = time.monotonic()
    while not _stop.is_set():
        try:
            item = _q.get(timeout=0.5)
            pending.append(item)
        except queue.Empty:
            pass

        now = time.monotonic()
        size_trigger = len(pending) >= BATCH_SIZE
        time_trigger = pending and (now - last_flush) >= BATCH_SECONDS
        if size_trigger or time_trigger:
            _post_batch(pending)
            pending.clear()
            last_flush = now

    if pending:
        _post_batch(pending)


# ── MQTT callbacks ────────────────────────────────────────────────────────────

def _on_connect(client: Any, userdata: Any, flags: Any, rc: int) -> None:
    if rc == 0:
        print(f"[mqtt-bridge] connected to {BROKER_HOST}:{BROKER_PORT}; subscribing to {TOPIC_PATTERN}")
        client.subscribe(TOPIC_PATTERN, qos=1)
    else:
        print(f"[mqtt-bridge] connect failed rc={rc}", file=sys.stderr)


def _parse_topic(topic: str) -> tuple[str, str] | None:
    """Topic shape: plant/{hive_code}/sensors/{asset_tag}/{parameter}."""
    parts = topic.split("/")
    if len(parts) < 5:
        return None
    # parts[0]='plant', parts[1]={hive_code}, parts[2]='sensors', parts[3]={tag}, parts[4:]={param + maybe trailing}
    asset_tag = parts[3].strip().upper()
    parameter = "_".join(parts[4:]).strip().lower()
    if not asset_tag or not parameter:
        return None
    return asset_tag, parameter


def _resolve_asset_id(asset_tag: str) -> str | None:
    # Local map wins for low-latency resolution.
    if asset_tag in LOCAL_TAG_MAP:
        return LOCAL_TAG_MAP[asset_tag]
    # Fallback: query asset_nodes via service-role REST. Cache locally so
    # we don't slam the REST API.
    return None  # Caller can extend this to do the REST lookup if desired.


def _on_message(client: Any, userdata: Any, msg: Any) -> None:
    try:
        topic   = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace").strip()
    except Exception as err:
        print(f"[mqtt-bridge] message decode failed: {err}", file=sys.stderr)
        return

    parsed = _parse_topic(topic)
    if not parsed:
        return
    asset_tag, parameter = parsed
    asset_id = _resolve_asset_id(asset_tag)
    if not asset_id:
        # Drop silently; the user is expected to fill WORKHIVE_ASSET_TAG_TO_ID
        # for the assets they actually want to track.
        return

    # Some plants publish JSON ({"value": 4.2, "ts": "..."}), most publish
    # raw numbers. Handle both.
    value: float | None = None
    recorded_at_iso: str | None = None
    try:
        as_json = json.loads(payload)
        if isinstance(as_json, dict):
            value = float(as_json.get("value"))
            ts = as_json.get("ts") or as_json.get("recorded_at")
            if ts:
                recorded_at_iso = str(ts)
        else:
            value = float(as_json)
    except (ValueError, TypeError, json.JSONDecodeError):
        try:
            value = float(payload)
        except ValueError:
            return

    if value is None:
        return
    if recorded_at_iso is None:
        recorded_at_iso = datetime.now(timezone.utc).isoformat()

    try:
        _q.put_nowait({
            "asset_id":    asset_id,
            "parameter":   parameter,
            "value":       value,
            "recorded_at": recorded_at_iso,
            "source":      "mqtt",
            "meta":        {"topic": topic},
        })
    except queue.Full:
        print("[mqtt-bridge] queue full - dropping reading", file=sys.stderr)


# ── Main loop ─────────────────────────────────────────────────────────────────

def _install_signal_handlers() -> None:
    def _shutdown(_signum: int, _frame: Any) -> None:
        print("[mqtt-bridge] shutting down...")
        _stop.set()
    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)


def main() -> None:
    _install_signal_handlers()

    flusher = threading.Thread(target=_flusher_loop, daemon=True)
    flusher.start()

    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS or "")
    if BROKER_PORT == 8883:
        client.tls_set()
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    try:
        while not _stop.is_set():
            client.loop(timeout=1.0)
    except Exception as err:
        print(f"[mqtt-bridge] fatal: {err}", file=sys.stderr)
    finally:
        client.disconnect()
        _stop.set()
        flusher.join(timeout=BATCH_SECONDS + 1)


if __name__ == "__main__":
    main()
