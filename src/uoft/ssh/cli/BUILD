uoft_python_cli(
    description = "Custom SSH wrapper which automatically handles authentication and provides a keyboard shortcut to insert the enable password on the switch",
    author = "Alex Tremblay",
    author_email = "alex.tremblay@utoronto.ca",
    license = "MIT",
    url = "https://github.com/uoft-networking/tools/tree/main/src/uoft/ssh/cli",
    pex_kwargs = dict(
        dependencies = [
            # [[[cog tasks._coghelpers.compute_pants_dist_deps('uoft/ssh/cli')]]]
            "src/uoft/core:dist",
            "src/uoft/ssh:dist",
            # [[[end]]]
        ]
    ),
)