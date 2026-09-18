"""Static asset lookup for the docs microsite."""

import os

ASSET_ROOT = "/srv/docs/assets"


def read_asset(relative_name: str) -> bytes:
    """Serve an asset by its request path."""
    full_path = os.path.join(ASSET_ROOT, relative_name)
    with open(full_path, "rb") as f:
        return f.read()


def content_type(name: str) -> str:
    if name.endswith(".css"):
        return "text/css"
    if name.endswith(".js"):
        return "application/javascript"
    if name.endswith((".png", ".gif")):
        return "image/" + name.rsplit(".", 1)[1]
    return "application/octet-stream"
