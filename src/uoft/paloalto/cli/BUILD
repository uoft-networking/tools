uoft_python_cli(
    description = "CLI and API to work with Paloalto products (NSM, etc)",
    author = "Alex Tremblay",
    author_email = "alex.tremblay@utoronto.ca",
    license = "MIT",
    url = "https://github.com/uoft-networking/tools/tree/main/src/uoft/paloalto/cli",
    pex_kwargs = dict(
        dependencies = [
            # [[[cog tasks._coghelpers.compute_pants_dist_deps('uoft/paloalto/cli')]]]
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
