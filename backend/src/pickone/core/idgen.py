from __future__ import annotations

import os
import time
import uuid


def new_uuid() -> uuid.UUID:
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = os.urandom(10)

    b = bytearray(16)
    b[0:6] = ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand[0] & 0x0F)
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)
    b[9:16] = rand[3:10]
    return uuid.UUID(bytes=bytes(b))
