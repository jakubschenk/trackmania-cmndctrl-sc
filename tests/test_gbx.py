import asyncio
import struct
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from xmlrpc.client import dumps

from gbx_client import GBXClient


class TestGBXSend(unittest.IsolatedAsyncioTestCase):
    async def test_send_encodes_payload_with_header(self):
        client = GBXClient()
        client.writer = MagicMock()
        client.writer.drain = AsyncMock()

        # Resolve the future from a concurrent task so send() can return
        async def resolve():
            await asyncio.sleep(0.01)
            fut = client._pending.get(0x80000000)
            if fut:
                fut.set_result(True)

        asyncio.create_task(resolve())
        result = await client.send("TestMethod", "arg1")

        written = client.writer.write.call_args[0][0]
        size, hid = struct.unpack("<II", written[:8])
        payload = written[8:]
        self.assertEqual(hid, 0x80000000)
        self.assertEqual(len(payload), size)
        self.assertIn(b"TestMethod", payload)
        self.assertTrue(result)


class TestGBXReadLoop(unittest.IsolatedAsyncioTestCase):
    async def test_resolves_pending_futures_for_responses(self):
        client = GBXClient()

        # Build a response payload (handler_id >= 0x80000000)
        response = dumps(("result_value",), methodresponse=True).encode()
        header = struct.pack("<II", len(response), 0x80000000)

        client.reader = AsyncMock()
        client.reader.readexactly = AsyncMock(side_effect=[
            header,
            response,
            asyncio.IncompleteReadError(b"", 8),
        ])

        fut = asyncio.get_event_loop().create_future()
        client._pending[0x80000000] = fut

        with self.assertRaises(asyncio.IncompleteReadError):
            await client._read_loop(AsyncMock())

        self.assertEqual(fut.result(), "result_value")

    async def test_dispatches_callbacks_for_server_events(self):
        client = GBXClient()

        # Build a callback payload (handler_id < 0x80000000)
        callback_payload = dumps(("login1",), methodname="ManiaPlanet.PlayerConnect").encode()
        header = struct.pack("<II", len(callback_payload), 0x00000001)

        client.reader = AsyncMock()
        client.reader.readexactly = AsyncMock(side_effect=[
            header,
            callback_payload,
            asyncio.IncompleteReadError(b"", 8),
        ])

        callback = AsyncMock()

        with self.assertRaises(asyncio.IncompleteReadError):
            await client._read_loop(callback)

        # Let the spawned task run
        await asyncio.sleep(0.01)
        callback.assert_called_once()
        self.assertEqual(callback.call_args[0][0], "ManiaPlanet.PlayerConnect")


class TestGBXConnect(unittest.IsolatedAsyncioTestCase):
    @patch("gbx_client.asyncio.open_connection")
    async def test_validates_gbxremote_header(self, mock_conn):
        reader = AsyncMock()
        writer = MagicMock()
        mock_conn.return_value = (reader, writer)

        proto = b"GBXRemote 2"
        reader.readexactly = AsyncMock(side_effect=[
            struct.pack("<I", len(proto)),
            proto,
        ])

        client = GBXClient()
        await client.connect()
        self.assertIs(client.reader, reader)
        self.assertIs(client.writer, writer)

    @patch("gbx_client.asyncio.open_connection")
    async def test_rejects_bad_header(self, mock_conn):
        reader = AsyncMock()
        writer = MagicMock()
        mock_conn.return_value = (reader, writer)

        bad_proto = b"NotGBX"
        reader.readexactly = AsyncMock(side_effect=[
            struct.pack("<I", len(bad_proto)),
            bad_proto,
        ])

        client = GBXClient()
        with self.assertRaises(ConnectionError):
            await client.connect()


if __name__ == "__main__":
    unittest.main()
