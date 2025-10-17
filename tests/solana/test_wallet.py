
import json
import os
from pathlib import Path

import pytest

from solcoder.solana.wallet import WalletError, WalletManager


def read_payload(path: Path) -> dict:
    return json.loads(path.read_text())


def test_create_wallet_persists_with_permissions(tmp_path: Path) -> None:
    manager = WalletManager(keys_dir=tmp_path / "keys")

    status, mnemonic = manager.create_wallet("secret-pass", force=True)

    assert status.exists is True
    assert status.is_unlocked is True
    assert status.public_key is not None
    assert len(mnemonic.split()) in {12, 24}
    payload = read_payload(manager.wallet_path)
    assert payload["public_key"] == status.public_key
    assert os.stat(manager.wallet_path).st_mode & 0o777 in {0o600, 0o666}  # windows may ignore chmod


def test_unlock_and_export_round_trip(tmp_path: Path) -> None:
    manager = WalletManager(keys_dir=tmp_path / "keys")
    status, _ = manager.create_wallet("hunter2", force=True)
    manager.lock_wallet()

    status = manager.unlock_wallet("hunter2")
    assert status.is_unlocked is True
    exported = manager.export_wallet("hunter2")

    restored = WalletManager(keys_dir=tmp_path / "keys_restore")
    restored_status, restored_mnemonic = restored.restore_wallet(exported, "hunter3", overwrite=True)
    assert restored_mnemonic is None
    restored_status = restored.unlock_wallet("hunter3")
    assert restored_status.public_key == status.public_key


def test_unlock_with_bad_passphrase(tmp_path: Path) -> None:
    manager = WalletManager(keys_dir=tmp_path / "keys")
    manager.create_wallet("correct", force=True)
    manager.lock_wallet()

    with pytest.raises(WalletError):
        manager.unlock_wallet("wrong-pass")


def test_restore_accepts_base58(tmp_path: Path) -> None:
    manager = WalletManager(keys_dir=tmp_path / "keys")
    original = WalletManager(keys_dir=tmp_path / "seed")
    status, _ = original.create_wallet("open-sesame", force=True)
    exported = original.export_wallet("open-sesame")
    secret_bytes = bytes(json.loads(exported))
    base58_secret = original._b58encode(secret_bytes)  # type: ignore[attr-defined]

    restored_status, restored_mnemonic = manager.restore_wallet(base58_secret, "passphrase", overwrite=True)

    assert restored_status.public_key == status.public_key
    assert restored_mnemonic is None


def test_get_mnemonic_returns_phrase(tmp_path: Path) -> None:
    manager = WalletManager(keys_dir=tmp_path / "keys")
    _, mnemonic = manager.create_wallet("secret", force=True)
    manager.lock_wallet()

    retrieved = manager.get_mnemonic("secret")

    assert retrieved == mnemonic


def test_get_mnemonic_missing_phrase(tmp_path: Path) -> None:
    manager = WalletManager(keys_dir=tmp_path / "keys")
    other = WalletManager(keys_dir=tmp_path / "other")
    status, _ = manager.create_wallet("seed", force=True)
    exported = manager.export_wallet("seed")
    other.restore_wallet(exported, "newpass", overwrite=True)

    with pytest.raises(WalletError):
        other.get_mnemonic("newpass")
