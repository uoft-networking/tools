from textwrap import indent, dedent
from django_jinja import library


@library.filter
def reindent(text: str, spaces: int):
    """
    dedents a block of text from its current indentation level to zero,
    and then indents that block of text by a given number of spaces
    """
    return indent(dedent(str(text)), " " * spaces)


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
