"""Proveedor de Cerebras (compatible con OpenAI)."""
import os
import json
import time
import logging
from openai import OpenAI, RateLimitError
from typing import List, Optional
from core.interfaces import LLMMessage, LLMResponse

logger = logging.getLogger("jarvis.llm")


class CerebrasProvider:
    """Cliente para Cerebras API."""

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or os.getenv("CEREBRAS_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-oss-120b")

        if not self.api_key:
            raise ValueError("Falta CEREBRAS_API_KEY en el archivo .env")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.cerebras.ai/v1"
        )

    def chat(self, messages: List[LLMMessage], tools: Optional[List] = None) -> LLMResponse:
        """Envía mensajes a Cerebras y retorna un LLMResponse."""
        max_retries = 4
        delay = 2  # segundos iniciales

        for attempt in range(max_retries):
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

            except RateLimitError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit Cerebras (intento {attempt + 1}/{max_retries}), reintentando en {delay}s...")
                    time.sleep(delay)
                    delay *= 2  # backoff exponencial: 2s → 4s → 8s → 16s
                else:
                    logger.error("Rate limit Cerebras agotado tras todos los reintentos.")
                    return LLMResponse(text=None, tool_call=None, error=str(e))

            except Exception as e:
                return LLMResponse(text=None, tool_call=None, error=str(e))