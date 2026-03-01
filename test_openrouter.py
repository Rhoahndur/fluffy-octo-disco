import os
import json
api_key = os.environ.get("OPENROUTER_API_KEY", "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")
from openai import OpenAI
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

try:
    response = client.chat.completions.create(
        model="google/gemini-2.5-flash-preview-05-20",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.1,
    )
    print("SUCCESS")
except Exception as e:
    print(getattr(e, "response", type(e)).text)
