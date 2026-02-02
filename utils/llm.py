"""OpenRouter LLM integration using OpenAI SDK format"""
import os
import json
import re
import yaml
from openai import OpenAI


def get_openrouter_client():
    """Initialize OpenRouter client"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/mini-researcher-agent",
            "X-Title": "Mini Researcher Agent"
        }
    )


def call_llm(prompt, model=None, max_tokens=4096, temperature=0.7):
    """
    Call OpenRouter API with given prompt

    Args:
        prompt: The prompt to send
        model: Model to use (defaults to OPENROUTER_MODEL env var)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature

    Returns:
        str: The model's response text
    """
    client = get_openrouter_client()
    model = model or os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")

    print(f"[API] Calling {model}... ", end="", flush=True)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=120.0  # 2 minute timeout
    )

    print("Done")
    return response.choices[0].message.content


def parse_structured(text):
    """
    Extract and parse structured data (JSON or YAML) from LLM response

    Tries JSON first (more reliable for prose-heavy output), then YAML.

    Args:
        text: LLM response containing structured data

    Returns:
        dict: Parsed content
    """
    # Strategy 1: Try JSON code block
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0].strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Try YAML code block
    if "```yaml" in text:
        yaml_str = text.split("```yaml")[1].split("```")[0].strip()
        try:
            return yaml.safe_load(yaml_str)
        except yaml.YAMLError:
            pass

    # Strategy 3: Try any code block as JSON then YAML
    if "```" in text:
        block = text.split("```")[1].split("```")[0].strip()
        # Remove language tag if present (e.g., "json\n{...}")
        block = re.sub(r"^\w+\n", "", block)
        try:
            return json.loads(block)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return yaml.safe_load(block)
        except yaml.YAMLError:
            pass

    # Strategy 4: Try raw text as JSON then YAML
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return yaml.safe_load(text.strip())
    except yaml.YAMLError:
        pass

    raise ValueError(f"Could not parse structured data from LLM response. First 200 chars: {text[:200]}")


# Keep backward compatibility
parse_yaml = parse_structured
