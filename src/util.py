import re

def unify_mac_address(mac_address: str) -> str:
    cleaned_mac = re.sub(r"[^0-9a-fA-F]", "", mac_address)
    formatted_mac = ":".join([cleaned_mac[i : i + 2] for i in range(0, 12, 2)])
    return formatted_mac.upper()