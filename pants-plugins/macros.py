def uoft_python_lib(dist_kwargs: dict | None = None, sources_kwargs: dict | None = None, **kwargs):
    """A convenience macro for defining lib and dist targets in uoft projects."""

    resources(name="res", sources=["**/*", "!**/*.py", "!tests/**/*", "!BUILD*"])

    sources_kwargs = sources_kwargs or {}
    sources_kwargs.setdefault("dependencies", []).append(":res")

    python_sources(name="lib", sources=["**/*.py", "!tests/**/*.py", "!cli/**/*.py"], **sources_kwargs)
    python_tests(name="tests", sources=["tests/**/*.py", "!**/conftest.py"])
    python_test_utils(name="test_utils", sources=["tests/**/conftest.py"])

    dist_kwargs = dist_kwargs or {}
    dist_kwargs.setdefault("dependencies", []).append(":lib")

    python_distribution(
        name="dist",
        provides=python_artifact(**kwargs),
        **dist_kwargs,
    )


def uoft_python_cli(
    dist_kwargs: dict | None = None, sources_kwargs: dict | None = None, pex_kwargs: dict | None = None, **kwargs
):
    """A convenience macro for defining lib, dist, pex, and scie targets in uoft projects that are CLIs."""
    # need to derive cli name (eg uoft-aruba) and module path (eg uoft.aruba.cli) from path (eg src/uoft/aruba/cli)
    path = build_file_dir()
    path = str(path).partition("src/")[2]  # ex: uoft/aruba/cli
    assert path.rpartition("/")[2] == "cli", (
        "This macro should only be used in BUILD files in a cli/ submodule directory"
    )
    mod_path = path.replace("/", ".")  # ex: uoft.aruba.cli
    file_name = path.replace("/", "_")  # ex: uoft_aruba_cli
    cli_name = path.rpartition("/")[0].replace("/", "-")  # ex: uoft-aruba

    resources(name="res", sources=["**/*", "!**/*.py", "!BUILD*"])

    sources_kwargs = sources_kwargs or {}
    sources_kwargs.setdefault("dependencies", []).append(":res")

    python_sources(
        name="lib",
        sources=[
            "**/*.py",
        ],
        **sources_kwargs,
    )

    dist_kwargs = dist_kwargs or {}
    dist_kwargs.setdefault("dependencies", []).append(":lib")
    dist_kwargs.setdefault("entry_points", {}).setdefault("console_scripts", {})[cli_name] = f"{mod_path}.__main__:cli"

    python_distribution(
        name="dist",
        provides=python_artifact(name=mod_path, **kwargs),
        **dist_kwargs,
    )

    pex_kwargs = pex_kwargs or {}
    pex_kwargs.setdefault("dependencies", []).append(":dist")

    pex_binary(
        name="pex",
        entry_point=f"{mod_path}.__main__:cli",
        include_tools=True,
        output_path=f"{file_name}.pex",
        scie="lazy",
        **pex_kwargs,
    )
