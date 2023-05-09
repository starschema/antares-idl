from cryptography.hazmat.primitives import serialization


def str2bool(val):
    """Convert a string to a boolean value."""
    if not isinstance(val, str):
        raise ValueError(f"invalid value type {type(val)}")

    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        parsed_val = True
    elif val in ("n", "no", "f", "false", "off", "0"):
        parsed_val = False
    else:
        raise ValueError(f"invalid truth value {val}")

    return parsed_val


def read_text_file(filename):
    """Read a text file and return its contents."""
    with open(filename, "r", encoding="utf-8") as f:
        contents = f.read()
    return contents


def pem_keypair_to_private_key_no_headers(pem_keypair, password=None):
    """Convert a PEM keypair to a private key."""
    keypair_b = bytearray()
    keypair_b.extend(map(ord, pem_keypair))
    pem = serialization.load_pem_private_key(
        keypair_b,
        password=password,
    )
    private_key = "".join(
        pem.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("utf-8")
        .split("\n")[1:-2]
    )
    return private_key
