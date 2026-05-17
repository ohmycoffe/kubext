from kubek.core.ports import get_deterministic_port
from kubek.kube.client import DEFAULT_NAMESPACE, get_current_namespace

from portfwd.config import (
    PortFwdConfig,
    get_default_service,
)
from portfwd.error import AmbiguousPortError, KubernetesResourceNotFoundError
from portfwd.kube import get_service
from portfwd.kube.client import KubernetesService
from portfwd.models import (
    NamespacedServiceName,
    ServicePortForwardPlan,
    ServicePortForwardSpec,
)
from portfwd.utils import find_free_port, is_port_free


def resolve_remote_port(service: KubernetesService) -> int:
    ports = [p.port for p in service.ports]

    # If there are multiple ports, we cannot guess which one to use
    if len(service.ports) > 1:
        raise AmbiguousPortError(
            f"Service '{service.namespace}/{service.name}' has multiple ports, "
            f"remote port must be specified (available: {', '.join(map(str, [p.port for p in service.ports]))})"
        )
    # If there is exactly one port, we can use it
    return ports[0]


def resolve_local_port(
    name: str,
    namespace: str,
    remote_port: int,
    config: PortFwdConfig,
) -> int:
    # If there is a default config for this service with a local port specified, use it
    default_service = get_default_service(
        config=config,
        name=name,
        namespace=namespace,
        remote_port=remote_port,
    )
    if default_service is not None:
        return int(default_service.local_port)

    # otherwise, we need to find a free local port to use
    deterministic_port = get_deterministic_port(
        service=name,
        namespace=namespace,
        service_port=remote_port,
    )
    if is_port_free(deterministic_port):
        return deterministic_port

    return find_free_port()


def build_port_forward_plan(
    spec: ServicePortForwardSpec,
    config: PortFwdConfig,
) -> ServicePortForwardPlan:
    name = spec.target.name
    ns = spec.target.namespace or get_current_namespace() or DEFAULT_NAMESPACE

    service = get_service(ns, name)
    if not service:
        raise KubernetesResourceNotFoundError(f"Service '{ns}/{name}' not found")

    # Assign a remote port
    # If remote port is explicitly specified in the spec, use it
    if spec.remote_port is not None:
        remote_port = int(spec.remote_port)
    else:
        remote_port = resolve_remote_port(service)

    # Assign a local port
    # If local port is explicitly specified in the spec, use it
    if spec.local_port is not None:
        local_port = int(spec.local_port)
    else:
        local_port = resolve_local_port(
            name=name, namespace=ns, remote_port=remote_port, config=config
        )

    return ServicePortForwardPlan(
        target=NamespacedServiceName(namespace=ns, name=name),
        remote_port=remote_port,
        local_port=local_port,
    )
