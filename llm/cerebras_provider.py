"""Proveedor de Cerebras (compatible con OpenAI)."""
import os
import json
from openai import OpenAI
from typing import List, Optional
from core.interfaces import LLMMessage, LLMResponse


class CerebrasProvider:
    """Cliente para Cerebras API."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("CEREBRAS_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "llama-3.3-70b")

        if not self.api_key:
            raise ValueError("Falta CEREBRAS_API_KEY en el archivo .env")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.cerebras.ai/v1"
        )

    def chat(self, messages: List[LLMMessage], tools: Optional[List] = None) -> LLMResponse:
        """Envía mensajes a Cerebras y retorna un LLMResponse."""
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
                            "parameters": t.parameters_schema,
                        }
                    }
                    for t in tools
                ]
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            if message.tool_calls:
                tc = message.tool_calls[0]
                params = json.loads(tc.function.arguments)
                return LLMResponse(
                    text=None,
                    tool_call={"tool": tc.function.name, "params": params},
                    error=None,
                )

            return LLMResponse(text=message.content, tool_call=None, error=None)

        except Exception as e:
            return LLMResponse(text=None, tool_call=None, error=str(e))