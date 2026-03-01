import os
import json
from openai import OpenAI

api_key = os.environ.get("OPENROUTER_API_KEY", "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")
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

print("Testing Gemini 3 Flash Code Execution via OpenRouter...")

try:
    response = client.chat.completions.create(
        model="google/gemini-3-flash-preview",
        messages=[{"role": "user", "content": "Write a python script to calculate the 100th fibonacci number and execute it to give me the answer."}],
        temperature=0.1
    )
    print("Response received:")
    # Print the tool calls or the message content
    message = response.choices[0].message
    if message.tool_calls:
        print("Tool calls made!")
        for tool_call in message.tool_calls:
            print(f"Tool Name: {tool_call.function.name}")
            print(f"Arguments: {tool_call.function.arguments}")
    else:
        print("No tool calls. Content:")
        print(message.content)
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, "response"):
        print(e.response.text)
