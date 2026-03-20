"""Manage the guestlist XML file locally (TM2020 SaveGuestList RPC is broken)."""

import logging
import xml.etree.ElementTree as ET

log = logging.getLogger("cmnd/ctrl")

_HEADER = '<?xml version="1.0" encoding="utf-8" ?>\n'


def load(path: str) -> set[str]:
    """Parse a TM guestlist XML file and return a set of logins."""
    try:
        tree = ET.parse(path)
        return {
            el.text.strip()
            for el in tree.findall(".//player/login")
            if el.text and el.text.strip()
        }
    except (FileNotFoundError, ET.ParseError) as e:
        log.warning("Could not load guestlist %s: %s", path, e)
        return set()


def save(path: str, logins: set[str]):
    """Write a set of logins to a TM guestlist XML file."""
    root = ET.Element("guestlist")
    for login in sorted(logins):
        player = ET.SubElement(root, "player")
        login_el = ET.SubElement(player, "login")
        login_el.text = login
    ET.indent(root, space="\t")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_HEADER)
        ET.ElementTree(root).write(f, encoding="unicode", xml_declaration=False)
        f.write("\n")
