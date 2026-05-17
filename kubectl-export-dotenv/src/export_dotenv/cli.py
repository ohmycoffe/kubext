from __future__ import annotations

import enum
import json
import subprocess
from typing import Annotated

import kubek.term.format as fmt
import questionary
import typer
from kubek.kube import DEFAULT_NAMESPACE, get_current_namespace
from kubek.term import STYLE_QUESTIONARY, get_console, print_error

from export_dotenv.kube import (
    get_available_deployments,
    get_available_workflowtemplates,
    get_deployment_envs,
    get_workflowtemplate_envs,
)
from export_dotenv.utils import export_as_dotenv, setup_logging

console = get_console()


class ResourceKind(enum.StrEnum):
    DEPLOYMENT = "deployment"
    WORKFLOWTEMPLATE = "workflowtemplate"


class ExportFormat(enum.StrEnum):
    ENV = "env"
    JSON = "json"


app = typer.Typer()


def ask_for_kind() -> ResourceKind:
    selected = questionary.select(
        "Select a kind:",
        choices=[
            questionary.Choice(
                title="Deployment",
                value=ResourceKind.DEPLOYMENT,
                description="(Kubernetes Deployment)",
            ),
            questionary.Choice(
                title="WorkflowTemplate",
                value=ResourceKind.WORKFLOWTEMPLATE,
                description="(Argo WorkflowTemplate)",
            ),
        ],
        use_jk_keys=False,
        style=STYLE_QUESTIONARY,
    ).ask()

    return ResourceKind(selected)


def ask_for_resource(resources: list[str], kind: ResourceKind) -> str:
    selected = questionary.select(
        f"Select a {kind.value}:",
        choices=resources,
        use_search_filter=True,
        use_jk_keys=False,
        style=STYLE_QUESTIONARY,
    ).ask()
    return selected


@app.callback(invoke_without_command=True)
def get(
    kind: Annotated[
        ResourceKind | None,
        typer.Option(
            help="Kind of resource to get parameters for. If not provided, you will be prompted to select one.",
        ),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option(
            help="Kubernetes namespace. If not provided, you will be prompted to select one.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            help="Name of the resource. If not provided, you will be prompted to select one.",
        ),
    ] = None,
    output: ExportFormat = ExportFormat.ENV,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Verbose output. Use -vv for debug."
        ),
    ] = 0,
):
    """
    Get environment variables for a Kubernetes deployment or Argo WorkflowTemplate.
    """
    setup_logging(verbose)

    kind = kind or ask_for_kind()

    if not kind:
        raise typer.Exit(code=0)

    try:
        namespace = namespace or get_current_namespace() or DEFAULT_NAMESPACE
    except subprocess.CalledProcessError as e:
        print_error(e, "Failed to get current namespace from kubeconfig")
        raise typer.Exit(code=1) from None

    console.print("Namespace:", fmt.highlight(namespace))

    try:
        with console.status(
            fmt.ongoing_status(f"Fetching available {kind.value}s in {namespace}…")
        ):
            if kind == ResourceKind.DEPLOYMENT:
                resources = get_available_deployments(namespace=namespace)
            else:
                resources = get_available_workflowtemplates(namespace=namespace)
    except subprocess.CalledProcessError as e:
        print_error(
            e, f"Failed to fetch available {kind.value}s in namespace '{namespace}'"
        )
        raise typer.Exit(code=1) from None
    if not resources:
        console.print(fmt.error(f"No {kind.value}s found in namespace '{namespace}'"))
        raise typer.Exit(code=1)

    if not name:
        name = ask_for_resource(resources=resources, kind=kind)
        if not name:
            raise typer.Exit(code=0)

    if name not in resources:
        console.print(
            fmt.error(f"{kind.value} '{name}' not found in namespace '{namespace}'")
        )
        raise typer.Exit(code=1)

    try:
        with console.status(fmt.ongoing_status("Fetching environment variables…")):
            if kind == ResourceKind.DEPLOYMENT:
                vals = get_deployment_envs(namespace=namespace, name=name)
            else:
                vals = get_workflowtemplate_envs(namespace=namespace, name=name)
    except subprocess.CalledProcessError as e:
        print_error(e, f"Failed to fetch environment variables for '{name}'")
        raise typer.Exit(code=1) from None

    if output == ExportFormat.JSON:
        formatted = json.dumps(vals, sort_keys=True)
    elif output == ExportFormat.ENV:
        formatted = export_as_dotenv(vals=vals, name=name)
    print(formatted)
    raise typer.Exit(code=0)
