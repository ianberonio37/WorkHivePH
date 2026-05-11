"""Sensor pipeline module - Physical AI Wave B1.

Lives under python-api/sensors/. The HTTP-side ingest endpoint is the
Supabase edge function sensor-readings-ingest. This module contains:

  anomaly.py
    Rule-based Z-score anomaly detection over recent sensor_readings.
    Endpoint: POST /sensors/anomaly-z

  mqtt_subscriber_template.py
    Stand-alone paho-mqtt subscriber that the hive operator runs on their
    plant gateway (Pi, plant PC, anywhere always-on). Batches MQTT
    readings and POSTs them to sensor-readings-ingest. Not deployed on
    Render free tier - the free tier sleeps after 15 min idle, which
    would silently drop MQTT messages.

See README.md in this directory for deployment notes.
"""
