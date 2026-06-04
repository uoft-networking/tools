# resources(
#     name = "nautobot-res",
#     sources = ["nautobot/**/*", "!nautobot/**/*.py", "!nautobot/pyproject.toml"],
# )

# python_sources(
#     name = "nautobot-src",
#     sources = ["nautobot/**/*.py"],
#     dependencies=[
#         ":nautobot-res",
#     ],
# )
# poetry_requirements(
#     name = "nautobot-reqs",
#     source="nautobot/pyproject.toml",
#     overrides={
#         # tell pants to ignore the jinja2 dependency coming from nautobot, since 
#         # we already have this dependency in our top-level pyproject.toml, and we 
#         # don't want to have two different versions of jinja2 in our dependency graph
#         "Jinja2": {'modules': ['']}, 
#     }
# )

# python_distribution(
#     name = "nautobot",
#     dependencies=[
#         ":nautobot-reqs",
#     ],
#     provides=python_artifact(),
#     skip_twine=True, # if / when we get to the point of publishing packages, don't publish this one
# )