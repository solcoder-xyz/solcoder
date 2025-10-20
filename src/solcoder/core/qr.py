"""ASCII QR rendering utilities."""

from __future__ import annotations

import io
from typing import Iterable

try:  # pragma: no cover - optional dependency
    import qrcode
    from qrcode import constants as qrcode_constants
    from qrcode.exceptions import DataOverflowError as _DataOverflowError
except ModuleNotFoundError:  # pragma: no cover - qrcode not installed
    qrcode = None  # type: ignore[assignment]
    qrcode_constants = None  # type: ignore[assignment]

    class _DataOverflowError(Exception):
        pass


class QRUnavailableError(RuntimeError):
    """Raised when QR rendering is unavailable."""


DataOverflowError = _DataOverflowError


def render_qr_ascii(data: str, *, invert: bool = False) -> str:
    """Return an ASCII-art QR code for `data`.

    The generated code uses dense blocks so that addresses remain readable in the CLI.
    Raises QRUnavailableError if the optional `qrcode` dependency is not installed.
    """

    if qrcode is None or qrcode_constants is None:  # pragma: no cover - dependency missing
        raise QRUnavailableError(
            "QR generation requires the 'qrcode' package. Install it to enable ASCII QR output."
        )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode_constants.ERROR_CORRECT_M,
        box_size=1,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.StringIO()
    qr.print_ascii(out=buffer, invert=invert)
    ascii_qr = buffer.getvalue().strip("\n")
    return ascii_qr


def format_qr_block(lines: Iterable[str]) -> str:
    """Indent QR code lines uniformly for nicer CLI formatting."""

    formatted = "\n".join(f"    {line}" for line in lines)
    return formatted


__all__ = ["render_qr_ascii", "format_qr_block", "QRUnavailableError", "DataOverflowError"]
