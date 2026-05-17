from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from kubek.kube import get_current_namespace
from kubek.term import format as fmt
from kubek.term import get_console, print_error

from portfwd.config import (
    DEFAULT_CONFIG_PATH,
    GroupSpec,
    PortFwdConfig,
    load_config,
)
from portfwd.kube import (
    KubernetesService,
    get_available_namespaces,
    get_current_context,
)
from portfwd.models import (
    NamespacedServiceName,
    ServicePortForwardPlan,
    ServicePortForwardSpec,
)
from portfwd.parser import parse_spec
from portfwd.plan import build_port_forward_plan
from portfwd.runner import (
    fetch_services,
    manage_port_forwards,
)
from portfwd.term import (
    SpecialGroups,
    ask_for_group,
    ask_for_namespace,
    ask_for_service,
)

logger = logging.getLogger(__name__)

app = typer.Typer()


console = get_console()


def __fetch_services_for_namespaces(namespaces: list[str]) -> list[KubernetesService]:
    try:
        with console.status(fmt.ongoing_status("Fetching services…")):
            return fetch_services(namespaces)
    except subprocess.CalledProcessError as e:
        print_error(e, "Failed to fetch services using kubectl")
        raise typer.Exit(code=1) from None


def __fetch_namespaces() -> tuple[list[str], str | None]:
    """Fetch all namespaces and current namespace.

    Returns tuple of (all_namespaces, current_namespace).
    """
    try:
        with console.status(fmt.ongoing_status("Fetching namespaces…")):
            all_namespaces = get_available_namespaces()
            current = get_current_namespace()
            return all_namespaces, current
    except subprocess.CalledProcessError as e:
        print_error(e, "Failed to fetch namespaces using kubectl")
        raise typer.Exit(code=1) from None


def __setup_logging(verbose: int) -> None:
    logging_verbosity = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = logging_verbosity[min(verbose, len(logging_verbosity) - 1)]
    logging.getLogger("kubek").setLevel(level)
    logging.getLogger("portfwd").setLevel(level)


def __extract_group(group_name: str, available: list[GroupSpec]) -> GroupSpec | None:
    for group in available:
        if group.name == group_name:
            return group
    return None


def __validate_group(group: str, available: list[GroupSpec]) -> None:
    available_groups = {g.name for g in available}
    if not available:
        raise typer.BadParameter("No groups defined in config file.")
    if group not in available_groups:
        raise typer.BadParameter(
            f"--group / -g. Unknown group '{group}' "
            f"(choose from: '{', '.join(sorted(available_groups))}')"
        )


def __run_group(group_name: str, cfg: PortFwdConfig, context: str | None) -> None:
    __validate_group(group_name, cfg.groups)
    group_obj = __extract_group(group_name, cfg.groups)
    assert group_obj is not None
    plans: list[ServicePortForwardPlan] = []
    for svc in group_obj.services:
        target = NamespacedServiceName(name=svc.name, namespace=svc.namespace)
        plan = ServicePortForwardPlan(
            target=target, remote_port=svc.remote_port, local_port=svc.local_port
        )
        plans.append(plan)
    asyncio.run(manage_port_forwards(plans, context=context))


def __run_services(service: list[str], cfg: PortFwdConfig, context: str | None) -> None:
    plans: list[ServicePortForwardPlan] = []
    for svc in service:
        spec = parse_spec(svc)

        plan: ServicePortForwardPlan = build_port_forward_plan(spec=spec, config=cfg)
        plans.append(plan)
    asyncio.run(manage_port_forwards(plans, context))


def __run_interactive(cfg: PortFwdConfig, context: str | None) -> None:
    all_namespaces, current_namespace = __fetch_namespaces()
    selected_namespaces = ask_for_namespace(all_namespaces, current_namespace)
    services = __fetch_services_for_namespaces(selected_namespaces)
    if not services:
        console.print(fmt.warn("No services found."))
        raise typer.Exit(code=0)

    selected: list[ServicePortForwardSpec] = ask_for_service(services)
    plans: list[ServicePortForwardPlan] = []
    for spec in selected:
        plan = build_port_forward_plan(spec=spec, config=cfg)
        plans.append(plan)
    asyncio.run(manage_port_forwards(plans=plans, context=context))


@app.callback(invoke_without_command=True)
def port_forward(
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            envvar="KUBEK_PORTFWD_CONFIG",
            help=f"Path to config file. Defaults to {DEFAULT_CONFIG_PATH}.",
        ),
    ] = None,
    group: Annotated[
        str | None,
        typer.Option(
            "--group",
            "-g",
            help="Run a predefined service group from the config.",
        ),
    ] = None,
    service: Annotated[
        list[str] | None,
        typer.Option(
            "--service",
            "-s",
            help="Service to forward in the format \\[namespace/]name\\[:remote_port]\\[::local_port]. Can be specified multiple times.",
        ),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Verbose output. Use -vv for more detail.",
        ),
    ] = 0,
) -> None:
    """Interactive kubectl port-forward for Kubernetes services.

    \b
    Examples:
        kubectl portfwd
        kubectl portfwd -g backend
        kubectl portfwd -s kube-public/auth-service
        kubectl portfwd -s kube-public/auth-service:8080
        kubectl portfwd -s kube-public/auth-service:8080::50000
        kubectl portfwd -s kube-public/auth -s kube-public/api
    """

    __setup_logging(verbose)

    if group is not None and service is not None:
        raise typer.BadParameter("'--group' and '--service' are mutually exclusive.")

    context = get_current_context()
    if context:
        console.print("Context:", fmt.highlight(context))

    cfg = load_config(config)

    if service is not None:
        __run_services(service, cfg, context)
        return

    if group is not None:
        __run_group(group, cfg, context)
        return

    group_obj = ask_for_group(cfg.groups)

    if group_obj is SpecialGroups.CUSTOM:
        __run_interactive(cfg, context)
    else:
        __run_group(group_obj.name, cfg, context)
