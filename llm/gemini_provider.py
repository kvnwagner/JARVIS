"""Provider de Gemini via API REST."""

from __future__ import annotations

from typing import Any

import requests

from core.interfaces import LLMMessage, LLMProvider, LLMResponse, Tool


class GeminiProvider(LLMProvider):
    """Provider usando Google Gemini API con soporte de function calling."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent"
        )

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[Tool] | None = None,
    ) -> LLMResponse:
        """Envía mensajes a Gemini y devuelve texto o una llamada a herramienta."""
        payload = self._build_payload(messages, tools or [])

        try:
            response = requests.post(
                self.url,
                params={"key": self.api_key},
                json=payload,
                headers={"Content-Type": "application/json"},
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
                error=f"Error de red hablando con Gemini: {exc}",
            )
        except ValueError as exc:
            return LLMResponse(
                text=None,
                tool_call=None,
                error=f"Gemini devolvió una respuesta no JSON: {exc}",
            )

    def _build_payload(self, messages: list[LLMMessage], tools: list[Tool]) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        system_parts: list[dict[str, str]] = []

        for message in messages:
            role = message.role.lower()
            if role == "system":
                system_parts.append({"text": message.content})
                continue

            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": message.content}],
                }
            )

        payload: dict[str, Any] = {"contents": contents}

        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters_schema,
                        }
                        for tool in tools
                    ]
                }
            ]

        return payload

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        candidates = data.get("candidates") or []
        if not candidates:
            return LLMResponse(
                text=None,
                tool_call=None,
                raw=data,
                error="Gemini no devolvió candidatos de respuesta.",
            )

        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])

        for part in parts:
            if "functionCall" in part:
                function_call = part["functionCall"]
                return LLMResponse(
                    text=None,
                    tool_call={
                        "tool": function_call.get("name", ""),
                        "params": function_call.get("args", {}),
                    },
                    raw=data,
                )

        text = "".join(part.get("text", "") for part in parts).strip()
        if text:
            return LLMResponse(text=text, tool_call=None, raw=data)

        finish_reason = candidate.get("finishReason", "desconocida")
        return LLMResponse(
            text=None,
            tool_call=None,
            raw=data,
            error=f"Gemini no devolvió texto ni herramienta. finishReason={finish_reason}",
        )

    def _extract_api_error(self, data: dict[str, Any], status_code: int) -> str:
        api_error = data.get("error", {})
        message = api_error.get("message") or str(data)
        return f"Gemini API HTTP {status_code}: {message}"
