"""CLI interface for ailocal - interactive TUI."""

import sys
import os
import shutil
import textwrap
import time
import select
from pathlib import Path

from ailocal.ollama_client import chat, chat_stream, list_models, DEFAULT_MODEL, OllamaError
from ailocal.file_writer import extract_and_write_files, strip_code_blocks


# ── Terminal helpers ─────────────────────────────────────────────

def term_width() -> int:
    """Get terminal width."""
    return shutil.get_terminal_size().columns


def cprint(text: str, color: str = "", bold: bool = False, end: str = "\n"):
    """Print with ANSI colors."""
    codes = {
        "blue": "34",
        "green": "32",
        "yellow": "33",
        "cyan": "36",
        "magenta": "35",
        "red": "31",
        "dim": "2",
    }
    code = codes.get(color, "")
    if bold and code:
        code = f"1;{code}"
    if code:
        print(f"\033[{code}m{text}\033[0m", end=end)
    else:
        print(text, end=end)


def hr(char: str = "─"):
    """Print a horizontal rule."""
    print(char * min(term_width(), 80))


def wrap(text: str, indent: int = 0) -> str:
    """Wrap text to terminal width."""
    width = min(term_width() - indent - 2, 78)
    return textwrap.fill(text, width=width)


# ── Chat history ──────────────────────────────────────────────────

class ChatHistory:
    """Simple message history for context."""

    def __init__(self, max_messages: int = 20):
        self.messages = []
        self.max_messages = max_messages

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_system_message(self) -> str:
        from ailocal.ollama_client import SYSTEM_PROMPT
        return SYSTEM_PROMPT


# ── Main TUI ──────────────────────────────────────────────────────

def print_banner():
    """Show startup banner."""
    hr("━")
    cprint("  ailocal  —  local AI coding assistant", "cyan", bold=True)
    cprint(f"  model: {DEFAULT_MODEL}", "dim")
    hr("━")
    print()


def show_help():
    """Show help text."""
    print()
    cprint("Commands:", "yellow", bold=True)
    print("  /help       show this help")
    print("  /model      show current model")
    print("  /models     list available models")
    print("  /clear      clear chat history")
    print("  /exit       quit")
    print()


def ask_model(output: str):
    """Display model response nicely."""
    width = min(term_width() - 4, 76)
    
    # Split into lines and wrap
    lines = []
    for line in output.split("\n"):
        if line.strip() == "":
            lines.append("")
        else:
            wrapped = textwrap.fill(line, width=width)
            lines.extend(wrapped.split("\n") if "\n" in wrapped else [wrapped])
    
    for line in lines:
        print(f"  {line}")


def read_input(prompt=">>> ") -> str:
    """Read user input with multi-line paste detection.
    
    If text is pasted (lines arrive quickly), reads all lines as one prompt.
    Single typed lines are processed immediately.
    """
    print(prompt, end="", flush=True)
    
    lines = []
    paste_mode = False
    
    while True:
        # Check if data is available
        r, _, _ = select.select([sys.stdin], [], [], 0.3)
        if r:
            line = sys.stdin.readline()
            if not line:
                break
            lines.append(line.rstrip("\r\n"))
            # If we got data within 300ms, we're likely in paste mode
            paste_mode = True
        elif paste_mode:
            # No more data after paste - finish
            break
        elif lines:
            # Single line, no more data
            break
        else:
            # First line not received yet, wait more
            r, _, _ = select.select([sys.stdin], [], [], None)
            if r:
                line = sys.stdin.readline()
                if not line:
                    break
                lines.append(line.rstrip("\r\n"))
                # Check if more coming
                r, _, _ = select.select([sys.stdin], [], [], 0.3)
                if r:
                    paste_mode = True
                else:
                    break
    
    text = "\n".join(lines).strip()
    return text


