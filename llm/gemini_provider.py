"""Provider de Gemini via API REST."""
from core.interfaces import LLMProvider, LLMMessage, LLMResponse
import requests

class GeminiProvider(LLMProvider):
    """Provider usando Google Gemini API."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    def chat(self, messages, tools=None):
        """Envía mensaje y opcionalmente tools."""
        contents = [{"role": msg.role, "parts": [{"text": msg.content}]} for msg in messages]
        
        payload = {"contents": contents}
        
        if tools:
            payload["tools"] = {
                "functionDeclarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_schema
                    }
                    for t in tools
                ]
            }
        
        try:
            response = requests.post(
                self.url,
                params={"key": self.api_key},
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            data = response.json()
            
            if "candidates" in data:
                candidate = data["candidates"][0]
                content = candidate.get("content", {})
                
                if "parts" in content:
                    for part in content["parts"]:
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            return LLMResponse(
                                text=None,
                                tool_call={
                                    "tool": fc["name"],
                                    "params": fc.get("args", {})
                                }
                            )
                        
                        if "text" in part:
                            return LLMResponse(text=part["text"])
            
            return LLMResponse(text="No entendí. ¿Puedes repetir?")
            
        except Exception as e:
            return LLMResponse(text=f"Error: {str(e)}", tool_call=None)