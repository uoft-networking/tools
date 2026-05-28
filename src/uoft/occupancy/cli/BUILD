uoft_python_cli(
    description = "Occupancy tracking",
    author = "Kyle Fozo",
    author_email = "kyle.fozo@utoronto.ca",
    license = "MIT",
    url = "https://github.com/uoft-networking/tools/tree/main/src/uoft/occupancy/cli",
    pex_kwargs = dict(
        dependencies = [
            # [[[cog tasks._coghelpers.compute_pants_dist_deps('uoft/occupancy/cli')]]]
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
