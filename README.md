# ailocal

CLI tool for coding with local ollama models. No function-calling, no tool injection — just raw code generation and file creation.

## Install

```bash
git clone https://github.com/Albarracin-sg/ailocal
cd ailocal
# add to path: PYTHONPATH=./src:$PYTHONPATH
alias ailocal='PYTHONPATH=/path/to/ailocal/src:$PYTHONPATH python3 -m ailocal'
```

## Usage

```bash
# interactive mode
ailocal

# one-shot
ailocal "create a Flask REST API..."

# pipe
echo "fix this bug" | ailocal

# options
ailocal --model qwen2.5-coder:1.5b
ailocal --dir ./myproject
ailocal -l              # list models
```

## Requires

- Python 3.10+
- Ollama running (docker or local)
- A model pulled (e.g. `qwen2.5-coder:3b-nt`)
