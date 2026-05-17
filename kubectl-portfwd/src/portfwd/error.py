class KubernetesError(Exception):
    """Base class for all Kubernetes-related errors."""


class AmbiguousPortError(KubernetesError):
    """Raised when a port forward specification is ambiguous and cannot be resolved to a single service."""


class KubernetesAmbiguousResourceError(KubernetesError):
    """Raised when a specified Kubernetes resource (e.g. service) is ambiguous and cannot be resolved to a single resource."""


class KubernetesResourceNotFoundError(KubernetesError):
    """Raised when a specified Kubernetes resource (e.g. service) cannot be found."""
