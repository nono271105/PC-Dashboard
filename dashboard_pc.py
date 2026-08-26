"""
PC Telemetry Dashboard
"""

import os
import re
import json
import time
from flask import Flask, jsonify, render_template_string, send_file
from dotenv import load_dotenv
import requests

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

LHM_URL = os.getenv("LHM_URL", "http://localhost:8085/data.json")
LHM_USER = os.getenv("LHM_USER")
LHM_PASS = os.getenv("LHM_PASS")
NAMES_FILE = os.getenv("NAMES_FILE", os.path.join(BASE_DIR, "names.json"))
SENSOR_CONFIG_FILE = os.getenv("SENSOR_CONFIG_FILE", os.path.join(BASE_DIR, "sensors.json"))
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "5000"))

DEFAULT_SENSOR_CONFIG = {
    "labels": {
        "cpu_name": "CPU",
        "gpu_name": "GPU",
        "ram_name": "RAM",
        "storage_c_name": "Disque C:",
        "storage_d_name": "Disque D:",
    },
    "defaults": {"ram_total_gb": 32.0, "vram_total_gb": 16.0, "storage_total_gb": 1000.0},
    "sensors": {},
}


def load_sensor_config():
    """Load local sensor mappings without committing machine-specific details."""
    config = {
        **DEFAULT_SENSOR_CONFIG,
        "labels": DEFAULT_SENSOR_CONFIG["labels"].copy(),
        "defaults": DEFAULT_SENSOR_CONFIG["defaults"].copy(),
        "sensors": {},
    }
    if not os.path.exists(SENSOR_CONFIG_FILE):
        return config

    try:
        with open(SENSOR_CONFIG_FILE, "r", encoding="utf-8") as file:
            local_config = json.load(file)
        for section in ("labels", "defaults", "sensors"):
            if isinstance(local_config.get(section), dict):
                config[section].update(local_config[section])
    except (OSError, json.JSONDecodeError):
        app.logger.warning("Impossible de charger la configuration locale des capteurs.")
    return config


def sensor_value(sensors, config, key):
    """Return a sensor value from a user-maintained keyword mapping."""
    keywords = config["sensors"].get(key, [])
    return find_sensor(sensors, keywords) if keywords else (None, None)


def parse_num(value_str):
    if not value_str:
        return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value_str))
    return float(m.group().replace(",", ".")) if m else None


def walk_lhm(node, path=""):
    text = node.get("Text", "")
    current_path = f"{path} › {text}" if path else text
    children = node.get("Children", [])
    results = []
    if not children:
        value = (node.get("Value") or "").strip()
        if value and value not in ("-", ""):
            results.append({"path": current_path, "value": value})
    else:
        for child in children:
            results.extend(walk_lhm(child, current_path))
    return results


