# Sonde Tracker

Monitoriza radiosondas de [sondehub.org](https://sondehub.org) y envía notificaciones por Telegram cuando una sonda está descendiendo y aterrizará dentro de un radio configurable.

## Características

- 📡 Conexión WebSocket a sondehub.org para datos en tiempo real
- 🎯 Filtrado por distancia (radio configurable, por defecto 30 km)
- 📉 Detección automática de fase de descenso
- 📱 Notificaciones por Telegram Bot
- ⚙️ Configuración mediante archivo YAML + variables de entorno
- 🐳 Listo para Docker / systemd

## Instalación rápida

```bash
# Clonar y entrar
git clone <tu-repo>
cd sonde-tracker

# Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copiar y editar configuración
cp config/config.example.yaml config/config.yaml
# Edita config/config.yaml con tus datos
```

## Configuración

Edita `config/config.yaml`:

```yaml
# Tu ubicación (obtener en: https://www.latlong.net/)
location:
  latitude: 40.4168
  longitude: -3.7038
  altitude_m: 650

# Radio de alerta en kilómetros
alert_radius_km: 30

# Telegram Bot
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"  # Se lee de variable de entorno
  chat_id: "${TELEGRAM_CHAT_ID}"

# Opcional: filtro por frecuencia (MHz) o tipo de sonda
filters:
  # frequency_mhz: [400, 406]
  # sonde_type: "RS41"
```

**Variables de entorno** (en `.env` o exportadas):
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="-1001234567890"
```

## Uso

```bash
# Ejecutar una vez (modo prueba)
python -m src.main --once

# Ejecutar como daemon (producción)
python -m src.main

# Con Docker
docker compose up -d
```

## Despliegue como servicio (systemd)

```bash
sudo cp deploy/sonde-tracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sonde-tracker
```

## Estructura del proyecto

```
sonde-tracker/
├── config/
│   ├── config.example.yaml    # Plantilla de configuración
│   └── config.yaml            # Tu configuración (no versionar)
├── deploy/
│   ├── sonde-tracker.service  # Unit file systemd
│   └── Dockerfile
├── src/
│   ├── __init__.py
│   ├── main.py                # Punto de entrada
│   ├── config.py              # Carga de configuración
│   ├── sondehub.py            # Cliente WebSocket sondehub
│   ├── tracker.py             # Lógica de tracking y alertas
│   ├── notifier.py            # Notificaciones Telegram
│   └── utils.py               # Utilidades geográficas
├── tests/
│   ├── test_utils.py
│   └── test_tracker.py
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

## API sondehub.org

Usa el endpoint WebSocket público: `wss://sondehub.org/ws`

Documentación: https://github.com/projecthorus/sondehub

## Licencia

MIT