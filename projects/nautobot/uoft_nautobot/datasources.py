from pathlib import Path
import typing as t

from .jinja_filters import import_repo_filters_module

from nautobot.apps.datasources import DatasourceContent
from nautobot.extras.datasources.git import GitRepository
from nautobot.extras.models import GraphQLQuery
from nautobot.extras.choices import LogLevelChoices


def refresh_device_types(repository_record: GitRepository, job_result, delete=False):
    """Callback for GitRepository updates - refresh Device Types managed by it."""
    if delete or "nautobot.device_types" not in t.cast(set[str], repository_record.provided_contents):
        # This repository is defined not to provide DeviceType records.
        # In a more complete worked example, we might want to iterate over any
        # DeviceType records that might have been previously created by this GitRepository
        # and ensure their deletion, but for now this is a no-op.
        return

    # This datasource type will be removed. for now it's a no-op
    return


def refresh_graphql_queries(repository_record: GitRepository, job_result, delete=False):
    """Callback for GitRepository updates - refresh GraphQL queries managed by it."""
    if delete or "nautobot.device_types" not in t.cast(set[str], repository_record.provided_contents):
        # This repository is defined not to provide GraphQL queries.
        # In a more complete worked example, we might want to iterate over any
        # GraphQL queries that might have been previously created by this GitRepository
        # and ensure their deletion, but for now this is a no-op.
        return

    repo_path = Path(repository_record.filesystem_path)
    gql_dir = repo_path / "graphql"
    if not gql_dir.exists():
        job_result.log("No graphql directory found in repository, skipping.")
        return
    for file in gql_dir.glob("[!_]*.graphql"):  # ignore files starting with _
        name = file.stem
        with open(file, "r") as f:
            query = f.read()
        GraphQLQuery.objects.update_or_create(
            name=name,
            defaults={
                "query": query,
            },
        )
        job_result.log(f"Updated GraphQL query: {name}", level_choice=LogLevelChoices.LOG_INFO)

    # TODO: reimplement this as a separate datasource
    # we have a mechanism to load jinja filters fro ma file called filters.py in the root of the repo
    # When this file changes (as part of a git pull) we want to reload the filters module
    # in the running nautobot instance. Since we use the same repo to store our filters.py file and
    # our graphql queries, we can use this datasource function to trigger the reload.
    import_repo_filters_module(repo_path, force=True)


# Register that DeviceType records can be loaded from a Git repository,
# and register the callback function used to do so
datasource_contents = [
    (
        "extras.gitrepository",  # datasource class we are registering for
        DatasourceContent(
            name="Device Types",  # human-readable name to display in the UI
            content_identifier="nautobot.device_types",  # internal id to identify the data type
            icon="mdi-archive-sync",  # Material Design Icons icon to use in UI
            callback=refresh_device_types,  # callback function on GitRepository refresh
        ),
    ),
    (
        "extras.gitrepository",  # datasource class we are registering for
        DatasourceContent(
            name="GraphQL Queries",  # human-readable name to display in the UI
            content_identifier="nautobot.graphql",  # internal id to identify the data type
            icon="mdi-graph",  # Material Design Icons icon to use in UI
            callback=refresh_graphql_queries,  # callback function on GitRepository refresh
        ),
    ),
]
