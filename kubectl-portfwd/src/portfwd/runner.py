from __future__ import annotations

import asyncio
import itertools
import logging
import signal
from collections.abc import Callable

from kubek.term import get_console
from rich.live import Live

from portfwd.kube import (
    KubernetesService,
    PortForwardProcess,
    get_services,
    start_port_forward,
)
from portfwd.models import ServicePortForwardPlan
from portfwd.term import make_table

logger = logging.getLogger(__name__)
console = get_console()


async def watch_processes(
    processes: list[PortForwardProcess],
    statuses: dict[str, str],
    stop_event: asyncio.Event,
    on_exit: Callable[[], None] = lambda: None,
) -> None:
    async def _watch(process: PortForwardProcess) -> None:
        await process.process.wait()
        if not stop_event.is_set():
            statuses[f"{process.service_name}:{process.remote_port}"] = (
                f"died (exit {process.process.returncode})"
            )
            on_exit()

    async with asyncio.TaskGroup() as tg:
        for proc in processes:
            tg.create_task(_watch(proc))


async def manage_port_forwards(
    plans: list[ServicePortForwardPlan],
    context: str | None,
) -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    processes: list[PortForwardProcess] = []
    statuses: dict[str, str] = {}

    for plan in plans:
        process = await start_port_forward(
            plan.target.namespace,
            plan.target.name,
            plan.local_port,
            plan.remote_port,
        )
        processes.append(process)
        statuses[f"{plan.target.name}:{plan.remote_port}"] = "live"

    if not processes:
        return

    with Live(
        renderable=make_table(processes, statuses, context),
        console=console,
        refresh_per_second=1,
    ) as live:

        def refresh() -> None:
            live.update(make_table(processes, statuses, context))

        def cleanup() -> None:
            stop_event.set()
            for proc in processes:
                try:
                    proc.process.terminate()
                    statuses[f"{proc.service_name}:{proc.remote_port}"] = "stopped"
                except ProcessLookupError:
                    pass
            refresh()

        loop.add_signal_handler(signal.SIGINT, cleanup)
        loop.add_signal_handler(signal.SIGTERM, cleanup)

        await watch_processes(
            processes=processes,
            statuses=statuses,
            stop_event=stop_event,
            on_exit=refresh,
        )


def fetch_services(namespaces: list[str]) -> list[KubernetesService]:
    return list(itertools.chain.from_iterable(get_services(ns) for ns in namespaces))
