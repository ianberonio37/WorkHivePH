# Sensors Module — Physical AI Wave B1

Two pieces:

## 1. `anomaly.py` — Z-score anomaly detection

Stateless Python function that reads recent `sensor_readings` from
Supabase and returns a Z-score for the latest value vs the rolling
window mean.

### Wire into `python-api/main.py`

```python
from sensors.anomaly import handle_zscore

# Inside your dispatch table:
elif path == "/sensors/anomaly-z":
    return handle_zscore(payload, supabase)
```

### Request

```json
POST /sensors/anomaly-z
{
  "hive_id":     "...",
  "asset_id":    "...",
  "parameter":   "vibration_mms",
  "window_days": 30,
  "min_n":       20
}
```

### Response

```json
{
  "n":          247,
  "mean":       4.21,
  "std":        0.34,
  "latest_value": 5.62,
  "latest_recorded_at": "2026-05-12T03:04:05Z",
  "z":          4.15,
  "anomaly":    true,
  "warning":    false,
  "diagnostic": "Latest value 5.62 is 4.15 sigma above the 247-reading window mean of 4.21 (std 0.34)."
}
```

Folds into `v_risk_truth.top_factors` as `sensor_anomaly_score` once the
Phase 5b composite-risk model is updated (separate change).

## 2. `mqtt_subscriber_template.py` — plant-side bridge

A `paho-mqtt` template the hive operator copies onto their plant gateway
(Raspberry Pi, plant PC, anywhere always-on). It:

1. Subscribes to an MQTT topic pattern.
2. Resolves `{asset_tag}` to `asset_id` via a local JSON map.
3. Batches readings every 5 seconds or 50 readings.
4. POSTs them to the `sensor-readings-ingest` Supabase edge function.

**Do NOT deploy this on Render free tier.** Render free tier sleeps after
15 minutes of HTTP idle and would silently drop MQTT messages.

### Install + run

```bash
pip install paho-mqtt requests
export WORKHIVE_HIVE_ID=...
export WORKHIVE_INGEST_URL='https://YOUR_PROJECT.supabase.co/functions/v1/sensor-readings-ingest'
export WORKHIVE_SERVICE_KEY=...
export MQTT_BROKER_HOST=mqtt.plant.local
export MQTT_BROKER_PORT=1883
export WORKHIVE_ASSET_TAG_TO_ID='{"PUMP-201":"<asset-uuid>","MTR-3B":"<asset-uuid>"}'

python mqtt_subscriber_template.py
```

For systemd autostart on a Pi:

```ini
# /etc/systemd/system/workhive-mqtt-bridge.service
[Unit]
Description=WorkHive MQTT bridge
After=network-online.target

[Service]
EnvironmentFile=/etc/workhive/bridge.env
ExecStart=/usr/bin/python3 /opt/workhive/mqtt_subscriber_template.py
Restart=always
RestartSec=5
User=workhive

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable workhive-mqtt-bridge
sudo systemctl start  workhive-mqtt-bridge
```

## Topic format

Default: `plant/{hive_code}/sensors/{asset_tag}/{parameter}`

Examples:

| Topic | Asset tag | Parameter |
|---|---|---|
| `plant/manila/sensors/PUMP-201/vibration_mms` | `PUMP-201` | `vibration_mms` |
| `plant/manila/sensors/MTR-3B/bearing_temp_c` | `MTR-3B` | `bearing_temp_c` |
| `plant/cebu/sensors/ATS-01/voltage_v` | `ATS-01` | `voltage_v` |

The parameter must match `^[a-z][a-z0-9_]{0,40}$` (validated in both the
edge function and `sensor_readings.parameter` CHECK constraint).

## Supported parameter examples

These are conventional names used elsewhere in the platform — pick what
matches your sensor library:

- `vibration_mms` (mm/s, ISO 10816)
- `bearing_temp_c`
- `motor_current_a`
- `oil_debris_ppm`
- `discharge_pressure_kpa`
- `flow_rate_lpm`
- `rpm`
- `voltage_v`
- `power_factor`
