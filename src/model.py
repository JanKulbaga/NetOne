from dataclasses import dataclass

@dataclass
class IPInterface:
    interface: str
    ip_address: str
    status: str
    protocol: str

@dataclass
class MacAddressEntry:
    mac_address: str
    type: str
    port: str

@dataclass
class VlanEntry:
    id: int
    name: str
    status: str

@dataclass
class NeighborEntry:
    local_interface: str
    neighbor_interface: str
    name: str
    ip_address: str

@dataclass
class ArpEntry:
    ip_address: str
    mac_address: str

@dataclass
class LacpGroup:
    name: str
    mode: str
    state: str
    members: list[str]
