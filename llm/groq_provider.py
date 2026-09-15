"""Provider de Groq via API REST."""

from __future__ import annotations

import json
import re
import time
import unicodedata
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
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[Tool] | None = None,
    ) -> LLMResponse:
        payload = self._build_payload(messages, tools or [])

        for attempt in range(self.max_retries + 1):
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

                if response.status_code == 429 and attempt < self.max_retries:
                    wait_s = self._extract_retry_wait(data, response.headers)
                    time.sleep(wait_s)
                    continue

                if response.status_code >= 400:
                    return LLMResponse(
                        text=None,
                        tool_call=None,
                        raw=data,
                        error=self._extract_api_error(data, response.status_code),
                    )

                return self._parse_response(data)

            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return LLMResponse(text=None, tool_call=None, error=f"Error de red: {exc}")
            except ValueError as exc:
                return LLMResponse(text=None, tool_call=None, error=f"Respuesta no JSON: {exc}")

        return LLMResponse(
            text=None,
            tool_call=None,
            error="Groq API HTTP 429: límite de tokens por minuto agotado tras varios reintentos.",
        )

    def _extract_retry_wait(self, data: dict[str, Any], headers) -> float:
        """
        Calcula cuánto esperar antes de reintentar.
        Prioridad: mensaje de error de Groq ('try again in 480ms') >
        header Retry-After > valor por defecto (1.5s).
        """
        message = (data.get("error", {}) or {}).get("message", "")

        match = re.search(r"try again in\s+([\d.]+)(ms|s)", message, re.IGNORECASE)
        if match:
            value, unit = match.groups()
            wait = float(value) / 1000 if unit.lower() == "ms" else float(value)
            return max(wait, 0.05) + 0.1  # pequeño margen de seguridad

        retry_after = headers.get("Retry-After") if headers else None
        if retry_after:
            try:
                return float(retry_after) + 0.1
            except ValueError:
                pass

        return 1.5

    @staticmethod
    def _normalize(text: str) -> str:
        """Elimina tildes y caracteres especiales para evitar errores en Groq."""
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

    def _build_payload(self, messages: list[LLMMessage], tools: list[Tool]) -> dict[str, Any]:
        formatted = []
        for msg in messages:
            role = msg.role.lower()
            if role not in ("system", "assistant", "user"):
                role = "user"
            content = self._normalize((msg.content or "").strip())
            if not content:
                continue
            formatted.append({"role": role, "content": content})

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted,
            "temperature": 0.3,
        }

        if tools:
            tools_formatted = []
            for tool in tools:
                schema = tool.parameters_schema or {"type": "object", "properties": {}}
                if "required" not in schema:
                    schema = dict(schema)
                    schema["required"] = []
                tools_formatted.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": self._normalize(tool.description or ""),
                        "parameters": schema,
                    },
                })
            payload["tools"] = tools_formatted
            payload["tool_choice"] = "auto"

        return payload

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(text=None, tool_call=None, raw=data, error="Groq no devolvio respuestas.")

        message = choices[0].get("message", {})

        tool_calls = message.get("tool_calls")
        if tool_calls:
            tc = tool_calls[0]
            function = tc.get("function", {})
            params = function.get("arguments", "{}")
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}
            return LLMResponse(
                text=None,
                tool_call={"tool": function.get("name", ""), "params": params},
                raw=data,
            )

        text = message.get("content", "").strip()
        if text:
            return LLMResponse(text=text, tool_call=None, raw=data)

        return LLMResponse(text=None, tool_call=None, raw=data, error="Groq no devolvio texto ni herramienta.")

    def _extract_api_error(self, data: dict[str, Any], status_code: int) -> str:
        error = data.get("error", {})
        message = error.get("message") or str(data)
        return f"Groq API HTTP {status_code}: {message}"