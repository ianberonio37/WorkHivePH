"""
Live test of the Claude Token Router.
Run from the project root: python test_token_routing.py
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load API key from test-data-seeder/.env
load_dotenv(Path(__file__).parent / "test-data-seeder" / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from tools.claude_token_tracker import TrackedClient
from tools.claude_model_router import ModelRouter

router = ModelRouter()
client = TrackedClient()

# Three test calls — router picks the model for each
tests = [
    ("search",      "List all the action types the token router knows about."),
    ("explanation", "In one sentence, explain what prompt caching does in the Claude API."),
    ("debugging",   "In one sentence, what is the most common cause of a Python UnboundLocalError?"),
]

print("\n=== Live Claude Token Routing Test ===\n")

for action, prompt in tests:
    model = router.suggest(action)
    print(f"Action : {action}")
    print(f"Model  : {model}")
    print(f"Prompt : {prompt}")

    response = client.chat(prompt, model=model, action_type=action, max_tokens=256)
    reply = response.content[0].text.strip()
    tokens = response.usage.input_tokens + response.usage.output_tokens

    print(f"Reply  : {reply}")
    print(f"Tokens : {tokens}  |  Cost: ${(tokens * 0.000005):.6f}")
    print()

print("All calls logged. Run 'python tools/analyze_tokens.py' to see updated stats.")
