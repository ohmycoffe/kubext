import hashlib

MIN_DYNAMIC_PORT = 49152
MAX_DYNAMIC_PORT = 65535


def get_deterministic_port(
    service: str,
    namespace: str,
    service_port: int,
):
    key = f"{namespace}/{service}:{service_port}"
    h = hashlib.sha256(key.encode()).hexdigest()
    value = int(h[:8], base=16)  # first 32 bits = 8 hex chars * 4 bits/char
    return MIN_DYNAMIC_PORT + (value % (MAX_DYNAMIC_PORT - MIN_DYNAMIC_PORT + 1))
