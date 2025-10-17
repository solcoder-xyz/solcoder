"""Wallet management for SolCoder."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from mnemonic import Mnemonic

from solcoder.core import DEFAULT_CONFIG_DIR

PBKDF_ITERATIONS = 390_000
KEY_FILENAME = "default_wallet.json"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MNEMONIC_STRENGTH = 256
MNEMONIC_WORD_COUNTS = {12, 15, 18, 21, 24}


class WalletError(RuntimeError):
    """Raised when wallet operations fail."""


@dataclass
class WalletStatus:
    """Represents the current wallet state."""

    exists: bool
    public_key: str | None
    is_unlocked: bool
    wallet_path: Path

    @property
    def masked_address(self) -> str:
        if not self.public_key:
            return "---"
        return f"{self.public_key[:4]}…{self.public_key[-4:]}"


@dataclass
class DecryptedPayload:
    """Represents decrypted wallet material."""

    private_key: bytes
    mnemonic: str | None


class WalletManager:
    """Handles secure storage and unlocking of Solana keypairs."""

    def __init__(self, keys_dir: Path | None = None) -> None:
        self.keys_dir = keys_dir or (DEFAULT_CONFIG_DIR / "keys")
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.wallet_path = self.keys_dir / KEY_FILENAME
        self._unlocked_key: ed25519.Ed25519PrivateKey | None = None
        self._cached_public_key: str | None = None
        self._mnemonic = Mnemonic("english")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def wallet_exists(self) -> bool:
        return self.wallet_path.exists()

    def status(self) -> WalletStatus:
        return WalletStatus(
            exists=self.wallet_exists(),
            public_key=self._cached_public_key or self._load_public_key_safely(),
            is_unlocked=self._unlocked_key is not None,
            wallet_path=self.wallet_path,
        )

    def create_wallet(self, passphrase: str, *, force: bool = False) -> tuple[WalletStatus, str]:
        if self.wallet_exists() and not force:
            raise WalletError("Wallet already exists. Use force=True to overwrite.")

        mnemonic = self._mnemonic.generate(strength=MNEMONIC_STRENGTH)
        private_key_bytes = self._derive_private_from_mnemonic(mnemonic)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        secret_bytes = self._serialize_private_key(private_key)
        public_key_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        public_key = self._b58encode(public_key_raw)
        payload = self._encrypt_payload(secret_bytes, passphrase, public_key=public_key, mnemonic=mnemonic)
        self._write_payload(payload)
        self._set_permissions()
        self._unlocked_key = private_key
        self._cached_public_key = public_key
        return self.status(), mnemonic

    def restore_wallet(
        self,
        secret: str,
        passphrase: str,
        *,
        overwrite: bool = False,
    ) -> tuple[WalletStatus, str | None]:
        if self.wallet_exists() and not overwrite:
            raise WalletError("Wallet already exists. Pass overwrite=True to replace it.")

        mnemonic: str | None = None
        if self._looks_like_mnemonic(secret):
            mnemonic_candidate = " ".join(secret.strip().lower().split())
            if not self._mnemonic.check(mnemonic_candidate):
                raise WalletError("Invalid recovery phrase checksum.")
            private_key_bytes = self._derive_private_from_mnemonic(mnemonic_candidate)
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            mnemonic = mnemonic_candidate
        else:
            secret_bytes = self._parse_secret_input(secret)
            if len(secret_bytes) not in {32, 64}:
                raise WalletError("Secret key must be 32 or 64 bytes.")
            private_bytes = secret_bytes[:32]
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
            if len(secret_bytes) == 64:
                public_component = secret_bytes[32:]
                derived_public = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                if public_component != derived_public:
                    raise WalletError("Provided public key does not match private key.")

        secret_bytes_normalized = self._serialize_private_key(private_key)
        public_key_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        public_key = self._b58encode(public_key_raw)
        payload = self._encrypt_payload(secret_bytes_normalized, passphrase, public_key=public_key, mnemonic=mnemonic)
        self._write_payload(payload)
        self._set_permissions()
        self._unlocked_key = None
        self._cached_public_key = public_key
        return self.status(), mnemonic

    def unlock_wallet(self, passphrase: str) -> WalletStatus:
        if not self.wallet_exists():
            raise WalletError("No wallet found. Run /wallet create first.")
        payload = self._decrypt_payload(passphrase)
        private_bytes = payload.private_key[:32]
        self._unlocked_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
        public_key = self._b58encode(self._unlocked_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        self._cached_public_key = public_key
        return self.status()

    def lock_wallet(self) -> WalletStatus:
        self._unlocked_key = None
        return self.status()

    def export_wallet(self, passphrase: str) -> str:
        if not self.wallet_exists():
            raise WalletError("No wallet to export.")
        payload = self._decrypt_payload(passphrase)
        return json.dumps(list(payload.private_key))

    def get_mnemonic(self, passphrase: str) -> str:
        payload = self._decrypt_payload(passphrase)
        if not payload.mnemonic:
            raise WalletError("Recovery phrase not available for this wallet.")
        return payload.mnemonic

    def get_private_key(self) -> ed25519.Ed25519PrivateKey:
        if self._unlocked_key is None:
            raise WalletError("Wallet is locked.")
        return self._unlocked_key

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _encrypt_payload(
        self,
        secret: bytes,
        passphrase: str,
        *,
        public_key: str,
        mnemonic: str | None,
    ) -> dict[str, Any]:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        aes_key = self._derive_key(passphrase, salt)
        payload_data = json.dumps(
            {
                "private_key": base64.b64encode(secret).decode("ascii"),
                "mnemonic": mnemonic,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        ciphertext = AESGCM(aes_key).encrypt(nonce, payload_data, associated_data=None)
        return {
            "public_key": public_key,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "salt": base64.b64encode(salt).decode("ascii"),
            "iterations": PBKDF_ITERATIONS,
            "created_at": datetime.now(UTC).isoformat(),
        }

    def _decrypt_payload(self, passphrase: str) -> DecryptedPayload:
        data = self._read_payload()
        salt = base64.b64decode(data["salt"])
        nonce = base64.b64decode(data["nonce"])
        ciphertext = base64.b64decode(data["ciphertext"])
        aes_key = self._derive_key(passphrase, salt)
        try:
            plaintext = AESGCM(aes_key).decrypt(nonce, ciphertext, associated_data=None)
        except Exception as exc:  # noqa: BLE001
            raise WalletError("Invalid passphrase for wallet.") from exc

        try:
            decoded = json.loads(plaintext.decode("utf-8"))
            private_key_b64 = decoded["private_key"]
            mnemonic = decoded.get("mnemonic")
            secret_bytes = base64.b64decode(private_key_b64)
            return DecryptedPayload(private_key=secret_bytes, mnemonic=mnemonic)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Backwards compatibility for legacy payloads that stored raw bytes
            return DecryptedPayload(private_key=plaintext, mnemonic=None)

    def _parse_secret_input(self, value: str) -> bytes:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list) and all(isinstance(item, int) for item in parsed):
                return bytes(parsed)
        except json.JSONDecodeError:
            pass
        try:
            return self._b58decode(value)
        except WalletError:
            pass
        raise WalletError("Unable to parse secret key input.")

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.wallet_path.write_text(json.dumps(payload, indent=2))

    def _read_payload(self) -> dict[str, Any]:
        if not self.wallet_exists():
            raise WalletError("Wallet not initialized.")
        return json.loads(self.wallet_path.read_text())

    def _set_permissions(self) -> None:
        try:
            os.chmod(self.wallet_path, 0o600)
        except PermissionError:
            # Ignore on platforms without chmod support (e.g., Windows)
            pass

    def _load_public_key_safely(self) -> str | None:
        if not self.wallet_exists():
            return None
        try:
            payload = self._read_payload()
            return payload.get("public_key")
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _serialize_private_key(private_key: ed25519.Ed25519PrivateKey) -> bytes:
        private_bytes = private_key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return private_bytes + public_bytes

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF_ITERATIONS,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def _derive_private_from_mnemonic(self, mnemonic: str) -> bytes:
        seed = self._mnemonic.to_seed(mnemonic, passphrase="")
        return seed[:32]

    def _looks_like_mnemonic(self, candidate: str) -> bool:
        words = candidate.strip().lower().split()
        if len(words) not in MNEMONIC_WORD_COUNTS:
            return False
        return all(word in self._mnemonic.wordlist for word in words)

    @staticmethod
    def _b58encode(data: bytes) -> str:
        num = int.from_bytes(data, "big")
        if num == 0:
            return "1" * len(data)

        encoded = ""
        while num > 0:
            num, remainder = divmod(num, 58)
            encoded = BASE58_ALPHABET[remainder] + encoded

        zeros = len(data) - len(data.lstrip(b"\x00"))
        return ("1" * zeros) + encoded

    @staticmethod
    def _b58decode(value: str) -> bytes:
        num = 0
        for char in value:
            try:
                num = num * 58 + BASE58_ALPHABET.index(char)
            except ValueError as exc:
                raise WalletError("Invalid base58 character in secret.") from exc

        full_bytes = num.to_bytes((num.bit_length() + 7) // 8, "big")
        zeros = len(value) - len(value.lstrip("1"))
        return b"\x00" * zeros + full_bytes


__all__ = [
    "WalletManager",
    "WalletStatus",
    "WalletError",
]
