from fastmcp import FastMCP
from figma_parser import FigmaParser
from figma_image_exporter import export_figma_image as _export_figma_image
import os
import requests
import json

# Create a FastMCP server named "Figma MCP"
mcp = FastMCP("Figma MCP")

def _parse_figma_design_impl(file_path: str) -> str:
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        parser = FigmaParser(file_path=file_path)
        return parser.get_summary()
    except Exception as e:
        return f"Error parsing Figma file: {str(e)}"

def _build_parser_data_from_file_response(file_json: dict) -> dict:
    document = file_json.get("document")
    if not document:
        return {"nodes": {}}
    return {"nodes": {"root": {"document": document}}}

def _fetch_figma_api_json(file_key: str, node_id: str | None = None) -> dict:
    token = os.getenv("FIGMA_TOKEN")
    if not token:
        raise ValueError("FIGMA_TOKEN is not set in environment variables.")

    headers = {"X-Figma-Token": token}
    proxies = {}
    figma_proxy = os.getenv("FIGMA_PROXY")
    if figma_proxy:
        proxies = {"http": figma_proxy, "https": figma_proxy}

    if node_id:
        url = f"https://api.figma.com/v1/files/{file_key}/nodes"
        resp = requests.get(url, headers=headers, params={"ids": node_id}, timeout=20, proxies=proxies or None)
    else:
        url = f"https://api.figma.com/v1/files/{file_key}"
        resp = requests.get(url, headers=headers, timeout=20, proxies=proxies or None)

    if resp.status_code != 200:
        raise ValueError(f"Figma API error {resp.status_code}: {resp.text}")

    return resp.json()

def fetch_figma_api_json(file_key: str, node_id: str | None = None) -> dict:
    """
    Fetch raw Figma API JSON for a file or specific node.
    """
    return _fetch_figma_api_json(file_key, node_id=node_id)

def get_figma_file_name(file_key: str) -> str:
    file_json = _fetch_figma_api_json(file_key)
    return file_json.get("name", "")

@mcp.tool()
def parse_figma_design(file_path: str) -> str:
    """
    Parses a local Figma JSON file and extracts the UI structure, text content, and interaction elements.
    Use this tool to understand the design before generating PRDs or Test Cases.
    
    Args:
        file_path (str): The absolute path to the local Figma JSON file.
        
    Returns:
        str: A JSON-formatted string containing the simplified UI context (Screens, Texts, Buttons).
    """
    return _parse_figma_design_impl(file_path)

@mcp.tool()
def _parse_figma_file_api(file_key: str, node_id: str | None, include_all_layers: bool) -> str:
    file_json = _fetch_figma_api_json(file_key, node_id=node_id)
    max_nodes_env = os.getenv("FIGMA_LAYER_LIMIT")
    max_nodes = int(max_nodes_env) if max_nodes_env and max_nodes_env.isdigit() else None
    if node_id:
        parser = FigmaParser(data=file_json, include_all_layers=include_all_layers, max_nodes=max_nodes)
    else:
        parser = FigmaParser(
            data=_build_parser_data_from_file_response(file_json),
            include_all_layers=include_all_layers,
            max_nodes=max_nodes
        )
    return parser.get_summary()

@mcp.tool()
def parse_figma_file(file_key: str, node_id: str | None = None) -> str:
    """
    Fetches a Figma file (or a specific node) from the Figma API and extracts a simplified UI summary.

    Args:
        file_key (str): The Figma file key from the file URL.
        node_id (str | None): Optional node id to limit parsing scope.

    Returns:
        str: A JSON-formatted string containing the simplified UI context.
    """
    try:
        return _parse_figma_file_api(file_key, node_id=node_id, include_all_layers=False)
    except Exception as e:
        return f"Error parsing Figma file from API: {str(e)}"

@mcp.tool()
def parse_figma_file_detailed(file_key: str, node_id: str | None = None) -> str:
    """
    Fetches a Figma file (or a specific node) and returns a layer-level UI summary.
    """
    try:
        return _parse_figma_file_api(file_key, node_id=node_id, include_all_layers=True)
    except Exception as e:
        return f"Error parsing Figma file from API: {str(e)}"

@mcp.tool()
def export_figma_image(file_key: str, node_id: str | None = None) -> str:
    """
    Export a Figma page/frame image and return a JSON string with image_url and used_node_id.
    """
    try:
        image_url, used_node_id = _export_figma_image(file_key, node_id=node_id)
        return json.dumps({"image_url": image_url, "node_id": used_node_id}, ensure_ascii=False)
    except Exception as e:
        return f"Error exporting Figma image: {str(e)}"

if __name__ == "__main__":
    # If run directly, this starts the MCP server
    mcp.run()
