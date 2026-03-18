import json
import os

class FigmaParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None

    def load_data(self):
        """Load the JSON data from the file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def extract_context(self):
        """Extract relevant UI context from the loaded data."""
        if not self.data:
            self.load_data()
        
        # The root usually contains a 'nodes' dictionary. 
        # We'll try to find the first document node.
        nodes = self.data.get('nodes', {})
        if not nodes:
            return {"error": "No nodes found in JSON"}
            
        # For this specific file, we know the key, but let's be generic
        # We process all top-level nodes found
        extracted_roots = []
        for node_id, node_data in nodes.items():
            document = node_data.get('document')
            if document:
                extracted_roots.append(self._traverse_node(document))
        
        return extracted_roots

    def _traverse_node(self, node):
        """Recursively traverse nodes and extract meaningful info."""
        node_type = node.get('type')
        node_name = node.get('name')
        node_id = node.get('id')
        
        # Base info
        info = {
            'id': node_id,
            'name': node_name,
            'type': node_type
        }

        # Extract Text Content
        if node_type == 'TEXT':
            info['content'] = node.get('characters', '')

        # Extract Interaction Properties (if any)
        if node.get('transitionNodeID'):
            info['interaction'] = {
                'trigger': 'onClick', # Simplified assumption
                'navigate_to': node.get('transitionNodeID')
            }

        # Recursive Traversal for Children
        # We only traverse children for container types
        if node.get('children'):
            children = []
            for child in node.get('children', []):
                child_info = self._traverse_node(child)
                if child_info:
                    children.append(child_info)
            if children:
                info['children'] = children
        
        # Filtering Logic to reduce noise
        # We keep containers, text, and components/instances (which are often interactive)
        relevant_types = [
            'CANVAS', 'SECTION', 'FRAME', 'GROUP', 
            'COMPONENT', 'INSTANCE', 'COMPONENT_SET', 
            'TEXT', 'SYMBOL'
        ]
        
        # Logic: 
        # 1. Always keep relevant types.
        # 2. Keep other types ONLY if they have children (might be a custom group/button background).
        # 3. Discard pure vector/shape nodes if they are leaf nodes (visual noise).
        
        is_relevant = node_type in relevant_types
        has_children = 'children' in info and len(info['children']) > 0
        
        if is_relevant or has_children:
            return info
            
        return None

    def get_summary(self):
        """Returns a string summary of the structure."""
        context = self.extract_context()
        return json.dumps(context, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # Test with the provided file
    file_path = r"f:\python\Ai-testcase\figma-json\figma_wpQSkv1J7nNG4YPTwF34ma_31063-12935.json"
    parser = FigmaParser(file_path)
    try:
        print(parser.get_summary()[:2000] + "\n... (truncated)")
    except Exception as e:
        print(f"Error: {e}")
