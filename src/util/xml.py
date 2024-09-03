import xml.etree.ElementTree as ET
from typing import Union


def set_namespaces(namespaces: dict):
    return {f"xmlns:{k}": v for k, v in namespaces.items()}


def to_webdav(data) -> bytes:
    namespaces = {"d": "DAV:"}

    multistatus = ET.Element(
        "d:multistatus",
        **set_namespaces(namespaces),
    )
    to_webdav_child(multistatus, data)
    return ET.tostring(
        multistatus,
        encoding="utf-8",
        xml_declaration=True,
    )


def to_webdav_child(parent: ET.Element, data: Union[dict, list]):
    if isinstance(data, list):
        for item in data:
            to_webdav_child(parent, item)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                ET.SubElement(parent, f"d:{key}").text = value
            else:
                to_webdav_child(ET.SubElement(parent, f"d:{key}"), value)
