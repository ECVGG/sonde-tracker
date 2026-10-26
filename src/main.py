#!/usr/bin/env python3
"""Punto de entrada principal - Sonde Tracker."""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .config import load_config, get_config, reload_config
from .sondehub import SondehubClient
from .tracker import SondeTracker
from .notifier import TelegramNotifier
from .utils import SondeData

console = Console()


def setup_logging(level: str = "INFO", json_format: bool = False, log_file: str = "") -> None:
    """Configura logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = []
    if json_format:
        import json_logging
        json_logging.init_non_web()
        handlers.append(logging.StreamHandler())
    else:
        handlers.append(RichHandler(console=console, rich_tracebacks=True))

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    # Reducir ruido de librerías
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


class SondeTrackerApp:
    """Aplicación principal."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.tracker = SondeTracker()
        self.notifier = TelegramNotifier()
        self.client = SondehubClient(self.config.sondehub)
        self._shutdown = False

    async def initialize(self) -> None:
        """Inicializa componentes."""
        # Conectar tracker con notifier
        self.tracker.set_alert_callback(self._on_alert)

        # Registrar handler en cliente sondehub
        self.client.add_handler(self.tracker.process_sonde)

        # Test de notificación al inicio
        if self.config.alerts.notify_on_descent_start or self.config.alerts.notify_on_landing:
            await self.notifier.send_startup_message()

    async def _on_alert(
        self,
        tracked,
        alert_type: str,
        distance_km: float | None
    ) -> None:
        """Callback de alertas del tracker."""
        await self.notifier.send_alert(tracked, alert_type, distance_km)

    async def run_once(self) -> None:
        """Ejecución única (para testing)."""
        console.print("[yellow]Modo --once: conectando, esperando 1 mensaje...[/yellow]")

        async def one_shot_handler(sonde: SondeData):
            console.print(f"[green]Recibido:[/green] {sonde.serial} @ {sonde.altitude_m:.0f}m")
            await self.tracker.process_sonde(sonde)
            # Parar tras primer mensaje procesado
            await self.client.stop()

        self.client.add_handler(one_shot_handler)
        await self.client.start()

    async def run_forever(self) -> None:
        """Ejecución continua (producción)."""
        console.print("[green]Sonde Tracker iniciado[/green]")
        console.print(f"[cyan]Estación:[/cyan] {self.config.location.latitude:.5f}, {self.config.location.longitude:.5f}")
        console.print(f"[cyan]Radio alerta:[/cyan] {self.config.alert_radius_km} km")

        # Manejo de señales
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_shutdown)

        try:
            await self.client.start()
        finally:
            await self.shutdown()

    def _signal_shutdown(self) -> None:
        console.print("\n[yellow]Señal de parada recibida...[/yellow]")
        self._shutdown = True

    async def shutdown(self) -> None:
        """Limpieza al cerrar."""
        console.print("[yellow]Cerrando...[/yellow]")
        await self.notifier.send_shutdown_message()
        await self.client.stop()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Sonde Tracker - Alertas radiosondas Telegram")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Ruta a config.yaml (default: config/config.yaml)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecutar una vez y salir (test)"
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Enviar notificación de prueba y salir"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de log"
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Logs en formato JSON"
    )
    args = parser.parse_args()

    # Cargar config primero para obtener nivel de log
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    # Setup logging
    setup_logging(
        level=args.log_level,
        json_format=args.log_json,
        log_file=config.logging.file
    )

    app = SondeTrackerApp(args.config)
    await app.initialize()

    if args.test_notify:
        ok = await app.notifier.send_test_message()
        return 0 if ok else 1

    if args.once:
        await app.run_once()
    else:
        await app.run_forever()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)