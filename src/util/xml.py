import xml.etree.ElementTree as ET


def set_namespaces(namespaces: dict):
    return {f"xmlns:{k}": v for k, v in namespaces.items()}


def to_webdav(data):
    namespaces = {"d": "DAV:"}

    multistatus = ET.Element(
        "d:multistatus",
        **set_namespaces(namespaces),
    )
    to_webdav_child(multistatus, data)
    return ET.tostring(multistatus, encoding="utf-8")


def to_webdav_child(parent: ET.Element, data: dict):
    for key, value in data.items():
        elem = ET.SubElement(parent, f"d:{key}")
        if isinstance(value, str):
            elem.text = value
        elif isinstance(value, dict):
            to_webdav_child(elem, value)
        elif isinstance(value, list):
            for item in value:
                to_webdav_child(elem, item)
