import base64
from hashlib import scrypt
import string
import secrets

ALPHABET = string.ascii_letters + string.digits
CISCO_BASE64_ENCODING_CHARS = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
STD_BASE64_ENCODING_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def type9_encode(data: bytes) -> str:
    encoding_translation_table = str.maketrans(
        STD_BASE64_ENCODING_CHARS,
        CISCO_BASE64_ENCODING_CHARS,
    )
    res = base64.b64encode(data).decode().translate(encoding_translation_table)

    # and strip off the trailing '='
    res = res[:-1]
    return res


def type9_decode(data: str) -> bytes:
    encoding_translation_table = str.maketrans(
        CISCO_BASE64_ENCODING_CHARS,
        STD_BASE64_ENCODING_CHARS,
    )
    # add back the trailing '='
    data += "=="
    res = data.translate(encoding_translation_table)
    res = base64.b64decode(res)
    return res


def encrypt_type9(unencrypted_password: str, salt: str | None = None) -> str:
    """Given an unencrypted password of Cisco Type 9 password, encypt it.

    Args:
        unencrypted_password: A password that has not been encrypted, and will be compared against.
        salt: a 14-character string that can be set by the operator. Defaults to random generated one.

    Returns:
        The encrypted password.

    Examples:
        >>> from netutils.password import encrypt_type9
        >>> encrypt_type9("123456")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
        >>> encrypt_type9("123456", "cvWdfQlRRDKq/U")
        "$9$cvWdfQlRRDKq/U$VFTPha5VHTCbSgSUAo.nPoh50ZiXOw1zmljEjXkaq1g"
    """

    if salt:
        if len(salt) != 14:
            raise ValueError("Salt must be 14 characters long.")
    else:
        # salt must always be a 14-byte-long printable string, often includes symbols
        salt = "".join(secrets.choice(CISCO_BASE64_ENCODING_CHARS) for _ in range(14))

    key = scrypt(unencrypted_password.encode(), salt=salt.encode(), n=2**14, r=1, p=1, dklen=32)

    # Cisco type 9 uses a different base64 encoding than the standard one, so we need to translate from
    # the standard one to the Cisco one.
    hash = type9_encode(key)

    return f"$9${salt}${hash}"

