from __future__ import annotations

from typing import Any

import httpx
import pytest

from solcoder.solana.rpc import SolanaRPCClient, SolanaRPCError


def make_response(status_code: int, json_data: dict[str, Any]) -> httpx.Response:
    request = httpx.Request("POST", "https://rpc.example.com")
    return httpx.Response(status_code=status_code, json=json_data, request=request)


def test_get_balance_success() -> None:
    def request(_url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:  # noqa: ARG001
        return make_response(200, {"jsonrpc": "2.0", "result": {"value": 2_500_000_000}, "id": json["id"]})

    client = SolanaRPCClient(endpoint="https://rpc.example.com", _request=request)

    balance = client.get_balance("TestPubkey")

    assert balance == 2.5


def test_get_balance_http_error() -> None:
    def request(_url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:  # noqa: ARG001
        return make_response(500, {"error": {"message": "fail"}})

    client = SolanaRPCClient(endpoint="https://rpc.example.com", _request=request)

    with pytest.raises(SolanaRPCError):
        client.get_balance("TestPubkey")


def test_get_balance_rpc_error() -> None:
    def request(_url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:  # noqa: ARG001
        return make_response(200, {"jsonrpc": "2.0", "error": {"message": "bad pubkey"}, "id": 1})

    client = SolanaRPCClient(endpoint="https://rpc.example.com", _request=request)

    with pytest.raises(SolanaRPCError):
        client.get_balance("BadPubkey")
