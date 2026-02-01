from src.network_driver import NetworkDriver
from src.model import ArpEntry, IPInterface, MacAddressEntry, VlanEntry, NeighborEntry, LacpGroup
from src.util import unify_mac_address

import sys
import re
from netmiko import ConnectHandler, NetmikoTimeoutException, NetMikoAuthenticationException


class IOSDriver(NetworkDriver):
    def __init__(self, ip_address: str, username: str, password: str, port: int = 22) -> None:
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.port = port
    
    def connect(self) -> None:
        try:
            self.ssh_client = ConnectHandler(**{
                "device_type": "cisco_ios",
                "host": self.ip_address,
                "username": self.username,
                "password": self.password,
                "port": self.port
            })
        except NetmikoTimeoutException as _:
            print("Connection failed: the hostname or IP address is incorrect or please check the port number and any firewall settings.")
            sys.exit(1)
        except NetMikoAuthenticationException as _:
            print("Authentication failed: Please verify your username and password.")
            sys.exit(1)

    def get_running_config(self) -> str:
        return self.ssh_client.send_command("sh run")

    def get_interfaces(self) -> list[IPInterface]:
        interfaces: list[IPInterface] = []

        output = self.ssh_client.send_command("sh ip int br")
        for line in output.split("\n")[1:]:
            if "administratively" in line:
                interface, ip_address, _, _, _, status, protocol = line.split()
                status = f"administratively {status}"
                interfaces.append(IPInterface(interface, ip_address, status, protocol))
            else:
                interface, ip_address, _, _, status, protocol = line.split()
                interfaces.append(IPInterface(interface, ip_address, status, protocol))

        return interfaces
    
    def get_arp_table(self) -> list[ArpEntry]:
        arp_table: list[ArpEntry] = []

        output = self.ssh_client.send_command("sh arp")
        for entry in output.split("\n")[1:]:
            _, ip_address, _, mac_address, _, _ = entry.split()
            arp_table.append(ArpEntry(ip_address, unify_mac_address(mac_address))) 

        return arp_table

    def get_mac_address_table(self) -> list[MacAddressEntry]:
        mac_address_table: list[MacAddressEntry] = []

        output = self.ssh_client.send_command("sh mac address-table")

        for line in output.split("\n")[5:-1]:
            _, mac_address, type, port = line.split()
            mac_address_table.append(MacAddressEntry(unify_mac_address(mac_address), type, port))

        return mac_address_table
    
    def get_vlans(self) -> list[VlanEntry]:
        vlans: list[VlanEntry] = []
        output = self.ssh_client.send_command("show vlan brief")

        pattern = re.compile(r'^\s*(\d+)\s+(\S+)\s+(\S+)', re.MULTILINE)

        for vlan_id, name, status in pattern.findall(output):
            vlans.append(VlanEntry(id=int(vlan_id), name=name, status=status))

        return vlans
    
    def get_neighbors(self) -> list[NeighborEntry]:

        cdp_status = self.ssh_client.send_command("show cdp")

        if "CDP is not enabled" not in cdp_status:
            cdp_output = self.ssh_client.send_command("show cdp neighbors detail")
            return self.__parse_cdp_neighbors(cdp_output)
        
        lldp_status = self.ssh_client.send_command("show lldp")

        if "LLDP is not enabled" not in lldp_status:
            lldp_output = self.ssh_client.send_command("show lldp neighbors detail")
            return self.__parse_lldp_neighbors(lldp_output)
        
        print("No CDP or LLDP is enabled!")
        return []
    
    def __parse_cdp_neighbors(self, output: str) -> list[NeighborEntry]:
        neighbors: list[NeighborEntry] = []

        pattern = re.compile(
            r"Device ID:\s*(.+?)\n.*?"
            r"Interface:\s*(\S+),\s*Port ID.*?:\s*(\S+)",
            re.DOTALL
        )

        for device, local_intf, neigh_intf in pattern.findall(output):
            ip_address_match = re.search(r"IP address:\s*(\S+)", output)
            ip_address = ip_address_match.group(1) if ip_address_match else ""
            neighbors.append(
                NeighborEntry(
                    name=device,
                    local_interface=local_intf,
                    neighbor_interface=neigh_intf,
                    ip_address=ip_address
                )
            )
        
        return neighbors

    def __parse_lldp_neighbors(self, output: str) -> list[NeighborEntry]:
        neighbors: list[NeighborEntry] = []

        lldp_detail = self.ssh_client.send_command("sh lldp neighbors detail")

        mgmt_ips = {}
        device_ip_pattern = re.compile(
            r"System Name:\s*(\S+).*?Management Addresses:\s*\n\s*IP:\s*(\S+)",
            re.DOTALL
        )
        for device in device_ip_pattern.findall(lldp_detail):
            system_name, ip = device
            mgmt_ips[system_name] = ip

        lldp = self.ssh_client.send_command("sh lldp neighbors")

        summary_pattern = re.compile(
            r"(\S+)\s+(\S+)\s+\d+\s+[\w,]+\s+(\S+)"
        )

        for device_id, local_intf, neigh_intf in summary_pattern.findall(lldp):
            neighbors.append(NeighborEntry(
                local_interface=local_intf,
                name=device_id,
                neighbor_interface=neigh_intf,
                ip_address=mgmt_ips.get(device_id, "")
            ))
            
        return neighbors
    
    def ping_remote(self, target: str, count: int = 4) -> bool:
        timeout = 4 * count
        output = self.ssh_client.send_command(f"ping {target} repeat {count}", read_timeout=timeout)
        received = int(output.split("rate is ")[1].split()[0])
        
        if (received <= 0):
            return False
        
        return True
    
    def exec_command(self, command: str) -> str:
        if "show" in command or "sh" in command:
            return self.ssh_client.send_command(command)
        
        return self.ssh_client.send_config_set([command])
    
    def get_lacp_groups(self) -> list[LacpGroup]:
        output = self.exec_command("sh etherchannel summary")

        _, number_of_groups = output.split("\n")[12].split(": ")
        if int(number_of_groups) == 0:
            print("No LACP groups found on device.")
            return []

        lacp_groups: list[LacpGroup] = []
        output = self.exec_command("sh etherchannel summary")
        for line in output.split("\n")[-2:]:
            if not line:
                continue
            parts = [p for p in line.split() if p]
            name_match = re.match(r'(\w+)', parts[1])
            name = name_match.group(1)
            mode = parts[2]
            state = "running" if parts[1][-2] == "U" else "disabled"
            members = [member[:-3] for member in parts[3:] if len(parts) > 3]
            lacp_groups.append(LacpGroup(name, mode, state, members))

        return lacp_groups

    def get_lacp_group(self, group_name: str) -> LacpGroup | None:
        lacp_groups = self.get_lacp_groups()
        for group in lacp_groups:
            if group.name == group_name:
                return group
        return None


    def close(self) -> None:
        self.ssh_client.disconnect()
