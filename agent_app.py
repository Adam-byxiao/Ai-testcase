import os
from typing import Annotated, Literal, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from figma_mcp import _parse_figma_design_impl as figma_mcp_tool
from proxy_manager import get_proxy_client, get_async_proxy_client

# --- Define Tools ---

@tool
def get_figma_context(file_path: str) -> str:
    """
    Parses a Figma JSON file to extract UI structure and content.
    Use this tool when you need to understand the design before writing documentation or test cases.
    """
    # Directly call the function from our MCP implementation
    # This allows us to use the same logic locally without a running MCP server
    return figma_mcp_tool(file_path)

# --- Define Agent State ---

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- Define Agent Logic ---

class FigmaAgent:
    def __init__(self, model_name="gpt-4o"):
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        if not api_key:
            print("Warning: OPENAI_API_KEY not found in environment variables.")
            # We'll allow initialization but execution will fail if key is missing
        
        kwargs = {
            "model": model_name, 
            "temperature": 0,
            "http_client": get_proxy_client(),
            "http_async_client": get_async_proxy_client()
        }
        if base_url:
            kwargs["base_url"] = base_url
            
        self.llm = ChatOpenAI(**kwargs)
        self.tools = [get_figma_context]
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.graph = self._build_graph()

    def _build_graph(self):
        # 1. Define Nodes
        def chatbot(state: AgentState):
            return {"messages": [self.llm_with_tools.invoke(state["messages"])]}

        tool_node = ToolNode(self.tools)

        # 2. Define Conditional Edge
        def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
            messages = state["messages"]
            last_message = messages[-1]
            if last_message.tool_calls:
                return "tools"
            return "__end__"

        # 3. Build Graph
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", chatbot)
        workflow.add_node("tools", tool_node)

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    def run(self, user_input: str):
        """Runs the agent with the given input and returns the final response text."""
        final_response = ""
        input_message = {"role": "user", "content": user_input}
        
        # Stream the execution to show progress
        print(f"\n[Agent] Processing: {user_input[:50]}...")
        
        try:
            for event in self.graph.stream({"messages": [input_message]}):
                for value in event.values():
                    if "messages" in value:
                        msg = value["messages"][-1]
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            print(f"  -> Calling Tool: {msg.tool_calls[0]['name']}")
                        elif hasattr(msg, "content") and msg.content:
                            # Final response usually
                            final_response = msg.content
        except Exception as e:
            return f"Error running agent: {e}"
            
        return final_response

if __name__ == "__main__":
    # Simple test
    agent = FigmaAgent()
    print("Agent initialized.")
