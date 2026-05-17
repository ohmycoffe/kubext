import re

from portfwd.models import NamespacedServiceNameSpec, ServicePortForwardSpec

REGEXP_PORT_FORWARD_SPEC = re.compile(
    r"""
    ^
    (?:(?P<namespace>[^/\s:]+)/)?   # optional namespace
    (?P<name>[^/\s:]+)              # service name
    (?::
        (?P<remote>\d+)             # remote port
        (?:->(?P<local>\d+))?       # optional local port
    )?
    $
    """,
    re.VERBOSE,
)


def parse_spec(value: str) -> ServicePortForwardSpec:
    """Parses a string in the format '[namespace/]name[:remote_port][->local_port]' into a ServicePortForwardSpec"""

    val = value.strip()

    match = REGEXP_PORT_FORWARD_SPEC.match(val)
    if not match:
        raise ValueError(f"Invalid '{value}', expected '[ns/]name[:remote][->local]'")

    namespace = match.group("namespace")
    name = match.group("name")
    remote = match.group("remote")
    local = match.group("local")

    target = NamespacedServiceNameSpec(
        namespace=namespace,
        name=name,
    )

    return ServicePortForwardSpec(
        target=target,
        remote_port=remote,  # type: ignore
        local_port=local,  # type: ignore
    )
