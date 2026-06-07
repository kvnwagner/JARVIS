"""Provider de Groq via API REST."""

from __future__ import annotations

from typing import Any

import requests

from core.interfaces import LLMMessage, LLMProvider, LLMResponse, Tool


class GroqProvider(LLMProvider):
    """Provider usando Groq API con soporte de function calling."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[Tool] | None = None,
    ) -> LLMResponse:
        """Envía mensajes a Groq y devuelve texto o una llamada a herramienta."""
        payload = self._build_payload(messages, tools or [])

        try:
            response = requests.post(
                self.url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=self.timeout,
            )
            data = response.json()

            if response.status_code >= 400:
                return LLMResponse(
                    text=None,
                    tool_call=None,
                    raw=data,
                    error=self._extract_api_error(data, response.status_code),
                )

            return self._parse_response(data)

        except requests.RequestException as exc:
            return LLMResponse(
                text=None,
                tool_call=None,
                error=f"Error de red hablando con Groq: {exc}",
            )
        except ValueError as exc:
            return LLMResponse(
                text=None,
                tool_call=None,
                error=f"Groq devolvió una respuesta no JSON: {exc}",
            )

    def _build_payload(self, messages: list[LLMMessage], tools: list[Tool]) -> dict[str, Any]:
        formatted = []
        for msg in messages:
            role = msg.role.lower()
            if role == "assistant":
                role = "assistant"
            elif role == "system":
                role = "system"
            else:
                role = "user"
            formatted.append({"role": role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted,
            "temperature": 0.7,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema,
                    },
                }
                for tool in tools
            ]
            payload["tool_choice"] = "auto"

        return payload

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(
                text=None,
                tool_call=None,
                raw=data,
                error="Groq no devolvió respuestas.",
            )

        message = choices[0].get("message", {})

        # Tool call
        tool_calls = message.get("tool_calls")
        if tool_calls:
            tc = tool_calls[0]
            import json
            function = tc.get("function", {})
            params = function.get("arguments", "{}")
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}
            return LLMResponse(
                text=None,
                tool_call={
                    "tool": function.get("name", ""),
                    "params": params,
                },
                raw=data,
            )

        # Texto normal
        text = message.get("content", "").strip()
        if text:
            return LLMResponse(text=text, tool_call=None, raw=data)

        return LLMResponse(
            text=None,
            tool_call=None,
            raw=data,
            error="Groq no devolvió texto ni herramienta.",
        )

    def _extract_api_error(self, data: dict[str, Any], status_code: int) -> str:
        error = data.get("error", {})
        message = error.get("message") or str(data)
        return f"Groq API HTTP {status_code}: {message}"