def interactive_loop(model: str, workdir: str, history: ChatHistory):
    """Main interactive loop."""
    print_banner()
    print(f"  Working in: {workdir}")
    print(f'  Type "/help" for commands')
    print()

    while True:
        # Prompt
        try:
            user_input = read_input(">>> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # Commands
        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit", "/q"):
                break
            elif cmd == "/help":
                show_help()
                continue
            elif cmd == "/model":
                cprint(f"  Current model: {model}", "cyan")
                continue
            elif cmd == "/models":
                try:
                    models = list_models()
                    cprint("  Available models:", "cyan")
                    for m in models:
                        print(f"    • {m}")
                except OllamaError as e:
                    cprint(f"  Error: {e}", "red")
                continue
            elif cmd == "/clear":
                history.messages.clear()
                cprint("  Chat history cleared.", "yellow")
                continue
            elif cmd in ("/write", "/w"):
                cprint("  /write is automatic — files are created from code blocks.", "dim")
                continue
            else:
                cprint(f"  Unknown command: {cmd}", "red")
                continue

        # Normal message
        hr()

        cprint("  ⏳ working... (model on CPU, may take a moment)", "yellow", bold=True)
        sys.stdout.flush()

        try:
            full_response = ""
            files_created = []

            # Try streaming first (better UX)
            try:
                start = time.time()
                stream = chat_stream(user_input, model=model)
                first_token = True
                for token in stream:
                    if first_token:
                        elapsed = time.time() - start
                        # Clear the "working" line
                        sys.stdout.write("\033[2K\r")
                        sys.stdout.flush()
                        first_token = False
                    full_response += token
                
                # Show output without code blocks
                clean = strip_code_blocks(full_response)
                if clean:
                    print()
                    ask_model(clean)
                    print()
                else:
                    # Just the code blocks, no text -> show we're processing
                    cprint("  generating files...", "dim")

                # Extract and write files
                files_created = extract_and_write_files(full_response, workdir=workdir)

            except Exception:
                # Fallback to non-streaming
                resp = chat(user_input, model=model)
                full_response = resp.get("message", {}).get("content", "")
                
                clean = strip_code_blocks(full_response)
                if clean:
                    print()
                    ask_model(clean)
                    print()
                
                files_created = extract_and_write_files(full_response, workdir=workdir)

            # Show files created
            if files_created:
                cprint("  ✓ Files created:", "green", bold=True)
                for f in files_created:
                    print(f"    • {f}")
                print()

            # Add to history (truncated for context)
            summary = full_response[:500] if len(full_response) > 500 else full_response
            history.add("user", user_input)
            history.add("assistant", summary)

            hr()

        except OllamaError as e:
            cprint(f"  Error: {e}", "red")
            cprint("  Is ollama running? Try: docker start ollama", "yellow")
            hr()
        except Exception as e:
            cprint(f"  Unexpected error: {e}", "red")
            hr()


# ── One-shot mode ─────────────────────────────────────────────────

def one_shot(prompt: str, model: str, workdir: str):
    """Run a single prompt and exit."""
    hr("━")
    cprint("  ailocal — one-shot", "cyan", bold=True)
    hr("━")
    print()

    try:
        resp = chat(prompt, model=model)
        content = resp.get("message", {}).get("content", "")

        # Display clean output
        clean = strip_code_blocks(content)
        if clean:
            print(clean)
            print()

        # Create files
        files = extract_and_write_files(content, workdir=workdir)
        if files:
            cprint("  ✓ Files created:", "green", bold=True)
            for f in files:
                print(f"    • {f}")
        else:
            cprint("  No code blocks found to create files.", "yellow")

    except OllamaError as e:
        cprint(f"  Error: {e}", "red")
        sys.exit(1)
    except Exception as e:
        cprint(f"  Unexpected error: {e}", "red")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="ailocal - local AI coding assistant powered by ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              ailocal                        # interactive mode
              ailocal "create a Flask app"   # one-shot mode
              echo "write a script" | ailocal  # pipe mode
              ailocal --model llama3.2       # use different model
              ailocal --dir ./myproject      # set working directory
        """),
    )
    parser.add_argument("prompt", nargs="?", help="Prompt (omit for interactive)")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help="Ollama model")
    parser.add_argument("--dir", "-d", default=".", help="Working directory")
    parser.add_argument("--list-models", "-l", action="store_true", help="List models")

    args = parser.parse_args()

    # Handle --list-models
    if args.list_models:
        try:
            models = list_models()
            print("Available models:")
            for m in models:
                print(f"  • {m}")
        except OllamaError as e:
            cprint(f"Error: {e}", "red")
            sys.exit(1)
        return

    # Resolve workdir
    workdir = os.path.abspath(args.dir)

    # Determine mode
    prompt = args.prompt

    if not prompt and not sys.stdin.isatty():
        # Read from pipe
        prompt = sys.stdin.read().strip()

    if not prompt:
        # Interactive mode
        history = ChatHistory()
        try:
            interactive_loop(args.model, workdir, history)
        except KeyboardInterrupt:
            print()
        finally:
            print()
            cprint("bye!", "dim")
    else:
        # One-shot mode
        one_shot(prompt, args.model, workdir)


if __name__ == "__main__":
    main()
