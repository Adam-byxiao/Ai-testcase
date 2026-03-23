import os
import tempfile
import requests


def download_image(image_url: str) -> str:
    timeout = float(os.getenv("FIGMA_IMAGE_TIMEOUT_SEC", "60"))
    retries = int(os.getenv("FIGMA_IMAGE_RETRY", "2"))
    figma_proxy = os.getenv("FIGMA_PROXY")
    proxies = {"http": figma_proxy, "https": figma_proxy} if figma_proxy else None
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = requests.get(image_url, timeout=timeout, proxies=proxies)
            resp.raise_for_status()
            fd, path = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(resp.content)
            return path
        except Exception as e:
            last_err = e
            continue
    raise last_err
