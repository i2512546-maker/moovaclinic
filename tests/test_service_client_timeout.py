# Tests for ServiceClient timeout fix — do NOT simulate ServiceClient,
# instead patch requests.get/post/put/delete at module level.

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.service_client import ServiceClient


class ServiceClientTimeoutTest(unittest.TestCase):
    def setUp(self):
        self.client = ServiceClient("test", timeout=15)

    # (a) Passar timeout=5 no lanza TypeError y llega a requests con timeout=5
    @patch("shared.service_client.requests.get")
    def test_get_timeout_pasado_llega_a_requests(self, mock_get):
        # Que requests.get devuelva un objeto con .json() y .status_code
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        self.client.get("/api/endpoint", timeout=5)

        # Verify requests.get was called with timeout=5, NOT 15
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs.get("timeout"), 5,
                         "timeout=5 must be passed to requests.get, not self.timeout (15)")

    # (b) Sin timeout se usa self.timeout (15)
    @patch("shared.service_client.requests.get")
    def test_get_sin_timeout_usa_self_timeout(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        self.client.get("/api/endpoint")  # no timeout arg

        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs.get("timeout"), 15,
                         "sin timeout debe usar self.timeout (15)")

    # (c) Verify ServiceClient methods don't raise TypeError when called
    # with timeout arguments, by patching requests at module level and
    # checking the calls go through without error.
    @patch("shared.service_client.requests.get")
    @patch("shared.service_client.requests.post")
    def test_service_client_methods_accept_timeout_args(
            self, mock_post, mock_get):
        mock_get.return_value = MagicMock()
        mock_get.return_value.json.return_value = {"data": "ok"}
        mock_get.return_value.status_code = 200
        mock_post.return_value = MagicMock()
        mock_post.return_value.json.return_value = {"data": "created"}
        mock_post.return_value.status_code = 201

        # Llamadas reales a ServiceClient con timeout arguments
        # get con timeout=5
        self.client.get("/api/test", timeout=5)
        # post sin timeout (debe usar self.timeout=15)
        self.client.post("/api/test", json_data={})

        # If we reach here without exception, the methods accept the args
        self.assertTrue(mock_get.called or mock_post.called)


if __name__ == "__main__":
    unittest.main()
