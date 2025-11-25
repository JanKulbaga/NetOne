from src.model import ArpEntry, IPInterface, MacAddressEntry, VlanEntry, NeighborEntry
from src.network_driver import NetworkDriver
from src.util import unify_mac_address

import sys
import re
import paramiko
from paramiko.ssh_exception import AuthenticationException, NoValidConnectionsError

class RouterOS7Driver(NetworkDriver):

    def __init__(self, ip_address: str, username: str, password: str, port: int = 22) -> None:
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.port = port
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.load_system_host_keys()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    

    def connect(self) -> None:
        try:
            self.ssh_client.connect(
                hostname=self.ip_address,
                username=self.username,
                password=self.password,
                port=self.port
            )
        except AuthenticationException as _:
            print("Authentication failed: Please verify your username and password.", file=sys.stderr)
            sys.exit(1)
        except NoValidConnectionsError as _:
            print("Connection failed: Unable to connect to the SSH port. Check the port number and any firewall settings.", file=sys.stderr)
            sys.exit(1)
        except TimeoutError as _:
            print("Timeout error: The host is unreachable or the IP address might be incorrect.", file=sys.stderr)
            sys.exit(1)

    def get_running_config(self) -> str:
        _, stdout, _ = self.ssh_client.exec_command("/export")
        return stdout.read().decode()

    def get_interfaces(self) -> list[IPInterface]:
        interfaces: list[IPInterface] = []

        _, stdout, _ = self.ssh_client.exec_command("/ip address print")
        ip_map = {}

        for line in stdout.readlines()[2:]:
            if (l := line.strip().split()):
                ip_address = l[1].split("/")[0]
                interface = l[3]
                ip_map[interface] = ip_address

        _, stdout, _ = self.ssh_client.exec_command("/interface print detail")
        output = stdout.read().decode().strip()
        flags_names = re.findall(r"\s(\d+)\s+((?:[A-Z]\s*){1,3})\s+name=\"([^\"]+)\"", output)
        
        for _, flag, name in flags_names:
            status = protocol = "down"

            if "X" in flag:
                status = protocol = "down"
            else:
                status = "up"
                protocol = "up" if "R" in flag else "down"
            
            ip_address = ip_map.get(name, "unassigned")
            interfaces.append(IPInterface(name, ip_address, status, protocol))

        return interfaces
    
    def get_arp_table(self) -> list[ArpEntry]:
        arp_table: list[ArpEntry] = []

        _, stdout, _ = self.ssh_client.exec_command("/ip arp print")
        output = stdout.readlines()

        for line in output[3:]:
            entry = line.strip()
            if "DC" not in entry:
                continue
            _, _, ip_address, mac_address, _, _ = entry.split()
            arp_table.append(ArpEntry(ip_address, unify_mac_address(mac_address))) 

        return arp_table

    def get_mac_address_table(self) -> list[MacAddressEntry]:
        mac_address_table: list[MacAddressEntry] = []

        _, stdout, _ = self.ssh_client.exec_command("/interface bridge host print")
        for line in stdout.readlines()[3:]:
            if (line := line.strip()):
                output = re.findall(r"\s*(\d+)\s+((?:[A-Z]\s*){1,3})\s+([0-9A-F:]{17})\s+(\S+)", line)
                for o in output:
                    if not o:
                        continue
                    _, type, mac_address, port = o
                    if "D" in type:
                        type = "Dynamic"    
                    mac_address_table.append(MacAddressEntry(unify_mac_address(mac_address), type, port))

        return mac_address_table

    def get_vlans(self) -> list[VlanEntry]:
        vlans: list[VlanEntry] = []
        _, stdout, _ = self.ssh_client.exec_command("/interface vlan print")
        output = stdout.read().decode().strip()
        if len(output) == 0:
            print("No Vlans are configured!", file=sys.stderr)
            return vlans
        
        pattern = re.compile(
            r'^\s*(\d+)\s*(X)?\s+(\S+)\s+\d+\s+\S+\s+(\d+)',
            re.MULTILINE
        )

        for _, x_flag, name, vlan_id in pattern.findall(output):
            status = "disabled" if x_flag == "X" else "active"
            vlans.append(VlanEntry(name=name, id=int(vlan_id), status=status))

        return vlans
    
    def get_neighbors(self) -> list[NeighborEntry]:
        neighbors: list[NeighborEntry] = []

        _, stdout, _ = self.ssh_client.exec_command("/ip neighbor print detail")
        output = stdout.read().decode().strip()
        if len(output) == 0:
            print("No CDP or LLDP is enabled!", file=sys.stderr)
            return neighbors
        
        pattern = re.compile(
            r"interface=(\S+).*?"
            r"address=(\S+).*?"
            r'identity="([^"]+)".*?'
            r'interface-name="([^"]+)"',
            re.DOTALL
        )

        for interface, address, identity, iface_name in pattern.findall(output):
            neighbors.append(
                NeighborEntry(
                    local_interface=interface,
                    neighbor_interface=iface_name,
                    name=identity,
                    ip_address=address
                )
            )

        return neighbors
    
    def ping_remote(self, target: str, count: int = 4) -> bool:
        _, stdout, _ = self.ssh_client.exec_command(f"ping count={count} {target}")
        output = stdout.read().decode().strip()
        received = int(output.split("received=")[1].split()[0])
        
        if (received <= 0):
            return False
        
        return True
    
    def exec_command(self, command: str) -> str:
        _, stdout, _ = self.ssh_client.exec_command(command)
        output = stdout.read().decode().strip()
        return output

    def close(self) -> None:
        self.ssh_client.close()
