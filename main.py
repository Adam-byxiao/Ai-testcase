import os
import sys
from dotenv import load_dotenv
from agent_app import FigmaAgent

# Load environment variables
load_dotenv()

# Configuration
FIGMA_FILE = r"f:\python\Ai-testcase\figma-json\figma_wpQSkv1J7nNG4YPTwF34ma_31063-12935.json"
OUTPUT_DIR = r"f:\python\Ai-testcase\output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Figma to Test Case Agent (LangGraph + MCP) ---")
    
    # Check for API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[Error] OPENAI_API_KEY is not set.")
        print("Please create a .env file based on .env.example and add your API key.")
        print("Example: OPENAI_API_KEY=sk-...")
        return

    # Initialize Agent
    try:
        agent = FigmaAgent(model_name="gpt-4o")
        print("Agent initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return

    # Task 1: Generate PRD
    print(f"\n[Task 1] Analyzing design and generating PRD...")
    prompt_prd = f"""
    Please analyze the Figma design file at '{FIGMA_FILE}'.
    Understand the UI structure, text, and interactions.
    Then, generate a Product Requirement Document (PRD) in Simplified Chinese (zh-CN).
    The PRD should include:
    1. Overview
    2. User Flow
    3. Screen Details (Elements, Interactions)
    4. Technical Requirements
    """
    
    prd_content = agent.run(prompt_prd)
    
    prd_path = os.path.join(OUTPUT_DIR, "generated_prd_agent.md")
    with open(prd_path, "w", encoding="utf-8") as f:
        f.write(prd_content)
    print(f" -> PRD saved to: {prd_path}")

    # Task 2: Generate Test Cases
    print(f"\n[Task 2] Generating Test Cases from PRD...")
    prompt_tc = f"""
    Based on the following PRD content, generate a comprehensive set of test cases in Simplified Chinese (zh-CN).
    Format the output as a Markdown table with columns: ID, Test Scenario, Pre-conditions, Steps, Expected Result, Priority.
    
    PRD Content:
    {prd_content}
    """
    
    tc_content = agent.run(prompt_tc)
    
    tc_path = os.path.join(OUTPUT_DIR, "generated_test_cases_agent.md")
    with open(tc_path, "w", encoding="utf-8") as f:
        f.write(tc_content)
    print(f" -> Test Cases saved to: {tc_path}")

    print("\n--- Workflow Completed ---")

if __name__ == "__main__":
    main()
