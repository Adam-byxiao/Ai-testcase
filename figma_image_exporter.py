import os
import requests
from typing import Optional, Dict, List, Tuple

FIGMA_API_BASE = "https://api.figma.com/v1"


def _get_figma_token() -> str:
    token = os.getenv("FIGMA_TOKEN")
    if not token:
        raise ValueError("FIGMA_TOKEN is not set in environment variables.")
    return token


def _headers() -> Dict[str, str]:
    return {"X-Figma-Token": _get_figma_token()}


def _proxies() -> Dict[str, str] | None:
    figma_proxy = os.getenv("FIGMA_PROXY")
    if not figma_proxy:
        return None
    return {"http": figma_proxy, "https": figma_proxy}


def get_figma_file(file_key: str) -> dict:
    url = f"{FIGMA_API_BASE}/files/{file_key}"
    resp = requests.get(url, headers=_headers(), timeout=20)
    if resp.status_code != 200:
        raise ValueError(f"Figma API error {resp.status_code}: {resp.text}")
    return resp.json()


def get_first_page_node_id(file_key: str) -> str:
    file_json = get_figma_file(file_key)
    document = file_json.get("document", {})
    pages = document.get("children", [])
    if not pages:
        raise ValueError("No pages found in Figma document.")
    return pages[0].get("id")


def export_figma_images(file_key: str, node_ids: List[str], image_format: str = "png", scale: float = 2.0) -> Dict[str, str]:
    if not node_ids:
        raise ValueError("node_ids is required")
    url = f"{FIGMA_API_BASE}/images/{file_key}"
    resp = requests.get(
        url,
        headers=_headers(),
        params={"ids": ",".join(node_ids), "format": image_format, "scale": scale},
        timeout=20,
        proxies=_proxies(),
    )
    if resp.status_code != 200:
        raise ValueError(f"Figma API error {resp.status_code}: {resp.text}")
    data = resp.json()
    return data.get("images", {})


def export_figma_image(file_key: str, node_id: Optional[str] = None, image_format: str = "png", scale: float = 2.0) -> Tuple[str, str]:
    """
    Export a single image. If node_id is None, export the first page (canvas).
    Returns (image_url, used_node_id).
    """
    used_node_id = node_id or get_first_page_node_id(file_key)
    images = export_figma_images(file_key, [used_node_id], image_format=image_format, scale=scale)
    image_url = images.get(used_node_id)
    if not image_url:
        raise ValueError("Failed to export image from Figma.")
    return image_url, used_node_id
