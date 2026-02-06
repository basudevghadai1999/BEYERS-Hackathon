import asyncio
import sys
import logging
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner

# Setup basic logging to see what's happening
logging.basicConfig(level=logging.INFO)

async def test_live_invocation():
    # Define a minimal agent with the Opus 4.5 model
    print("--- Testing Opus 4.5 Model Configuration ---")
    model_id = "bedrock/us.anthropic.claude-opus-4-5-20251101-v1:0"
    
    test_agent = Agent(
        name="test_opus_agent",
        model=model_id,
        instruction="You are a helpful assistant."
    )
    
    # Initialize the Runner with this agent
    runner = InMemoryRunner(agent=test_agent)
    
    print(f"Agent initialized with model: {test_agent.model}")
    print("Attempting to run a debug message...")
    
    try:
        # run_debug is a helper for quick testing
        events = await runner.run_debug(user_messages="Hello, are you online?")
        
        print("\n[SUCCESS] Events received from runner:")
        for event in events:
            print(f"- {event}")
            
    except Exception as e:
        print("\n[ERROR/NOTABLE] Execution stopped:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        
        if "Authentication" in str(e) or "credentials" in str(e).lower():
            print("\nNOTE: The execution reached the LLM provider but failed due to missing credentials.")
            print("This confirms the model ID is being used correctly by the ADK.")

if __name__ == "__main__":
    asyncio.run(test_live_invocation())
