"""Pure GBX/XML-RPC protocol client."""

import asyncio
import logging
import struct
from xmlrpc.client import dumps, loads

from config import RPC_HOST, RPC_PORT, RPC_USER, RPC_PASSWORD

log = logging.getLogger("cmnd/ctrl")


class GBXClient:
    def __init__(self):
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._handler_id = 0x80000000
        self._pending: dict[int, asyncio.Future] = {}

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(RPC_HOST, RPC_PORT)
        header = await self.reader.readexactly(4)
        size = struct.unpack_from("<I", header)[0]
        proto = await self.reader.readexactly(size)
        if b"GBXRemote" not in proto:
            raise ConnectionError(f"Bad GBX header: {proto}")
        log.info("Connected to %s:%s (%s)", RPC_HOST, RPC_PORT, proto.decode())

    async def send(self, method: str, *args) -> object:
        payload = dumps(args, method).encode()
        handler_id = self._handler_id
        self._handler_id += 1
        header = struct.pack("<II", len(payload), handler_id)
        self.writer.write(header + payload)
        await self.writer.drain()

        fut = asyncio.get_event_loop().create_future()
        self._pending[handler_id] = fut
        return await fut

    async def _read_loop(self, callback):
        while True:
            raw_header = await self.reader.readexactly(8)
            size, handler_id = struct.unpack("<II", raw_header)
            payload = await self.reader.readexactly(size)

            if handler_id >= 0x80000000:
                fut = self._pending.pop(handler_id, None)
                if fut and not fut.done():
                    try:
                        result, _ = loads(payload)
                        fut.set_result(result[0] if len(result) == 1 else result)
                    except Exception as e:
                        fut.set_exception(e)
            else:
                try:
                    params, method = loads(payload)
                    asyncio.create_task(callback(method, params))
                except Exception:
                    log.exception("Error parsing callback")

    async def authenticate(self):
        result = await self.send("Authenticate", RPC_USER, RPC_PASSWORD)
        if not result:
            raise ConnectionError("Authentication failed")
        log.info("Authenticated as %s", RPC_USER)

        await self.send("SetApiVersion", "2013-04-16")
        await self.send("EnableCallbacks", True)
        log.info("Callbacks enabled")

    async def chat_send(self, msg: str):
        await self.send("ChatSendServerMessage", msg)

    async def chat_send_to(self, msg: str, login: str):
        await self.send("ChatSendServerMessageToLogin", msg, login)

    async def chat_forward(self, text: str, sender: str, dest: str = ""):
        await self.send("ChatForwardToLogin", text, sender, dest)

    def close(self):
        if self.writer:
            self.writer.close()
