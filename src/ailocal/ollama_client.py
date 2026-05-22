"""Ollama API client - no function calling, no tools, raw chat."""

import json
import urllib.request
import urllib.error
import subprocess

BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:3b-nt"

SYSTEM_PROMPT = """Eres un asistente de codigo. Puedes LEER y EDITAR archivos existentes.

PARA LEER un archivo existente, usa:
[READ:ruta/del/archivo.py]

PARA CREAR/REEMPLAZAR archivos, usa bloques markdown con ruta:
```python:ruta/del/archivo.py
codigo aqui
```

Para otros lenguajes usa la extensión correspondiente:
```javascript:ruta/file.js
```html:ruta/file.html
```bash:ruta/script.sh

No uses tool calls ni JSON de function calling. Solo las marcas [READ:] y bloques de codigo."""


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
    messages.append({"role": "user", "content": prompt})
    return _chat_request(messages, model, stream)


def chat_stream(prompt: str, model: str = DEFAULT_MODEL, system: str = SYSTEM_PROMPT):
    """Stream response from ollama, yielding tokens."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    yield from _stream_request(messages, model)


def chat_with_history(
    messages: list,
    model: str = DEFAULT_MODEL,
    include_system: bool = True,
):
    """Send a full message history. Used for follow-up turns (e.g. [READ] responses)."""
    return _chat_request(messages, model, stream=False)


def chat_with_history_stream(
    messages: list,
    model: str = DEFAULT_MODEL,
):
    """Stream response from full message history."""
    yield from _stream_request(messages, model)


def _chat_request(messages: list, model: str, stream: bool = False) -> dict:
    """Low-level chat request."""
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


def _stream_request(messages: list, model: str):
    """Low-level streaming request."""
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


# Old chat functions kept for backward compat
def _old_chat(prompt, model, system, stream):
    return chat(prompt, model, system, stream)

def _old_chat_stream(prompt, model, system):
    return chat_stream(prompt, model, system)


def list_models() -> list[str]:
    """List available models from ollama."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        raise OllamaError(f"Failed to list models: {e}") from e
