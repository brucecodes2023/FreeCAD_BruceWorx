"""Set parameters in a FreeCAD user.cfg copy: cfgset.py <cfg> <light|dark|keep> [Path/Name:type=value ...].

light/dark re-applies the BruceWorx preference pack in that mode (theme, stylesheet,
viewport and accent colours) from this checkout; keep leaves the copy as it is.
"""

import os
import sys
import xml.etree.ElementTree as ET

TAGS = {"bool": "FCBool", "int": "FCInt", "uint": "FCUInt", "float": "FCFloat", "text": "FCText"}


def group(root, path):
    node = root.find("FCParamGroup[@Name='Root']")
    for part in path.split("/"):
        nxt = node.find(f"FCParamGroup[@Name='{part}']")
        if nxt is None:
            nxt = ET.SubElement(node, "FCParamGroup", Name=part)
        node = nxt
    return node


def set_param(root, path, name, typ, value):
    g = group(root, path)
    tag = TAGS[typ]
    el = g.find(f"{tag}[@Name='{name}']")
    if el is None:
        el = ET.SubElement(g, tag, Name=name)
    if typ == "text":
        el.text = value
    else:
        el.set("Value", value)


def main(argv):
    cfg, mode, rest = argv[1], argv[2], argv[3:]
    tree = ET.parse(cfg)
    root = tree.getroot()
    if mode in ("light", "dark"):
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(here, "..", "..", "..", "..", "..", "..", "src", "Mod", "BruceWorx"))
        import bruceworx_pack

        for entry in bruceworx_pack.pack_entries(mode):
            value = entry["value"]
            if entry["type"] == "bool":
                value = "1" if value else "0"
            set_param(root, entry["path"], entry["name"], entry["type"], str(value))
    for item in rest:
        key, value = item.split("=", 1)
        path_name, typ = key.rsplit(":", 1)
        path, name = path_name.rsplit("/", 1)
        set_param(root, path, name, typ, value)
    tree.write(cfg, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    main(sys.argv)
