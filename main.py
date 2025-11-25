from src.routeros7_driver import RouterOS7Driver
from src.ios_driver import IOSDriver


def main() -> None:
    # MikroTik RouterOS 7 example
    router_os = RouterOS7Driver("192.168.1.250", "admin", "admin")
    router_os.connect()
    print(router_os.get_arp_table())
    router_os.close()

    # Cisco IOS example
    switch = IOSDriver("192.168.1.163", "admin", "admin")
    switch.connect()
    print(switch.get_arp_table())
    switch.close()


if __name__ == "__main__":
    main()