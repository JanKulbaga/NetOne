from src.model import ArpEntry, IPInterface, MacAddressEntry, VlanEntry, NeighborEntry, LacpGroup

from typing import Protocol

class NetworkDriver(Protocol):

    def __init__(self, ip_address: str, username: str, password: str, port: int = 22) -> None:
        ...

    def connect(self) -> None:
        ...

    def get_running_config(self) -> str:
        ...

    def get_interfaces(self) -> list[IPInterface]:
        ...
    
    def get_arp_table(self) -> list[ArpEntry]:
        ...

    def get_mac_address_table(self) -> list[MacAddressEntry]:
        ...

    def get_vlans(self) -> list[VlanEntry]:
        ...

    def get_neighbors(self) -> list[NeighborEntry]:
        ...

    def ping_remote(self, target: str, count: int = 4) -> bool:
        ...

    def exec_command(self, command: str) -> str:
        ...

    def get_lacp_groups(self) -> list[LacpGroup]:
        ...

    def get_lacp_group(self, group_name: str) -> LacpGroup | None:
        ...

    def close(self) -> None:
        ...
