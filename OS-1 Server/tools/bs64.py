import base64
from io import BytesIO

from PIL import Image


def bytes2bs64(byte_data: bytes) -> str:
    return base64.b64encode(byte_data).decode("utf-8")


def bs642bytes(bs64_data: str) -> bytes:
    return base64.b64decode(bytes(bs64_data, encoding="utf-8"))


def bs642bytes_with_padding(bs64_data: str) -> bytes:
    bs64_data = bytes(bs64_data, encoding="utf-8")
    missing_padding = len(bs64_data) % 4
    if missing_padding:
        bs64_data += b"=" * (4 - missing_padding)
    return base64.b64decode(bs64_data)


def image2bs64(image: Image, format="JPEG") -> str:
    buffer = BytesIO()
    image.save(buffer, format=format)
    byte_data = buffer.getvalue()
    return bytes2bs64(byte_data)
