"""
Network service module.
"""

import socket


class NetworkTester:
    """Network connectivity tester."""

    @staticmethod
    def test_connectivity(host: str, port: int, timeout: int = 5) -> bool:
        """Test network connectivity to host:port."""
        try:
            socket.create_connection((host, port), timeout=timeout)
            return True
        except (socket.timeout, socket.error, ConnectionRefusedError, OSError):
            return False
