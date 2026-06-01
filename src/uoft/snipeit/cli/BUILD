uoft_python_cli(
    description = "Collection of tools to interact with SnipeIT, currently focused around Access Point provisioning, but will probably be expanded to support all asset types in general.",
    author = "Alex Tremblay",
    author_email = "alex.tremblay@utoronto.ca",
    license = "MIT",
    url = "https://github.com/uoft-networking/tools/tree/main/src/uoft/snipeit/cli",
    pex_kwargs = dict(
        dependencies = [
            # [[[cog tasks._coghelpers.compute_pants_dist_deps('uoft/snipeit/cli')]]]
            "src/uoft/core:dist",
            "src/uoft/snipeit:dist",
            # [[[end]]]
        ]
    ),
)