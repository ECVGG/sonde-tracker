# Sonde Tracker — User Manual

Monitor radiosondes from [sondehub.org](https://sondehub.org) and receive Telegram alerts when a sonde is descending and predicted to land within a configurable radius.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [Telegram Bot Setup](#telegram-bot-setup)
4. [Running](#running)
5. [Alert Logic](#alert-logic)
6. [Deployment](#deployment)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Clone and enter
git clone <your-repo>
cd sonde-tracker

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy configuration templates
cp config/config.example.yaml config/config.yaml
cp .env.example .env

# Edit config.yaml with YOUR location
# Edit .env with your Telegram credentials

# Test notification
python -m src.main --test-notify

# Run once to verify sondehub connection
python -m src.main --once

# Run continuously
python -m src.main
```

---

## Configuration

### Required: Your Location (`config.yaml`)

```yaml
location:
  latitude: 40.4168      # Your latitude (e.g., Madrid)
  longitude: -3.7038     # Your longitude
  altitude_m: 650        # Your altitude above sea level (meters)

alert_radius_km: 30      # Alert if predicted landing within this radius
```

Get your coordinates at: https://www.latlong.net/

### Required: Telegram Credentials (`.env`)

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890
```

### Optional: Filters

```yaml
filters:
  frequency_mhz_min: 400    # Only meteorological sondes 400-406 MHz
  frequency_mhz_max: 406
  sonde_type: "RS41"        # Only Vaisala RS41
  min_altitude_m: 1000      # Ignore if already low
```

### Alert Behavior

```yaml
alerts:
  notify_on_descent_start: true    # Alert when descent begins
  notify_on_landing: true          # Alert when landing imminent
  alert_once_per_sonde: true       # ONLY ONE alert per sonde (default: true)
  min_alert_interval_sec: 300      # Min interval if alert_once_per_sonde: false
  include_map_link: true           # Include sondehub.org predictor link
```

**`alert_once_per_sonde: true`** (default): Only the FIRST matching alert fires per sonde — either "descent started" OR "landing soon", whichever happens first.

**`alert_once_per_sonde: false`**: Both alerts can fire (with `min_alert_interval_sec` throttling).

---

## Telegram Bot Setup

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow instructions
3. Copy the **token** (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)
4. For **chat_id**:
   - **Personal**: Message **@userinfobot** — it replies with your ID
   - **Group/Channel**: Add bot to group, send a message, then visit:
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
     Look for `"chat":{"id":-1001234567890}` (negative = group)

---

## Running

### Development / Foreground

```bash
# With custom config path
python -m src.main -c /path/to/config.yaml

# Debug logging
python -m src.main --log-level DEBUG

# JSON logs (for log aggregation)
python -m src.main --log-json --log-file logs/sonde-tracker.log
```

### Docker

```bash
cd deploy
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### systemd (Linux Production)

```bash
# 1. Create service user
sudo useradd -r -s /bin/false sonde-tracker

# 2. Install to /opt
sudo mkdir -p /opt/sonde-tracker
sudo cp -r src config /opt/sonde-tracker/
sudo chown -R sonde-tracker: /opt/sonde-tracker

# 3. Create virtualenv in /opt
sudo -u sonde-tracker python -m venv /opt/sonde-tracker/.venv
sudo -u sonde-tracker /opt/sonde-tracker/.venv/bin/pip install -r /opt/sonde-tracker/requirements.txt

# 4. Copy config and .env to /opt/sonde-tracker/config/
sudo cp config/config.yaml /opt/sonde-tracker/config/
sudo cp .env /opt/sonde-tracker/config/

# 5. Install service
sudo cp deploy/sonde-tracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sonde-tracker

# 6. Check status
sudo systemctl status sonde-tracker
journalctl -u sonde-tracker -f
```

---

## Alert Logic

| Phase | Condition | Alert Sent |
|-------|-----------|------------|
| Tracking | Sonde enters ~3× alert radius (horizontal) | — |
| Descent start | `ascent_rate < -0.5 m/s` AND predicted landing ≤ `alert_radius_km` | 🟡 **DESCENT DETECTED** |
| Landing imminent | Already descending + altitude < 2000 m + predicted landing ≤ radius | 🔴 **LANDING IMMINENT** |

**Landing prediction**: Simple ballistic extrapolation — assumes current horizontal velocity vector remains constant until ground. No atmospheric model.

**With `alert_once_per_sonde: true`** (default): Only the first condition met triggers an alert. If descent starts outside radius but later enters radius while descending, no second alert.

---

## Example Telegram Messages

### 🟡 Descent Detected

```
📡 DESCENT DETECTED 🟡

📍 Sonde: ABC123 (RS41)
📡 Frequency: 403.200 MHz
📍 Current position: 40.12345, -3.67890
📏 Altitude: 12.5 km
⬇️ Descent rate: 5.2 m/s
🧭 Heading: 245°
💨 Horiz. velocity: 15.2 m/s
🎯 Est. landing distance: 18.3 km

🔗 View on sondehub.org
```

### 🔴 Landing Imminent

```
🎯 LANDING IMMINENT 🔴

📍 Sonde: ABC123 (RS41)
📍 Position: 40.13500, -3.65000
📏 Altitude: 1.2 km
🎯 Est. distance: 2.1 km

🔗 View on sondehub.org
```

### 🚀 Service Startup

```
🚀 Sonde Tracker started

📍 Station: 40.41680, -3.70380
📏 Altitude: 650 m
🎯 Alert radius: 30 km
🔍 Filters: Frequency: 400-406 MHz, Type: RS41
```

### 🛑 Service Shutdown

```
🛑 Sonde Tracker stopped
```

---

## Testing

```bash
# Unit tests
pytest tests/ -v

# Linting
ruff check src/
black --check src/

# Type checking
mypy src/

# Test Telegram notification
python -m src.main --test-notify

# Test sondehub connection (waits for 1 message)
python -m src.main --once
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Activate venv: `source .venv/bin/activate` |
| `FileNotFoundError: config.yaml` | Run `cp config/config.example.yaml config/config.yaml` |
| `Variable TELEGRAM_BOT_TOKEN not defined` | Check `.env` file exists and has correct variable names |
| `TelegramError: Unauthorized` | Bot token invalid or bot blocked |
| `TelegramError: Chat not found` | `chat_id` wrong; bot not in group/channel |
| No alerts received | Check `alert_radius_km`, filters, and that sondes are actually in range |
| WebSocket disconnects | Normal — auto-reconnects with exponential backoff |

---

## Files Not to Commit

- `config/config.yaml` — contains your location
- `.env` — contains Telegram secrets
- `.venv/` — virtual environment
- `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`
- `logs/`, `dist/`, `build/`

See `.gitignore` for full list.

---

## License

MIT — See LICENSE file.