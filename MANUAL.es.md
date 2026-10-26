# Sonde Tracker — Manual de Usuario

Monitoriza radiosondas de [sondehub.org](https://sondehub.org) y recibe alertas por Telegram cuando una sonda está descendiendo y se prevé que aterrice dentro de un radio configurable.

---

## Tabla de Contenidos

1. [Inicio Rápido](#inicio-rápido)
2. [Configuración](#configuración)
3. [Configuración del Bot de Telegram](#configuración-del-bot-de-telegram)
4. [Ejecución](#ejecución)
5. [Lógica de Alertas](#lógica-de-alertas)
6. [Despliegue](#despliegue)
7. [Pruebas](#pruebas)
8. [Solución de Problemas](#solución-de-problemas)

---

## Inicio Rápido

```bash
# Clonar y entrar
git clone <tu-repo>
cd sonde-tracker

# Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copiar plantillas de configuración
cp config/config.example.yaml config/config.yaml
cp .env.example .env

# Editar config.yaml con TU ubicación
# Editar .env con tus credenciales de Telegram

# Probar notificación
python -m src.main --test-notify

# Ejecutar una vez para verificar conexión con sondehub
python -m src.main --once

# Ejecutar continuamente
python -m src.main
```

---

## Configuración

### Obligatorio: Tu Ubicación (`config.yaml`)

```yaml
location:
  latitude: 40.4168      # Tu latitud (ej. Madrid)
  longitude: -3.7038     # Tu longitud
  altitude_m: 650        # Tu altitud sobre el nivel del mar (metros)

alert_radius_km: 30      # Alertar si aterrizaje previsto dentro de este radio
```

Obtén tus coordenadas en: https://www.latlong.net/

### Obligatorio: Credenciales de Telegram (`.env`)

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890
```

### Opcional: Filtros

```yaml
filters:
  frequency_mhz_min: 400    # Solo sondas meteorológicas 400-406 MHz
  frequency_mhz_max: 406
  sonde_type: "RS41"        # Solo Vaisala RS41
  min_altitude_m: 1000      # Ignorar si ya está muy baja
```

### Comportamiento de Alertas

```yaml
alerts:
  notify_on_descent_start: true    # Alertar al empezar el descenso
  notify_on_landing: true          # Alertar cuando aterrizaje inminente
  alert_once_per_sonde: true       # SOLO UNA alerta por sonda (default: true)
  min_alert_interval_sec: 300      # Intervalo mínimo si alert_once_per_sonde: false
  include_map_link: true           # Incluir enlace a predictor de sondehub.org
```

**`alert_once_per_sonde: true`** (por defecto): Solo la **PRIMERA** alerta que coincida se dispara por sonda — bien "inicio de descenso" O "aterrizaje inminente", la que ocurra primero.

**`alert_once_per_sonde: false`**: Ambas alertas pueden dispararse (con limitación por `min_alert_interval_sec`).

---

## Configuración del Bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot` y sigue las instrucciones
3. Copia el **token** (formato: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)
4. Para el **chat_id**:
   - **Personal**: Escribe a **@userinfobot** — te responde con tu ID
   - **Grupo/Canal**: Añade el bot al grupo, envía un mensaje, luego visita:
     `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
     Busca `"chat":{"id":-1001234567890}` (negativo = grupo)

---

## Ejecución

### Desarrollo / Primer Plano

```bash
# Con ruta de config personalizada
python -m src.main -c /ruta/a/config.yaml

# Logs de depuración
python -m src.main --log-level DEBUG

# Logs en JSON (para agregadores)
python -m src.main --log-json --log-file logs/sonde-tracker.log
```

### Docker

```bash
cd deploy
docker compose up -d

# Ver logs
docker compose logs -f

# Parar
docker compose down
```

### systemd (Producción en Linux)

```bash
# 1. Crear usuario de servicio
sudo useradd -r -s /bin/false sonde-tracker

# 2. Instalar en /opt
sudo mkdir -p /opt/sonde-tracker
sudo cp -r src config /opt/sonde-tracker/
sudo chown -R sonde-tracker: /opt/sonde-tracker

# 3. Crear virtualenv en /opt
sudo -u sonde-tracker python -m venv /opt/sonde-tracker/.venv
sudo -u sonde-tracker /opt/sonde-tracker/.venv/bin/pip install -r /opt/sonde-tracker/requirements.txt

# 4. Copiar config y .env a /opt/sonde-tracker/config/
sudo cp config/config.yaml /opt/sonde-tracker/config/
sudo cp .env /opt/sonde-tracker/config/

# 5. Instalar servicio
sudo cp deploy/sonde-tracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sonde-tracker

# 6. Ver estado
sudo systemctl status sonde-tracker
journalctl -u sonde-tracker -f
```

---

## Lógica de Alertas

| Fase | Condición | Alerta Enviada |
|------|-----------|----------------|
| Tracking | Sonda entra en ~3× radio alerta (horizontal) | — |
| Inicio descenso | `ascent_rate < -0.5 m/s` Y aterrizaje previsto ≤ `alert_radius_km` | 🟡 **DESCENSO DETECTADO** |
| Aterrizaje inminente | Ya descendiendo + altitud < 2000 m + aterrizaje previsto ≤ radio | 🔴 **ATERRIZAJE INMINENTE** |

**Predicción de aterrizaje**: Extrapolación balística simple — asume que el vector de velocidad horizontal actual se mantiene constante hasta el suelo. Sin modelo atmosférico.

**Con `alert_once_per_sonde: true`** (por defecto): Solo la primera condición cumplida dispara alerta. Si el descenso empieza fuera del radio pero luego entra en radio mientras desciende, **no** hay segunda alerta.

---

## Ejemplos de Mensajes en Telegram

### 🟡 Descenso Detectado

```
📡 DESCENSO DETECTADO 🟡

📍 Sonda: ABC123 (RS41)
📡 Frecuencia: 403.200 MHz
📍 Posición actual: 40.12345, -3.67890
📏 Altitud: 12.5 km
⬇️ Tasa descenso: 5.2 m/s
🧭 Rumbo: 245°
💨 Vel. horizontal: 15.2 m/s
🎯 Dist. estimada aterrizaje: 18.3 km

🔗 Ver en sondehub.org
```

### 🔴 Aterrizaje Inminente

```
🎯 ATERRIZAJE INMINENTE 🔴

📍 Sonda: ABC123 (RS41)
📍 Posición: 40.13500, -3.65000
📏 Altitud: 1.2 km
🎯 Dist. estimada: 2.1 km

🔗 Ver en sondehub.org
```

### 🚀 Inicio del Servicio

```
🚀 Sonde Tracker iniciado

📍 Estación: 40.41680, -3.70380
📏 Altitud: 650 m
🎯 Radio alerta: 30 km
🔍 Filtros: Frecuencia: 400-406 MHz, Tipo: RS41
```

### 🛑 Parada del Servicio

```
🛑 Sonde Tracker detenido
```

---

## Pruebas

```bash
# Tests unitarios
pytest tests/ -v

# Linting
ruff check src/
black --check src/

# Type checking
mypy src/

# Probar notificación Telegram
python -m src.main --test-notify

# Probar conexión sondehub (espera 1 mensaje)
python -m src.main --once
```

---

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError` | Activa venv: `source .venv/bin/activate` |
| `FileNotFoundError: config.yaml` | Ejecuta `cp config/config.example.yaml config/config.yaml` |
| `Variable TELEGRAM_BOT_TOKEN not defined` | Verifica que `.env` existe y tiene los nombres correctos |
| `TelegramError: Unauthorized` | Token inválido o bot bloqueado |
| `TelegramError: Chat not found` | `chat_id` incorrecto; bot no está en el grupo/canal |
| No llegan alertas | Revisa `alert_radius_km`, filtros, y que haya sondas realmente en rango |
| Desconexiones WebSocket | Normal — se reconecta automáticamente con backoff exponencial |

---

## Archivos NO Cometer a Git

- `config/config.yaml` — contiene tu ubicación
- `.env` — contiene secretos de Telegram
- `.venv/` — entorno virtual
- `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`
- `logs/`, `dist/`, `build/`

Ver `.gitignore` para lista completa.

---

## Licencia

MIT — Ver archivo LICENSE.