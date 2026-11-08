"""Small capability contracts; platform evidence stays source-labelled."""
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Capability:
    key: str
    status: Literal['supported','unsupported','unverified']
    mode: Literal['read','local','write']


@dataclass(frozen=True)
class AdapterDescriptor:
    platform_id: str
    label: str
    version: str
    marketplaces: tuple[str,...]
    capabilities: tuple[Capability,...]


class OperationsAdapter(Protocol):
    descriptor: AdapterDescriptor

    def stores(self) -> list[dict]: ...

    def overview(self,store_id: str) -> dict: ...
