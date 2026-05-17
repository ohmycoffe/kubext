from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".kube" / "portfwd"


class ServicePortForwardDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    remote_port: int = Field(ge=1, le=65535)
    local_port: int = Field(ge=1, le=65535)


class GroupSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    services: list[ServicePortForwardDefaults] = Field(default_factory=list)


class PortFwdConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    defaults: list[ServicePortForwardDefaults] = Field(default_factory=list)
    groups: list[GroupSpec] = Field(default_factory=list)


def get_default_service(
    config: PortFwdConfig,
    name: str,
    namespace: str,
    remote_port: int,
) -> ServicePortForwardDefaults | None:
    candidates = [
        entry
        for entry in config.defaults
        if (
            entry.name == name
            and entry.namespace == namespace
            and entry.remote_port == remote_port
        )
    ]
    # if multiple defaults match, use the last one.
    return candidates[-1] if candidates else None


def get_group(cfg: PortFwdConfig, name: str) -> GroupSpec | None:
    for group in cfg.groups:
        if group.name == name:
            return group
    return None


def load_config(path: Path | None) -> PortFwdConfig:
    if path is None:
        path = DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.debug("No config file found at %s, using empty config", path)
        return PortFwdConfig()

    yaml = YAML(typ="safe")
    try:
        with path.open(encoding="utf-8") as f:
            root = yaml.load(f)
        if not isinstance(root, dict):
            logger.warning(
                "Config at %s has unexpected structure, using empty config", path
            )
            return PortFwdConfig()
        logger.info("Loaded config from %s", path)
        return PortFwdConfig.model_validate(root)
    except Exception as e:
        logger.warning("Failed to load config from %s: %s, using empty config", path, e)
        return PortFwdConfig()


if __name__ == "__main__":
    cfg = load_config(Path("portfwd"))
    print(cfg)
