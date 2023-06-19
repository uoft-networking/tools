from textwrap import indent, dedent
from typing import Literal
from hashlib import shake_128
from django_jinja import library
from . import Settings
from .golden_config import encrypt_type9, type9_encode


@library.filter
def reindent(text: str, spaces: int):
    """
    dedents a block of text from its current indentation level to zero,
    and then indents that block of text by a given number of spaces
    """
    return indent(dedent(str(text)), " " * spaces)


@library.filter
def derive_type9_password(sw, password_variant: Literal['enable', 'admin']):
    """Derives a type 9 password from a given switch object and a password variant"""
    s = Settings.from_cache()
    if password_variant == 'enable':
        password = s.ssh.enable_secret.get_secret_value()
    elif password_variant == 'admin':
        password = s.ssh.admin.password.get_secret_value()
    else:
        raise ValueError(f"Invalid password variant: {password_variant}")
    
    # convert variable-length switch name to 14 bytes of cisco-compatible salt
    salt = type9_encode(shake_128(sw.hostname.encode()).digest(14))[:14]
    return encrypt_type9(password, salt=salt)


@library.filter
def debug_jinja(obj):
    import inspect
    stack = inspect.stack()
    def get_render_frame():
        for frame in stack:
            if frame.function == "render" and 'environment.py' in frame.filename:
                return frame
        return None
    frame = get_render_frame()
    assert frame is not None
    f_locals = frame.frame.f_locals
    template = f_locals["self"]
    context = f_locals["ctx"]
    data = f_locals["kwargs"]
    filters = template.environment.filters
    breakpoint()
    return obj
