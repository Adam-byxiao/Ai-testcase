from fastmcp import FastMCP
from figma_parser import FigmaParser
import os

# Create a FastMCP server named "Figma MCP"
mcp = FastMCP("Figma MCP")

def _parse_figma_design_impl(file_path: str) -> str:
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        parser = FigmaParser(file_path)
        return parser.get_summary()
    except Exception as e:
        return f"Error parsing Figma file: {str(e)}"

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

if __name__ == "__main__":
    # If run directly, this starts the MCP server
    mcp.run()
