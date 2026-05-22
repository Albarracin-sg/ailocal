"""Ollama API client - no function calling, no tools, raw chat."""

import json
import urllib.request
import urllib.error
import subprocess

BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:3b-nt"

SYSTEM_PROMPT = """Eres un asistente de codigo. Cuando te pidan crear archivos, USA EL SIGUIENTE FORMATO EXACTO para cada archivo:

```python:ruta/del/archivo.py
codigo aqui
```

La ruta debe incluir el directorio si aplica, ej: inventario/main.py
No uses tool calls ni JSON de function calling. Solo codigo markdown con rutas."""


class OllamaError(Exception):
    pass


def chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: str = SYSTEM_PROMPT,
    stream: bool = False,
) -> dict:
    """Send a chat request to ollama and return the response."""
    messages = [{"role": "system", "content": system}]
    
    # Si el prompt viene con stdin (varias lineas), lo enviamos completo
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": stream,
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise OllamaError(f"Error connecting to ollama: {e}") from e
    except json.JSONDecodeError as e:
        raise OllamaError(f"Invalid JSON response: {e}") from e

    return data


def chat_stream(prompt: str, model: str = DEFAULT_MODEL, system: str = SYSTEM_PROMPT):
    """Stream response from ollama, yielding tokens."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            buffer = b""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk
                # Try to parse complete lines
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done"):
                                return
                        except json.JSONDecodeError:
                            pass
    except urllib.error.URLError as e:
        raise OllamaError(f"Connection error: {e}") from e


def list_models() -> list[str]:
    """List available models from ollama."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        raise OllamaError(f"Failed to list models: {e}") from e
