import os


def pdm_build_initialize(context):
    if "dependencies" in context.config_settings:
        target = context.config_settings["dependencies"]
        import re
        from pathlib import Path
        import subprocess

        monorepo_root = Path(__file__).parent.parent.parent

        # TODO: find out if python build frontends like pip ALWAYS initialize submodules
        # if so, this call won't be necessary
        subprocess.run(["git", "submodule", "init"], cwd=monorepo_root)
        forks_dir = monorepo_root / "custom-forks"
        forks = {fork.name: fork for fork in forks_dir.iterdir() if fork.is_dir() and not fork.name.startswith("_")}

        if target == "local":

            def local_dependency(name: str):
                if name.startswith("uoft_"):
                    proj_name = name.partition(" ")[0].partition("uoft_")[2]
                    proj_dir = monorepo_root / "projects" / proj_name
                    if proj_dir.exists():
                        return f"{name} @ file://{proj_dir}"
                base_name = re.split(r" |<|>|!|=|~|@|\[", name)[0]
                if base_name in forks:
                    extras = re.search(r"\[.*\]", name)
                    if extras:
                        base_name = f"{base_name}{extras.group()}"
                    return f"{base_name} @ file://{forks[base_name]}"
                return name

        metadata = context.config.metadata
        # import debugpy

        # debugpy.listen(5678)
        # print("Debugger listening on 5678")
        # debugpy.wait_for_client()
        # debugpy.breakpoint()
        metadata["dependencies"] = [local_dependency(dep) for dep in metadata["dependencies"]]
        print("Local dependencies selected")
