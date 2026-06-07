"""Proveedor de DeepSeek compatible con OpenAI."""
import os
import json
from openai import OpenAI
from typing import List, Optional
from core.interfaces import LLMMessage, LLMResponse


class DeepSeekProvider:
    """Cliente para DeepSeek API (compatible con OpenAI)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")

        if not self.api_key:
            raise ValueError("Falta OPENAI_API_KEY en el archivo .env para DeepSeek")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def chat(self, messages: List[LLMMessage], tools: Optional[List] = None) -> LLMResponse:
        """Envía mensajes a DeepSeek y retorna un LLMResponse."""
        try:
            raw_messages = [{"role": m.role, "content": m.content} for m in messages]

            kwargs = dict(
                model=self.model,
                messages=raw_messages,
                temperature=0.7,
                max_tokens=1000,
            )

            if tools:
                kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters_schema,  # ← corregido
                        }
                    }
                    for t in tools
                ]
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            # Tool call
            if message.tool_calls:
                tc = message.tool_calls[0]
                params = json.loads(tc.function.arguments)
                return LLMResponse(
                    text=None,
                    tool_call={"tool": tc.function.name, "params": params},
                    error=None,
                )

            # Texto normal
            return LLMResponse(text=message.content, tool_call=None, error=None)

        except Exception as e:
            return LLMResponse(text=None, tool_call=None, error=str(e))