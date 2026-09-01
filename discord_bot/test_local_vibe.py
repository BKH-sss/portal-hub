import sys
import os
sys.path.append(r"C:\Users\skbkh\Desktop\html\chat bot")
import asyncio
import json
from llm_orchestrator import orchestrator

async def test_vibe_coding():
    messages = [{"role": "user", "content": "바이브코딩에 대해 알려줘"}]
    system_prompt = "너는 스카디야. 친절하고 똑똑한 반말로 설명해줘."
    
    print("Generating response with local LLM (Ollama) + Grounding...")
    full_text = ""
    async for chunk in orchestrator.stream_chat(
        messages=messages,
        system_prompt=system_prompt,
        target_model="ollama",
        ollama_model_name="qwen2.5:7b",
        enable_grounding=True
    ):
        if chunk.startswith("data: "):
            try:
                data = json.loads(chunk[6:])
                if "content" in data:
                    print(data["content"], end="", flush=True)
                    full_text += data["content"]
                elif "status" in data:
                    print(f"\n[{data.get('status')} - {data.get('label', '')}]")
            except Exception:
                pass
    print("\n--- DONE ---")

if __name__ == "__main__":
    asyncio.run(test_vibe_coding())
