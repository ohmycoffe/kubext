import json
from types import SimpleNamespace

import pytest
from portfwd.kube.client import (
    KubernetesService,
    KubernetesServicePort,
    parse_context,
    parse_namespaces,
    parse_services,
)


def _create_dummy_process_info(
    name: str, cmdline: list[str], pid: int
) -> SimpleNamespace:
    return SimpleNamespace(info={"name": name, "cmdline": cmdline, "pid": pid})


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("my-cluster\n", "my-cluster"),
        ("arn:aws:eks:us-east-1:123456789012:cluster/my-cluster", "my-cluster"),
        ("", ""),
        ("   \n", ""),
    ],
)
def test_parse_context(raw, expected):
    """Strips whitespace and extracts the cluster name from plain strings and EKS ARNs."""
    assert parse_context(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            json.dumps(
                {
                    "items": [
                        {"metadata": {"name": "default"}},
                        {"metadata": {"name": "kube-system"}},
                    ]
                }
            ),
            ["default", "kube-system"],
        ),
        (json.dumps({"items": []}), []),
    ],
)
def test_parse_namespaces(raw, expected):
    """Parses namespace names from kubectl JSON output."""
    assert parse_namespaces(raw) == expected


def test_parse_services_basic():
    """Parses a single service with one port from kubectl JSON output."""
    raw = json.dumps(
        {
            "items": [
                {
                    "metadata": {"name": "my-svc"},
                    "spec": {"ports": [{"port": 80, "protocol": "TCP"}]},
                },
            ]
        }
    )
    tested = parse_services(raw, namespace="ns")
    assert tested == [
        KubernetesService(
            name="my-svc",
            ports=[KubernetesServicePort(port=80, protocol="TCP")],
            namespace="ns",
        )
    ]


def test_parse_services_skips_kubernetes():
    """Excludes the built-in 'kubernetes' service from the parsed result."""
    raw = json.dumps(
        {
            "items": [
                {
                    "metadata": {"name": "kubernetes"},
                    "spec": {"ports": [{"port": 443, "protocol": "TCP"}]},
                },
                {
                    "metadata": {"name": "my-svc"},
                    "spec": {"ports": [{"port": 80, "protocol": "TCP"}]},
                },
            ]
        }
    )
    tested = parse_services(raw, namespace="ns")
    assert tested == [
        KubernetesService(
            name="my-svc",
            ports=[KubernetesServicePort(port=80, protocol="TCP")],
            namespace="ns",
        )
    ]


def test_parse_services_multiple_ports_expanded():
    """Groups all ports of a service into one KubernetesService entry."""
    raw = json.dumps(
        {
            "items": [
                {
                    "metadata": {"name": "my-svc"},
                    "spec": {
                        "ports": [
                            {"port": 80, "protocol": "TCP"},
                            {"port": 8080, "protocol": "TCP"},
                        ]
                    },
                },
            ]
        }
    )
    tested = parse_services(raw, namespace="ns")
    assert tested == [
        KubernetesService(
            name="my-svc",
            ports=[
                KubernetesServicePort(port=80, protocol="TCP"),
                KubernetesServicePort(port=8080, protocol="TCP"),
            ],
            namespace="ns",
        ),
    ]


def test_parse_services_sorted_by_namespace_then_name_then_port():
    """Returns services sorted by namespace then name; ports sorted within each service."""
    raw = json.dumps(
        {
            "items": [
                {
                    "metadata": {"name": "zebra"},
                    "spec": {"ports": [{"port": 80, "protocol": "TCP"}]},
                },
                {
                    "metadata": {"name": "alpha"},
                    "spec": {
                        "ports": [
                            {"port": 9000, "protocol": "TCP"},
                            {"port": 80, "protocol": "TCP"},
                        ]
                    },
                },
            ]
        }
    )
    tested = parse_services(raw, namespace="ns")
    assert tested == [
        KubernetesService(
            name="alpha",
            ports=[
                KubernetesServicePort(port=80, protocol="TCP"),
                KubernetesServicePort(port=9000, protocol="TCP"),
            ],
            namespace="ns",
        ),
        KubernetesService(
            name="zebra",
            ports=[KubernetesServicePort(port=80, protocol="TCP")],
            namespace="ns",
        ),
    ]


def test_parse_services_empty():
    """Returns an empty list when the items array contains no services."""
    assert parse_services(json.dumps({"items": []}), namespace="ns") == []
