import os
import tempfile
from typing import Tuple


def save_upload_to_temp(file_bytes: bytes, suffix: str = '.png') -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'wb') as f:
        f.write(file_bytes)
    return path
