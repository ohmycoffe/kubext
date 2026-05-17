from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, TypeAlias

import kubek.term.format as fmt
import questionary
import typer
from kubek.term.console import get_console
from kubek.term.style import STYLE_QUESTIONARY

from portfwd.config import GroupSpec
from portfwd.models import NamespacedServiceNameSpec, ServicePortForwardSpec

if TYPE_CHECKING:
    from portfwd.kube import KubernetesService


class SpecialGroups(StrEnum):
    CUSTOM = "custom"


GroupNamesSelection: TypeAlias = GroupSpec | SpecialGroups


console = get_console()


def ask_for_namespace(
    all_namespaces: list[str],
    current_namespace: str | None,
) -> list[str]:
    ordered = (
        [current_namespace] + [ns for ns in all_namespaces if ns != current_namespace]
        if current_namespace in all_namespaces
        else all_namespaces
    )
    choices = [
        questionary.Choice(
            title=f"{ns} (current namespace)" if ns == current_namespace else ns,
            value=ns,
            checked=(ns == current_namespace),
        )
        for ns in ordered
    ]
    selected: list[str] = questionary.checkbox(
        "Select namespaces:",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
        style=STYLE_QUESTIONARY,
    ).ask()

    if not selected:
        console.print(fmt.warn("No namespaces selected. Exiting."))
        raise typer.Exit(code=0)
    return selected


def ask_for_service(
    available_services: list[KubernetesService],
) -> list[ServicePortForwardSpec]:
    choices: list[questionary.Choice] = []
    for svc in sorted(available_services, key=lambda x: (x.namespace, x.name)):
        for port in sorted(svc.ports, key=lambda x: x.port):
            target = NamespacedServiceNameSpec(namespace=svc.namespace, name=svc.name)
            title = f"{svc.namespace}/{svc.name}  :{port.port} ({port.protocol})"
            spec = ServicePortForwardSpec(target=target, remote_port=port.port)
            choice = questionary.Choice(title=title, value=spec)
            choices.append(choice)

    selected: list[ServicePortForwardSpec] = questionary.checkbox(
        "Select services to forward:",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
        style=STYLE_QUESTIONARY,
    ).ask()
    if not selected:
        console.print(fmt.warn("No services selected. Exiting."))
        raise typer.Exit(code=0)
    return selected


def ask_for_group(groups: list[GroupSpec]) -> GroupNamesSelection:
    if not groups:
        return SpecialGroups.CUSTOM

    choices = [
        *(questionary.Choice(title=group.name, value=group) for group in groups),
        questionary.Choice(
            title="custom",
            value=SpecialGroups.CUSTOM,
            description="(interactive: select services to forward)",
        ),
    ]
    selected = questionary.select(
        "Select a group to run:",
        choices=choices,
        use_jk_keys=False,
        style=STYLE_QUESTIONARY,
    ).ask()
    return selected
