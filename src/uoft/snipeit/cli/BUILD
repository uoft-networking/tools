uoft_python_cli(
    description = "Collection of tools to interact with SnipeIT, currently focused around Access Point provisioning, but will probably be expanded to support all asset types in general.",
    author = "Alex Tremblay",
    author_email = "alex.tremblay@utoronto.ca",
    license = "MIT",
    url = "https://github.com/uoft-networking/tools/tree/main/src/uoft/snipeit/cli",
    pex_kwargs = dict(
        dependencies = [
            # [[[cog tasks._coghelpers.compute_pants_dist_deps('uoft/snipeit/cli')]]]
            "src/uoft/aruba/cli:dist",
            "src/uoft/aruba:dist",
            "src/uoft/bluecat:dist",
            "src/uoft/core:dist",
            "src/uoft/librenms:dist",
            "src/uoft/paloalto:dist",
            "src/uoft/scripts:dist",
            "src/uoft/ssh:dist",
            "src/uoft_nautobot:dist",
            # [[[end]]]
        ]
    ),
)