def load_sensors_from_file():
    if os.path.exists(NAMES_FILE):
        try:
            with open(NAMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_raw_sensors():
    # 1. LibreHardwareMonitor Web Server
    try:
        auth = (LHM_USER, LHM_PASS) if LHM_USER else None
        resp = requests.get(LHM_URL, auth=auth, timeout=1.2)
        if resp.status_code == 200:
            return walk_lhm(resp.json()), True
    except Exception:
        pass

    # 2. Local names.json
    return load_sensors_from_file(), False


def find_sensor(sensors, keywords):
    for s in sensors:
        p = s.get("path", "").lower()
        if all(k.lower() in p for k in keywords):
            return parse_num(s.get("value")), s.get("value")
    return None, None


def get_telemetry():
    """Build the dashboard payload from locally configured sensor mappings."""
    sensors, is_live = get_raw_sensors()
    config = load_sensor_config()
    labels = config["labels"]
    defaults = config["defaults"]

    cpu_load, _ = sensor_value(sensors, config, "cpu_load")
    cpu_temp, _ = sensor_value(sensors, config, "cpu_temp")
    if cpu_temp is None:
        cpu_temp, _ = sensor_value(sensors, config, "cpu_temp_fallback")
    cpu_freq, _ = sensor_value(sensors, config, "cpu_frequency")
    cpu_power, _ = sensor_value(sensors, config, "cpu_power")
    cpu_volt, _ = sensor_value(sensors, config, "cpu_voltage")
    if cpu_volt is None:
        cpu_volt, _ = sensor_value(sensors, config, "cpu_voltage_fallback")

    gpu_load, _ = sensor_value(sensors, config, "gpu_load")
    gpu_temp, _ = sensor_value(sensors, config, "gpu_temp")
    gpu_hotspot, _ = sensor_value(sensors, config, "gpu_hotspot")
    gpu_clock, _ = sensor_value(sensors, config, "gpu_clock")
    gpu_power, _ = sensor_value(sensors, config, "gpu_power")
    gpu_vram_used, _ = sensor_value(sensors, config, "gpu_vram_used")
    gpu_vram_total, _ = sensor_value(sensors, config, "gpu_vram_total")
    gpu_fan, _ = sensor_value(sensors, config, "gpu_fan")

    ram_load, _ = sensor_value(sensors, config, "ram_load")
    ram_used, _ = sensor_value(sensors, config, "ram_used")
    ram_avail, _ = sensor_value(sensors, config, "ram_available")

    mb_temp, _ = sensor_value(sensors, config, "motherboard_temp")
    vrm_temp, _ = sensor_value(sensors, config, "vrm_temp")
    fan_pump, _ = sensor_value(sensors, config, "pump_fan")
    fan_2, _ = sensor_value(sensors, config, "chassis_fan_2")
    fan_3, _ = sensor_value(sensors, config, "chassis_fan_3")

    storage_c_temp, _ = sensor_value(sensors, config, "storage_c_temp")
    storage_c_used, _ = sensor_value(sensors, config, "storage_c_used")
    storage_c_free, _ = sensor_value(sensors, config, "storage_c_free")
    storage_c_total, _ = sensor_value(sensors, config, "storage_c_total")

    storage_d_temp, _ = sensor_value(sensors, config, "storage_d_temp")
    storage_d_used, _ = sensor_value(sensors, config, "storage_d_used")
    storage_d_free, _ = sensor_value(sensors, config, "storage_d_free")
    storage_d_total, _ = sensor_value(sensors, config, "storage_d_total")

    storage_c_total = storage_c_total if storage_c_total is not None else defaults["storage_total_gb"]
    storage_d_total = storage_d_total if storage_d_total is not None else defaults["storage_total_gb"]
    storage_c_used_gb = storage_c_total - storage_c_free if storage_c_free is not None else None
    storage_d_used_gb = storage_d_total - storage_d_free if storage_d_free is not None else None

    return {
        "is_live": is_live,
        "cpu": {
            "name": labels["cpu_name"],
            "load": round(cpu_load, 1) if cpu_load is not None else None,
            "temp": round(cpu_temp, 1) if cpu_temp is not None else None,
            "freq_mhz": round(cpu_freq, 0) if cpu_freq is not None else None,
            "freq_ghz": round(cpu_freq / 1000.0, 2) if cpu_freq is not None else None,
            "power": round(cpu_power, 1) if cpu_power is not None else None,
            "voltage": round(cpu_volt, 2) if cpu_volt is not None else None,
        },
        "gpu": {
            "name": labels["gpu_name"],
            "load": round(gpu_load, 1) if gpu_load is not None else None,
            "temp": round(gpu_temp, 1) if gpu_temp is not None else None,
            "hotspot": round(gpu_hotspot, 1) if gpu_hotspot is not None else None,
            "clock_mhz": round(gpu_clock, 0) if gpu_clock is not None else None,
            "power": round(gpu_power, 1) if gpu_power is not None else None,
            "vram_used": round(gpu_vram_used / 1024.0, 1) if gpu_vram_used is not None else None,
            "vram_total": round(gpu_vram_total / 1024.0, 1) if gpu_vram_total is not None else defaults["vram_total_gb"],
            "fan_rpm": round(gpu_fan, 0) if gpu_fan is not None else None,
        },
        "ram": {
            "name": labels["ram_name"],
            "load": round(ram_load, 1) if ram_load is not None else None,
            "used": round(ram_used, 1) if ram_used is not None else None,
            "avail": round(ram_avail, 1) if ram_avail is not None else None,
            "total": defaults["ram_total_gb"],
        },
        "temps": {
            "cpu": round(cpu_temp, 0) if cpu_temp is not None else None,
            "gpu": round(gpu_temp, 0) if gpu_temp is not None else None,
            "hotspot": round(gpu_hotspot, 0) if gpu_hotspot is not None else None,
            "mb": round(mb_temp, 0) if mb_temp is not None else None,
            "vrm": round(vrm_temp, 0) if vrm_temp is not None else None,
            "ssd": round(storage_c_temp, 0) if storage_c_temp is not None else None,
        },
        "fans": {
            "pump": round(fan_pump, 0) if fan_pump is not None else None,
            "fan2": round(fan_2, 0) if fan_2 is not None else None,
            "fan3": round(fan_3, 0) if fan_3 is not None else None,
            "gpu_fan": round(gpu_fan, 0) if gpu_fan is not None else None,
        },
        "storage": {
            "c": {
                "name": labels["storage_c_name"],
                "used_pct": round(storage_c_used, 1) if storage_c_used is not None else None,
                "used_gb": round(storage_c_used_gb, 0) if storage_c_used_gb is not None else None,
                "total_gb": round(storage_c_total, 0),
                "temp": round(storage_c_temp, 0) if storage_c_temp is not None else None,
            },
            "d": {
                "name": labels["storage_d_name"],
                "used_pct": round(storage_d_used, 1) if storage_d_used is not None else None,
                "used_gb": round(storage_d_used_gb, 0) if storage_d_used_gb is not None else None,
                "total_gb": round(storage_d_total, 0),
                "temp": round(storage_d_temp, 0) if storage_d_temp is not None else None,
            },
        },
    }


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="120" fill="url(#bg)"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#2563eb" stroke-width="36"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#38bdf8" stroke-width="36" stroke-dasharray="1005" stroke-dashoffset="400" stroke-linecap="round"/>
  <circle cx="256" cy="256" r="60" fill="#38bdf8"/>
</svg>"""


ICON_PNG = os.path.join(BASE_DIR, "icon.png")


@app.route("/favicon.ico")
@app.route("/apple-touch-icon.png")
@app.route("/icon.png")
def favicon():
    if os.path.exists(ICON_PNG):
        return send_file(ICON_PNG, mimetype="image/png")
    return FAVICON_SVG, 200, {"Content-Type": "image/svg+xml"}


@app.route("/api/data")
def api_data():
    try:
        return jsonify(get_telemetry())
    except Exception:
        app.logger.exception("Erreur lors de la génération des données de télémétrie.")
        return jsonify({"error": "Erreur interne lors de la lecture des données."}), 500


PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>PC Telemetry Dashboard</title>
  <link rel="icon" type="image/png" href="/icon.png">
  <link rel="apple-touch-icon" href="/icon.png">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }

    :root {
      --bg-dark:    #2e343b;
      --card-bg:    #3e464f;
      --card-hdr:   #343b44;
      --gauge-bg:   #23282f;
      --gauge-track:#1c2026;
      --blue-accent:#3da5ff;
      --blue-glow:  rgba(61, 165, 255, 0.4);
      --text-main:  #ffffff;
      --text-muted: #9ba7b4;
      --border:     #23282e;
      --green:      #10b981;
      --orange:     #f59e0b;
      --sans:       'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
      --num-font:   'Rajdhani', 'Roboto', sans-serif;
    }

    html, body {
      background: var(--bg-dark);
      color: var(--text-main);
      font-family: var(--sans);
      height: 100%;
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }

    .app-container {
      max-width: 1200px;
      margin: 0 auto;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      padding: 10px;
      gap: 10px;
    }

    /* ── TOP HEADER ── */
    .top-header {
      background: #23282f;
      border-radius: 4px;
      padding: 8px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border: 1px solid var(--border);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
      font-size: 13px;
      letter-spacing: 0.08em;
      color: #fff;
    }

    .cam-icon {
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 11px;
      color: var(--text-muted);
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 8px;
      border-radius: 3px;
      background: rgba(0,0,0,0.3);
      font-size: 11px;
    }

    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 6px var(--green);
    }

    .status-dot.offline {
      background: var(--orange);
      box-shadow: 0 0 6px var(--orange);
    }

    .clock-text {
      font-family: var(--num-font);
      font-size: 16px;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: 0.05em;
    }

    /* ── CARD ── */
    .card {
      background: var(--card-bg);
      border-radius: 4px;
      border: 1px solid var(--border);
      overflow: hidden;
    }

    .card-header {
      background: var(--card-hdr);
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(0,0,0,0.25);
    }

    .card-title {
      font-size: 13px;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
      letter-spacing: 0.02em;
    }

    .card-title .prefix {
      color: var(--blue-accent);
      font-weight: 800;
    }

    /* ── GAUGE GRID (4 GAUGES PER CARD) ── */
    .gauge-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      padding: 16px 14px;
    }

    @media (max-width: 768px) {
      .gauge-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        padding: 12px 10px;
      }
    }

    .gauge-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      position: relative;
    }

    .svg-gauge {
      width: 100%;
      max-width: 170px;
      height: auto;
      display: block;
      filter: drop-shadow(0 4px 10px rgba(0,0,0,0.25));
    }

    /* ── BOTTOM SECTION (RAM & STORAGE & SENSORS) ── */
    .bottom-grid {
      display: grid;
      grid-template-columns: 1fr 1.6fr;
      gap: 10px;
    }

    @media (max-width: 768px) {
      .bottom-grid {
        grid-template-columns: 1fr;
      }
    }

    /* RAM CONTENT */
    .ram-content {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 14px 10px;
      gap: 14px;
    }

    .ram-gauge-wrap {
      flex: 1;
      max-width: 140px;
    }

    .ram-stats {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .ram-stat-box {
      background: var(--gauge-bg);
      border-radius: 4px;
      padding: 8px 10px;
      border: 1px solid var(--border);
    }

    .ram-stat-lbl {
      font-size: 9px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 2px;
    }

    .ram-stat-val {
      font-family: var(--num-font);
      font-size: 20px;
      font-weight: 700;
      color: #fff;
    }

    .ram-stat-val.blue {
      color: var(--blue-accent);
    }

    .ram-stat-val.green {
      color: var(--green);
    }

    /* STORAGE CONTENT */
    .storage-content {
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .storage-item {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .storage-header {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      font-weight: 600;
      color: #ffffff;
    }

    .storage-temp {
      color: var(--text-muted);
      font-size: 10px;
    }

    .storage-bar-wrap {
      background: var(--gauge-bg);
      height: 34px;
      border-radius: 3px;
      overflow: hidden;
      position: relative;
      border: 1px solid var(--border);
      display: flex;
    }

    .storage-bar-used {
      background: var(--blue-accent);
      height: 100%;
      transition: width 0.5s ease;
      display: flex;
      align-items: center;
      padding-left: 10px;
    }

    .storage-bar-free {
      background: #23282f;
      height: 100%;
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding-right: 10px;
    }

    .storage-bar-txt {
      font-family: var(--num-font);
      font-size: 15px;
      font-weight: 700;
      color: #ffffff;
      white-space: nowrap;
      text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }

    .storage-bar-txt.free-txt {
      color: var(--text-muted);
      font-size: 13px;
    }

    /* EXTRA SENSORS STRIP */
    .sensors-strip {
      background: var(--card-bg);
      border-radius: 4px;
      border: 1px solid var(--border);
      padding: 10px 14px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
    }

    .sensor-tile {
      background: var(--gauge-bg);
      border-radius: 3px;
      padding: 6px 10px;
      border: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .sensor-tile-name {
      font-size: 10px;
      color: var(--text-muted);
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .sensor-tile-val {
      font-family: var(--num-font);
      font-size: 17px;
      font-weight: 700;
      color: #ffffff;
    }

    .sensor-tile-val.blue { color: var(--blue-accent); }
    .sensor-tile-val.purple { color: #c084fc; }
  </style>
</head>
<body>
<div class="app-container">

  <!-- TOP HEADER -->
  <header class="top-header">
    <div class="brand">
      <div class="cam-icon">
        <img src="/icon.png" width="20" height="20" style="border-radius:4px;display:block;" onerror="this.style.display='none'">
      </div>
      <span>PC TELEMETRY MONITOR</span>
    </div>
    <div class="header-right">
      <div class="status-badge">
        <span class="status-dot" id="status-dot"></span>
        <span id="status-text">CONNECTÉ</span>
      </div>
      <div class="clock-text" id="clock">--:--:--</div>
    </div>
  </header>

  <!-- ══════════ CPU CARD ══════════ -->
  <section class="card">
    <div class="card-header">
      <div class="card-title">
        <span class="prefix">CPU:</span> Processeur
      </div>
    </div>
    <div class="gauge-grid">

      <!-- 1. CPU TEMP (Ring) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <!-- Track -->
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="11"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <!-- Progress -->
          <circle id="ring-cpu-temp" cx="75" cy="75" r="54" fill="none" stroke="#3da5ff" stroke-width="11"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease;"/>
          <text x="75" y="52" text-anchor="middle" fill="#9ba7b4" font-size="11" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="1">TEMP</text>
          <text id="val-cpu-temp" x="75" y="86" text-anchor="middle" fill="#ffffff" font-size="34" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="104" text-anchor="middle" fill="#9ba7b4" font-size="13" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">°C</text>
        </svg>
      </div>

      <!-- 2. CPU LOAD (Ring) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <!-- Track -->
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="11"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <!-- Progress -->
          <circle id="ring-cpu-load" cx="75" cy="75" r="54" fill="none" stroke="#3da5ff" stroke-width="11"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease;"/>
          <text x="75" y="52" text-anchor="middle" fill="#9ba7b4" font-size="11" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="1">LOAD</text>
          <text id="val-cpu-load" x="75" y="86" text-anchor="middle" fill="#ffffff" font-size="34" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="104" text-anchor="middle" fill="#9ba7b4" font-size="14" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">%</text>
        </svg>
      </div>

      <!-- 3. CPU CLOCK SPEED (Needle Speedometer) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <!-- Semi-arc track with glow -->
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="10"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <circle id="arc-cpu-freq" cx="75" cy="75" r="54" fill="none" stroke="#2563eb" stroke-width="10"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease; opacity: 0.5;"/>
          <!-- Center needle line -->
          <line id="nd-cpu-freq" x1="75" y1="75" x2="75" y2="28" stroke="#ffffff" stroke-width="3" stroke-linecap="round"
            transform="rotate(-135 75 75)" style="transition: transform 0.4s ease;"/>
          <circle cx="75" cy="75" r="6" fill="#3da5ff"/>
          <text x="75" y="102" text-anchor="middle" fill="#9ba7b4" font-size="9.5" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="0.5">CLOCK SPEED</text>
          <text id="val-cpu-freq" x="75" y="126" text-anchor="middle" fill="#ffffff" font-size="24" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="139" text-anchor="middle" fill="#9ba7b4" font-size="10" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">MHz</text>
        </svg>
      </div>

      <!-- 4. CPU PUMP SPEED / FAN (Needle Speedometer) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="10"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <circle id="arc-cpu-pump" cx="75" cy="75" r="54" fill="none" stroke="#2563eb" stroke-width="10"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease; opacity: 0.5;"/>
          <line id="nd-cpu-pump" x1="75" y1="75" x2="75" y2="28" stroke="#ffffff" stroke-width="3" stroke-linecap="round"
            transform="rotate(-135 75 75)" style="transition: transform 0.4s ease;"/>
          <circle cx="75" cy="75" r="6" fill="#3da5ff"/>
          <text x="75" y="102" text-anchor="middle" fill="#9ba7b4" font-size="9.5" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="0.5">PUMP SPEED</text>
          <text id="val-cpu-pump" x="75" y="126" text-anchor="middle" fill="#ffffff" font-size="24" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="139" text-anchor="middle" fill="#9ba7b4" font-size="10" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">RPM</text>
        </svg>
      </div>

    </div>
  </section>

  <!-- ══════════ GPU CARD ══════════ -->
  <section class="card">
    <div class="card-header">
      <div class="card-title">
        <span class="prefix">GPU:</span> Carte graphique
      </div>
    </div>
    <div class="gauge-grid">

      <!-- 1. GPU TEMP (Ring) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="11"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <circle id="ring-gpu-temp" cx="75" cy="75" r="54" fill="none" stroke="#3da5ff" stroke-width="11"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease;"/>
          <text x="75" y="52" text-anchor="middle" fill="#9ba7b4" font-size="11" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="1">TEMP</text>
          <text id="val-gpu-temp" x="75" y="86" text-anchor="middle" fill="#ffffff" font-size="34" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="104" text-anchor="middle" fill="#9ba7b4" font-size="13" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">°C</text>
        </svg>
      </div>

      <!-- 2. GPU LOAD (Ring) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="11"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <circle id="ring-gpu-load" cx="75" cy="75" r="54" fill="none" stroke="#3da5ff" stroke-width="11"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease;"/>
          <text x="75" y="52" text-anchor="middle" fill="#9ba7b4" font-size="11" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="1">LOAD</text>
          <text id="val-gpu-load" x="75" y="86" text-anchor="middle" fill="#ffffff" font-size="34" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="104" text-anchor="middle" fill="#9ba7b4" font-size="14" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">%</text>
        </svg>
      </div>

      <!-- 3. GPU CLOCK SPEED (Needle Speedometer) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="10"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <circle id="arc-gpu-clock" cx="75" cy="75" r="54" fill="none" stroke="#2563eb" stroke-width="10"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease; opacity: 0.5;"/>
          <line id="nd-gpu-clock" x1="75" y1="75" x2="75" y2="28" stroke="#ffffff" stroke-width="3" stroke-linecap="round"
            transform="rotate(-135 75 75)" style="transition: transform 0.4s ease;"/>
          <circle cx="75" cy="75" r="6" fill="#3da5ff"/>
          <text x="75" y="102" text-anchor="middle" fill="#9ba7b4" font-size="9.5" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="0.5">CLOCK SPEED</text>
          <text id="val-gpu-clock" x="75" y="126" text-anchor="middle" fill="#ffffff" font-size="24" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="139" text-anchor="middle" fill="#9ba7b4" font-size="10" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">MHz</text>
        </svg>
      </div>

      <!-- 4. GPU FAN SPEED (Needle Speedometer) -->
      <div class="gauge-card">
        <svg class="svg-gauge" viewBox="0 0 150 150">
          <circle cx="75" cy="75" r="54" fill="#23282f"/>
          <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="10"
            stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
          <circle id="arc-gpu-fan" cx="75" cy="75" r="54" fill="none" stroke="#2563eb" stroke-width="10"
            stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease; opacity: 0.5;"/>
          <line id="nd-gpu-fan" x1="75" y1="75" x2="75" y2="28" stroke="#ffffff" stroke-width="3" stroke-linecap="round"
            transform="rotate(-135 75 75)" style="transition: transform 0.4s ease;"/>
          <circle cx="75" cy="75" r="6" fill="#3da5ff"/>
          <text x="75" y="102" text-anchor="middle" fill="#9ba7b4" font-size="9.5" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="0.5">FAN SPEED</text>
          <text id="val-gpu-fan" x="75" y="126" text-anchor="middle" fill="#ffffff" font-size="24" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
          <text x="75" y="139" text-anchor="middle" fill="#9ba7b4" font-size="10" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">RPM</text>
        </svg>
      </div>

    </div>
  </section>

  <!-- ══════════ BOTTOM GRID (RAM & STORAGE) ══════════ -->
  <div class="bottom-grid">

    <!-- RAM CARD -->
    <section class="card">
      <div class="card-header">
        <div class="card-title"><span class="prefix">RAM:</span> Mémoire système</div>
      </div>
      <div class="ram-content">
        <div class="ram-gauge-wrap">
          <svg class="svg-gauge" viewBox="0 0 150 150">
            <circle cx="75" cy="75" r="54" fill="#23282f"/>
            <circle cx="75" cy="75" r="54" fill="none" stroke="#1c2026" stroke-width="11"
              stroke-dasharray="254.47 84.82" stroke-linecap="round" transform="rotate(135 75 75)"/>
            <circle id="ring-ram-load" cx="75" cy="75" r="54" fill="none" stroke="#3da5ff" stroke-width="11"
              stroke-dasharray="0 339.29" stroke-linecap="round" transform="rotate(135 75 75)" style="transition: stroke-dasharray 0.4s ease;"/>
            <text x="75" y="52" text-anchor="middle" fill="#9ba7b4" font-size="11" font-weight="700" font-family="Roboto,sans-serif" letter-spacing="1">LOAD</text>
            <text id="val-ram-load" x="75" y="86" text-anchor="middle" fill="#ffffff" font-size="34" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">--</text>
            <text x="75" y="104" text-anchor="middle" fill="#9ba7b4" font-size="14" font-weight="700" font-family="Rajdhani,Roboto,sans-serif">%</text>
          </svg>
        </div>
        <div class="ram-stats">
          <div class="ram-stat-box">
            <div class="ram-stat-lbl">Utilisée</div>
            <div class="ram-stat-val blue" id="val-ram-used">-- <span style="font-size:13px;color:var(--text-muted)">GB</span></div>
          </div>
          <div class="ram-stat-box">
            <div class="ram-stat-lbl">Libre</div>
            <div class="ram-stat-val green" id="val-ram-avail">-- <span style="font-size:13px;color:var(--text-muted)">GB</span></div>
          </div>
        </div>
      </div>
    </section>

    <!-- STORAGE CARD -->
    <section class="card">
      <div class="card-header">
        <div class="card-title"><span class="prefix">STORAGE</span></div>
        <div style="font-size:11px;color:var(--text-muted);display:flex;gap:10px;">
          <span><span style="color:var(--blue-accent)">●</span> Used</span>
          <span><span style="color:#23282f">●</span> Free</span>
        </div>
      </div>
      <div class="storage-content">

        <!-- C: DRIVE -->
        <div class="storage-item">
          <div class="storage-header">
            <span>Disque C:</span>
            <span class="storage-temp" id="val-ssd-temp">-- °C</span>
          </div>
          <div class="storage-bar-wrap">
            <div class="storage-bar-used" id="bar-ssd-c" style="width: 0%;">
              <span class="storage-bar-txt" id="val-ssd-c-used">-- GB USED</span>
            </div>
            <div class="storage-bar-free">
              <span class="storage-bar-txt free-txt" id="val-ssd-c-free">-- GB FREE</span>
            </div>
          </div>
        </div>

        <!-- D: DRIVE -->
        <div class="storage-item">
          <div class="storage-header">
            <span>Disque D:</span>
            <span class="storage-temp" id="val-ssd-d-temp">-- °C</span>
          </div>
          <div class="storage-bar-wrap">
            <div class="storage-bar-used" id="bar-ssd-d" style="width: 0%;">
              <span class="storage-bar-txt" id="val-ssd-d-used">-- GB USED</span>
            </div>
            <div class="storage-bar-free">
              <span class="storage-bar-txt free-txt" id="val-ssd-d-free">-- GB FREE</span>
            </div>
          </div>
        </div>

      </div>
    </section>

  </div>

  <!-- ══════════ EXTRA SENSORS STRIP ══════════ -->
  <div class="sensors-strip">
    <div class="sensor-tile">
      <span class="sensor-tile-name">CPU Package Power</span>
      <span class="sensor-tile-val blue" id="val-cpu-power">-- W</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">GPU Package Power</span>
      <span class="sensor-tile-val blue" id="val-gpu-power">-- W</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">GPU Hot Spot</span>
      <span class="sensor-tile-val" id="val-gpu-hotspot">-- °C</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">GPU VRAM</span>
      <span class="sensor-tile-val purple" id="val-gpu-vram">-- / 16 GB</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">Carte Mère Temp</span>
      <span class="sensor-tile-val" id="val-mb-temp">-- °C</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">VRM Temp</span>
      <span class="sensor-tile-val" id="val-vrm-temp">-- °C</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">Ventilateur #2</span>
      <span class="sensor-tile-val purple" id="val-fan-2">-- RPM</span>
    </div>
    <div class="sensor-tile">
      <span class="sensor-tile-name">Ventilateur #3</span>
      <span class="sensor-tile-val purple" id="val-fan-3">-- RPM</span>
    </div>
  </div>

</div>

<script>
  /* ── CONSTANTS FOR SVG GAUGES (270 DEGREE ARCS) ── */
  const CIRCUMFERENCE = 339.29; // 2 * PI * 54
  const ARC_LENGTH    = 254.47; // 270 deg of circle (0.75 * CIRCUMFERENCE)

  /* Update Ring Progress */
  function updateRing(elementId, value, maxValue) {
    const el = document.getElementById(elementId);
    if (!el || value === null || value === undefined) return;
    const ratio = Math.min(1, Math.max(0, value / maxValue));
    const fillLength = ratio * ARC_LENGTH;
    el.style.strokeDasharray = `${fillLength} ${CIRCUMFERENCE}`;
  }

  /* Update Needle Speedometer */
  function updateNeedle(needleId, arcId, value, maxValue) {
    const needle = document.getElementById(needleId);
    if (!needle || value === null || value === undefined) return;
    const ratio = Math.min(1, Math.max(0, value / maxValue));
    // Needle sweeps from -135deg to +135deg (270deg total)
    const angle = -135 + (ratio * 270);
    needle.setAttribute('transform', `rotate(${angle} 75 75)`);
    if (arcId) {
      updateRing(arcId, value, maxValue);
    }
  }

  /* Helper to set inner text safely */
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = (text !== null && text !== undefined) ? text : '--';
  }

  /* Clock */
  function tickClock() {
    document.getElementById('clock').textContent =
      new Date().toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }
  tickClock();
  setInterval(tickClock, 1000);

  /* Telemetry Refresh Loop */
  async function refreshTelemetry() {
    try {
      const resp = await fetch('/api/data');
      const data = await resp.json();
      if (data.error) throw new Error(data.error);

      // Connection Status
      const dot = document.getElementById('status-dot');
      const statusText = document.getElementById('status-text');
      if (data.is_live) {
        dot.className = 'status-dot';
        statusText.textContent = 'CONNECTÉ';
      } else {
        dot.className = 'status-dot offline';
        statusText.textContent = 'NAMES.JSON';
      }

      /* ═════ CPU ═════ */
      const cpu = data.cpu;
      // 1. Temp (0 - 100°C)
      updateRing('ring-cpu-temp', cpu.temp, 100);
      setText('val-cpu-temp', cpu.temp !== null ? Math.round(cpu.temp) : '--');

      // 2. Load (0 - 100%)
      updateRing('ring-cpu-load', cpu.load, 100);
      setText('val-cpu-load', cpu.load !== null ? Math.round(cpu.load) : '--');

      // 3. Clock Speed (0 - 6000 MHz)
      const cpuFreqMhz = cpu.freq_mhz || (cpu.freq_ghz ? cpu.freq_ghz * 1000 : null);
      updateNeedle('nd-cpu-freq', 'arc-cpu-freq', cpuFreqMhz, 6000);
      setText('val-cpu-freq', cpuFreqMhz !== null ? Math.round(cpuFreqMhz) : '--');

      // 4. Pump / Fan (0 - 3500 RPM)
      const pumpRpm = data.fans ? data.fans.pump : null;
      updateNeedle('nd-cpu-pump', 'arc-cpu-pump', pumpRpm, 3500);
      setText('val-cpu-pump', pumpRpm !== null ? Math.round(pumpRpm) : '--');

      /* ═════ GPU ═════ */
      const gpu = data.gpu;
      // 1. Temp (0 - 110°C)
      updateRing('ring-gpu-temp', gpu.temp, 110);
      setText('val-gpu-temp', gpu.temp !== null ? Math.round(gpu.temp) : '--');

      // 2. Load (0 - 100%)
      updateRing('ring-gpu-load', gpu.load, 100);
      setText('val-gpu-load', gpu.load !== null ? Math.round(gpu.load) : '--');

      // 3. Clock Speed (0 - 3000 MHz)
      updateNeedle('nd-gpu-clock', 'arc-gpu-clock', gpu.clock_mhz, 3000);
      setText('val-gpu-clock', gpu.clock_mhz !== null ? Math.round(gpu.clock_mhz) : '--');

      // 4. Fan (0 - 3500 RPM)
      const gpuFanRpm = gpu.fan_rpm !== null ? gpu.fan_rpm : (data.fans ? data.fans.gpu_fan : null);
      updateNeedle('nd-gpu-fan', 'arc-gpu-fan', gpuFanRpm, 3500);
      setText('val-gpu-fan', gpuFanRpm !== null ? Math.round(gpuFanRpm) : '0');

      /* ═════ RAM ═════ */
      const ram = data.ram;
      updateRing('ring-ram-load', ram.load, 100);
      setText('val-ram-load', ram.load !== null ? Math.round(ram.load) : '--');
      setText('val-ram-used', ram.used !== null ? `${ram.used} GB` : '--');
      setText('val-ram-avail', ram.avail !== null ? `${ram.avail} GB` : '--');

      /* ═════ STORAGE ═════ */
      if (data.storage) {
        // C:
        const sc = data.storage.c;
        if (sc) {
          const cPct = sc.used_pct || (sc.total_gb && sc.used_gb ? (sc.used_gb / sc.total_gb) * 100 : 0);
          const barC = document.getElementById('bar-ssd-c');
          if (barC) barC.style.width = `${Math.min(100, Math.max(0, cPct))}%`;
          setText('val-ssd-c-used', sc.used_gb !== null ? `${Math.round(sc.used_gb)} GB USED` : '--');
          const freeC = (sc.total_gb && sc.used_gb) ? Math.round(sc.total_gb - sc.used_gb) : '--';
          setText('val-ssd-c-free', `${freeC} GB FREE`);
          setText('val-ssd-temp', sc.temp !== null ? `${sc.temp} °C` : '-- °C');
        }

        // D:
        const sd = data.storage.d;
        if (sd) {
          const dPct = sd.used_pct || (sd.total_gb && sd.used_gb ? (sd.used_gb / sd.total_gb) * 100 : 0);
          const barD = document.getElementById('bar-ssd-d');
          if (barD) barD.style.width = `${Math.min(100, Math.max(0, dPct))}%`;
          setText('val-ssd-d-used', sd.used_gb !== null ? `${Math.round(sd.used_gb)} GB USED` : '--');
          const freeD = (sd.total_gb && sd.used_gb) ? Math.round(sd.total_gb - sd.used_gb) : '--';
          setText('val-ssd-d-free', `${freeD} GB FREE`);
          setText('val-ssd-d-temp', sd.temp !== null ? `${sd.temp} °C` : '-- °C');
        }
      }

      /* ═════ EXTRA SENSORS STRIP ═════ */
      setText('val-cpu-power', cpu.power !== null ? `${cpu.power} W` : '-- W');
      setText('val-gpu-power', gpu.power !== null ? `${gpu.power} W` : '-- W');
      setText('val-gpu-hotspot', gpu.hotspot !== null ? `${gpu.hotspot} °C` : '-- °C');
      setText('val-gpu-vram', gpu.vram_used !== null ? `${gpu.vram_used} / ${gpu.vram_total || 16} GB` : '--');
      if (data.temps) {
        setText('val-mb-temp', data.temps.mb !== null ? `${data.temps.mb} °C` : '-- °C');
        setText('val-vrm-temp', data.temps.vrm !== null ? `${data.temps.vrm} °C` : '-- °C');
      }
      if (data.fans) {
        setText('val-fan-2', data.fans.fan2 !== null ? `${data.fans.fan2} RPM` : '-- RPM');
        setText('val-fan-3', data.fans.fan3 !== null ? `${data.fans.fan3} RPM` : '-- RPM');
      }

    } catch (err) {
      const dot = document.getElementById('status-dot');
      const statusText = document.getElementById('status-text');
      if (dot) dot.className = 'status-dot offline';
      if (statusText) statusText.textContent = 'CONNEXION PERDU';
    }
  }

  // Initial call and refresh every 1.5s
  refreshTelemetry();
  setInterval(refreshTelemetry, 1500);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE_HTML)


if __name__ == "__main__":
    print("=" * 60)
    print("PC Telemetry Dashboard")
    print(f"Accès local : http://{APP_HOST}:{APP_PORT}")
    print("=" * 60)
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
