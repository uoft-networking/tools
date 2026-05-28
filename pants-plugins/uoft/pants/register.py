from . import synthetic_targets, custom_setup_kwargs, uv, ripgrep


def rules():
    return [
        *synthetic_targets.rules(),
        *custom_setup_kwargs.rules(),
        *uv.rules(),
        *ripgrep.rules(),
    ]
