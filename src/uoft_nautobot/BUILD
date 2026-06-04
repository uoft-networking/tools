uoft_python_lib(
    # These deps have to be manually specified because they can't be inferred
    # they're not explicitly imported by any of our code, but are needed at runtime
    sources_kwargs={
        "dependencies": [ 
            '//:py-deps#python-dotenv',
            '//:py-deps#python-box',
            '//:py-deps#nautobot_ssot',
            '//:py-deps#nautobot_golden_config',
            '//:py-deps#nautobot-device-onboarding',
            '//:py-deps#ptpython',
            '//:py-deps#napalm',
            '//:py-deps#napalm-aruba-cx',
            '//:py-deps#django-debug-toolbar',
        ],
    },
    entry_points={
        "console_scripts": [
            "nautobot = nautobot.core.cli:main",
        ],
    },
)

pex_binary(
    name="pex",
    entry_point="nautobot.core.cli:main",
    dependencies=[
        ":dist", 
        # [[[cog tasks._coghelpers.compute_pants_dist_deps('uoft_nautobot')]]]
        "src/uoft/aruba:dist",
        "src/uoft/bluecat:dist",
        "src/uoft/core:dist",
        "src/uoft/librenms:dist",
        "src/uoft/scripts:dist",
        "src/uoft/ssh:dist",
        # [[[end]]]
    ],
    include_tools=True,
    execution_mode="venv",
    output_path="uoft_nautobot.pex",
)