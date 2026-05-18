"""Offline OUI (MAC vendor) lookup — no internet required."""

# Trimmed OUI database focused on ISP/networking equipment vendors
_OUI_DB: dict[str, str] = {
    # MikroTik
    "000C42": "MikroTik", "4C5E0C": "MikroTik", "B869F4": "MikroTik",
    "D401C3": "MikroTik", "CC2DE0": "MikroTik", "488F5A": "MikroTik",
    "744D28": "MikroTik", "DC2C6E": "MikroTik", "E48D8C": "MikroTik",
    "2CC81B": "MikroTik", "6C3B6B": "MikroTik", "08555C": "MikroTik",
    "18FD74": "MikroTik", "C4AD34": "MikroTik", "E4CE8F": "MikroTik",
    "64D154": "MikroTik", "B8B253": "MikroTik", "DC9FA4": "MikroTik",
    "2C573D": "MikroTik",
    # Ubiquiti
    "002722": "Ubiquiti", "0418D6": "Ubiquiti", "24A43C": "Ubiquiti",
    "44D9E7": "Ubiquiti", "687251": "Ubiquiti", "784558": "Ubiquiti",
    "802AA8": "Ubiquiti", "DC9FDB": "Ubiquiti", "F09FC2": "Ubiquiti",
    "FCECDA": "Ubiquiti", "00156D": "Ubiquiti", "E063DA": "Ubiquiti",
    "788A20": "Ubiquiti", "D021F9": "Ubiquiti", "F492BF": "Ubiquiti",
    "68D79A": "Ubiquiti", "0418D6": "Ubiquiti", "B4FBE4": "Ubiquiti",
    # TP-Link
    "000AEB": "TP-Link", "001122": "TP-Link", "14CC20": "TP-Link",
    "1C61B4": "TP-Link", "30B5C2": "TP-Link", "50C7BF": "TP-Link",
    "60E3272": "TP-Link", "98DABC": "TP-Link", "A0F3C1": "TP-Link",
    "C46E1F": "TP-Link", "D46AA8": "TP-Link", "E80480": "TP-Link",
    # Cisco
    "00000C": "Cisco", "001AA1": "Cisco", "001B54": "Cisco",
    "001E68": "Cisco", "002155": "Cisco", "002BCD": "Cisco",
    "5006AB": "Cisco", "70697F": "Cisco", "888475": "Cisco",
    "A4435B": "Cisco", "B4A4E3": "Cisco", "CC4694": "Cisco",
    "E8BA70": "Cisco", "F4CFE2": "Cisco",
    # Huawei
    "001882": "Huawei", "002568": "Huawei", "0025136": "Huawei",
    "287B09": "Huawei", "30D17E": "Huawei", "48AD08": "Huawei",
    "4C1FCC": "Huawei", "5C4CCA": "Huawei", "70720D": "Huawei",
    "88E3AB": "Huawei", "AC853D": "Huawei", "D440F0": "Huawei",
    "E8088B": "Huawei", "F4830E": "Huawei",
    # Intelbras
    "000FB5": "Intelbras", "506313": "Intelbras", "E8C8B4": "Intelbras",
    "9C9C1F": "Intelbras", "001DB9": "Intelbras",
    # Motorola
    "000ABF": "Motorola", "001C10": "Motorola", "002168": "Motorola",
    # Netgear
    "00146C": "Netgear", "001E2A": "Netgear", "00224B": "Netgear",
    "083FBC": "Netgear", "10FEed": "Netgear", "20E52A": "Netgear",
    # D-Link
    "001346": "D-Link", "0019DB": "D-Link", "001CF0": "D-Link",
    "00265A": "D-Link", "14D64D": "D-Link", "1C5F2B": "D-Link",
    # Asus
    "002369": "Asus", "049226": "Asus", "083FBC": "Asus",
    "107B44": "Asus", "1C872C": "Asus", "2C56DC": "Asus",
    # Apple
    "000A27": "Apple", "000A95": "Apple", "001451": "Apple",
    "001B63": "Apple", "001CB3": "Apple", "0023DF": "Apple",
    "003065": "Apple", "0050E4": "Apple", "0C1539": "Apple",
    "101C0C": "Apple", "1499E2": "Apple", "18AF61": "Apple",
    # Samsung
    "002339": "Samsung", "0026E2": "Samsung", "08FD0E": "Samsung",
    "2C44FD": "Samsung", "38AA3C": "Samsung", "5C0A5B": "Samsung",
    # Raspberry Pi
    "B827EB": "Raspberry Pi", "DCA632": "Raspberry Pi", "E45F01": "Raspberry Pi",
    # VMware
    "000C29": "VMware", "000569": "VMware", "001C14": "VMware",
    # VirtualBox
    "080027": "VirtualBox",
}


def lookup_vendor(mac: str) -> str:
    """Return vendor name for a MAC address. Works fully offline."""
    if not mac:
        return "Unknown"
    normalized = mac.upper().replace(":", "").replace("-", "").replace(".", "")
    if len(normalized) < 6:
        return "Unknown"
    oui = normalized[:6]
    return _OUI_DB.get(oui, "Unknown")


def is_mikrotik(mac: str) -> bool:
    return lookup_vendor(mac) == "MikroTik"


def is_ubiquiti(mac: str) -> bool:
    return lookup_vendor(mac) == "Ubiquiti"
