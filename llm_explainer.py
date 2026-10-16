"""Generate concise code explanations with an OpenAI-compatible LLM API."""

import os
from argparse import ArgumentParser
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL_ID = os.getenv("LLM_MODEL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
client = OpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key=LLM_API_KEY)


def _error_message(error: Exception) -> str:
    """Convert common API failures into a useful message for the caller."""
    message = str(error).lower()
    if "402" in message or "payment required" in message or "credits" in message:
        return "Error: AI credits exhausted. Please try again later."
    if "api key" in message or "unauthorized" in message or "401" in message or "403" in message:
        return "Error: Authentication failed. Check LLM_API_KEY."
    if "timeout" in message or "timed out" in message:
        return "Error: Request timed out. Please try again."
    if "rate" in message or "429" in message:
        return "Error: Rate limit reached. Please try again later."
    if "model" in message and ("not found" in message or "does not exist" in message):
        return "Error: Model not found. Check LLM_MODEL."
    return f"Error: LLM API call failed: {error}"


def explain_chunk(code: str, chunk_type: str = "function") -> str:
    """Explain a code chunk in markdown."""
    if not LLM_API_KEY:
        return "Error: LLM_API_KEY is missing."

    fence = "`````"
    prompt = f"""Provide a detailed and descriptive explanation of this {chunk_type}.
Please include:
- **Overall Purpose**: A clear description of what the code does.
- **Key Functions/Classes**: Highlight important function names or classes and explain what they do.
- **Inputs and Outputs**: Describe the expected inputs and what it produces.
Use Markdown formatting to make it easy to read. Be comprehensive but concise.

Code:
{fence}python
{code}
{fence}"""
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant. You explain code clearly, comprehensively, and use markdown formatting."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.2,
        )
        choice = response.choices[0]
        text = (choice.message.content or "").strip()
        if not text:
            return f"Error: Model returned an empty reply (finish_reason={choice.finish_reason})."
        return text
    except Exception as error:
        return _error_message(error)

def get_file_context(chunks: list[dict[str, str]]) -> str:
    """Build compact file context from extracted code chunks."""
    lines = []
    for chunk in chunks:
        code = chunk.get("code", "").splitlines()
        if code:
            lines.append(code[0])
        for line in code[1:]:
            stripped = line.strip()
            if stripped.startswith(('"""', "'''")):
                lines.append(stripped)
                break
    return "\n".join(lines)


def summarize_file(function_names: list[str], file_context: str) -> str:
    """Summarize a file's overall purpose using a fixed template."""
    if not LLM_API_KEY:
        return "Error: LLM_API_KEY is missing."

    functions = ", ".join(function_names) if function_names else "No named functions found"
    prompt = f"""You are documenting a code file for another developer.

Functions in this file: {functions}

File context:
{file_context}

Fill in this exact template with your answer, nothing else:

Purpose: <one line, what this file is for>
Key functions: <one line, which functions matter most and why>
Used by: <one line, how/where this file likely gets used, or "Unclear from file alone" if you can't tell>
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as error:
        return _error_message(error)


if __name__ == "__main__":
    parser = ArgumentParser(description="Explain a source file with an LLM.")
    parser.add_argument("file", nargs="?", help="Path to the source file to explain")
    args = parser.parse_args()
    raw_path = args.file or input("Enter the path to a source file: ").strip()
    file_path = Path(raw_path.strip().strip('"').strip("'")).expanduser()

    try:
        file_code = file_path.read_text(encoding="utf-8")
        print(explain_chunk(file_code, chunk_type="file"))
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
    except IsADirectoryError:
        print(f"Error: Please provide a file path, not a directory: {file_path}")
    except UnicodeDecodeError:
        print(f"Error: Could not read {file_path} as a UTF-8 text file.")
    except OSError as error:
        print(f"Error: Could not read file: {error}")
