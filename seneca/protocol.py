"""."""
import asyncio
import logging
#import hashlib
#import signal
import bitcoin.messages


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MY_SUBVERSION = b"/bitcoinlib:0.2/"


class BitcoinP2P(asyncio.StreamReaderProtocol):
    """."""

    def __init__(self, remote_addr, remote_port, net_magic,
                 sub_ver=MY_SUBVERSION):
        super().__init__(asyncio.StreamReader(), self.version_handshake)

        self._remote_port = remote_port
        self._remote_addr = remote_addr

        self._net_magic = net_magic
        self._last_message_sent = None
        self._sub_ver = sub_ver
        self._min_proto_version = bitcoin.MIN_PROTO_VERSION
        self._their_ver = None
        self._acked_ver = None

        self._version_handshake_done = asyncio.Future()
        self._connection_closed = asyncio.Future()

        self._reader_task = asyncio.Task(self.start_reader_task())

    def connection_lost(self, exc):
        """."""
        super().connection_lost(exc)

        self._stream_writer.write_eof()
        self._stream_writer.close()

        # Do some Bitcoin node specific clean up.
        self._connection_closed.set_result(True)
        self._reader_task.cancel()

    @asyncio.coroutine
    def start_reader_task(self):
        """."""
        # Pause till we exchange version information with our peer.
        yield from self._version_handshake_done

        while not self._connection_closed.done():
            # read message header, version, use call soon for callback
            try:
                pass
            except asyncio.IncompleteReadError:
                pass

    @asyncio.coroutine
    def version_handshake(self, reader, writer):
        """Exchange version information with our new client.

        This coroutine will be called by `asyncio.StreamReaderProtocol` when
        the connection is first made. After our simple handshake is complete,
        we'll signal our reader task to start processing messages via future.
        """

        version_message = bitcoin.messages.msg_version()
        version_message.addrTo.ip = self._remote_addr
        version_message.addrTo.port = self._remote_addr
        version_message.addrFrom.ip = "0.0.0.0"
        version_message.addrFrom.port = 0
        version_message.strSubVer = self._sub_ver

        yield from self.send_message(version_message)

        remote_version_message = yield from self._parse_next_message()

        self._their_ver = min(bitcoin.PROTO_VERSION,
                              remote_version_message.nVersion)

        # If we don't support this peer's version, then close the connection.
        if self._their_ver < self._min_proto_version:
            logger.debug("Peer's version is obsolete: %d", self._session_ver)
            self.connection_lost(Exception)
            return

        # Otherwise, ACK the version message, and let's request some more
        # addresses.
        yield from self.send_message(bitcoin.message.msg_verack(self._their_ver))
        yield from self.send_message(bitcoin.message.msg_getaddr(self._their_ver))
