"""Cliente WebSocket para sondehub.org."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Callable, Awaitable
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import get_config, SondehubConfig
from .utils import SondeData, parse_sondehub_message

logger = logging.getLogger(__name__)

# Tipo para callback de mensajes
MessageHandler = Callable[[SondeData], Awaitable[None]]


class SondehubClient:
    """Cliente WebSocket para sondehub.org con reconexión automática."""

    def __init__(self, config: SondehubConfig | None = None):
        self.config = config or get_config().sondehub
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._handlers: list[MessageHandler] = []

    def add_handler(self, handler: MessageHandler) -> None:
        """Registra un handler para mensajes recibidos."""
        self._handlers.append(handler)

    def remove_handler(self, handler: MessageHandler) -> None:
        """Elimina un handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def _connect(self) -> websockets.WebSocketClientProtocol:
        """Establece conexión WebSocket."""
        url = self.config.ws_url
        logger.info(f"Conectando a sondehub: {url}")
        ws = await websockets.connect(
            url,
            ping_interval=self.config.ping_interval_sec,
            ping_timeout=10,
            close_timeout=10,
        )
        logger.info("Conexión establecida")
        return ws

    async def _handle_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Procesa mensajes entrantes."""
        async for message in ws:
            try:
                data = json.loads(message)
                sonde = parse_sondehub_message(data)
                if sonde:
                    await self._dispatch(sonde)
            except json.JSONDecodeError:
                logger.debug("Mensaje no JSON recibido")
            except Exception as e:
                logger.error(f"Error procesando mensaje: {e}")

    async def _dispatch(self, sonde: SondeData) -> None:
        """Envía sonda a todos los handlers registrados."""
        for handler in self._handlers:
            try:
                await handler(sonde)
            except Exception as e:
                logger.error(f"Error en handler: {e}")

    @retry(
        wait=wait_exponential(multiplier=1, min=5, max=300),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type((ConnectionClosed, WebSocketException, OSError)),
        reraise=True,
    )
    async def _run_with_reconnect(self) -> None:
        """Ejecuta el cliente con reconexión automática."""
        self._ws = await self._connect()
        try:
            await self._handle_messages(self._ws)
        finally:
            await self._ws.close()
            self._ws = None

    async def start(self) -> None:
        """Inicia el cliente (bloqueante hasta stop)."""
        self._running = True
        logger.info("Iniciando cliente sondehub...")
        await self._run_with_reconnect()

    async def stop(self) -> None:
        """Detiene el cliente."""
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info("Cliente sondehub detenido")


async def stream_sondes(
    handlers: list[MessageHandler],
    config: SondehubConfig | None = None
) -> None:
    """
    Función helper para streaming simple.

    Uso:
        async def mi_handler(sonde: SondeData):
            print(sonde)

        await stream_sondes([mi_handler])
    """
    client = SondehubClient(config)
    for h in handlers:
        client.add_handler(h)
    await client.start()