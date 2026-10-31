import os
import json
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        if self.provider == "groq":
            self.client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=120.0)

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if self.provider == "stub":
            return {"hubs": [{"name": "hub_test", "business_keys": ["id"]}], "links": [], "satellites": []}
            
        if self.provider == "groq":
            resp = self.client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(resp.choices[0].message.content)
            
        elif self.provider == "ollama":
            # Локальный вызов (B2B)
            url = f"{os.getenv('OLLAMA_URL')}/api/generate"
            payload = {
                "model": os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "format": "json",
                "stream": False
            }
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            return json.loads(resp.json()["response"])
            
        raise ValueError(f"Неизвестный провайдер: {self.provider}")