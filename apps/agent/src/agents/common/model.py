import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parents[3] / "models.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"models.json not found at {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text())


def _resolve_active(config: dict) -> tuple[str, str, dict]:
    active = config.get("active")
    if not active or "/" not in active:
        raise RuntimeError(
            "models.json 'active' must be set as 'provider/model-id' "
            "(e.g. 'bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0')."
        )
    provider, _, model = active.partition("/")
    provider_cfg = config.get("providers", {}).get(provider)
    if not provider_cfg:
        raise RuntimeError(f"Unknown provider '{provider}' in models.json.")
    if model not in provider_cfg.get("models", []):
        listed = ", ".join(provider_cfg.get("models", [])) or "(none)"
        raise RuntimeError(
            f"Model '{model}' not listed under providers.{provider}.models in models.json. "
            f"Listed: {listed}."
        )
    return provider, model, provider_cfg


def build_chat_model(temperature: float = 0.2, max_tokens: int = 1024) -> BaseChatModel:
    config = _load_config()
    provider, model, provider_cfg = _resolve_active(config)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv(provider_cfg.get("api_key_env", "ANTHROPIC_API_KEY"))
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        return ChatAnthropic(
            model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        api_key = os.getenv(provider_cfg.get("api_key_env", "GROQ_API_KEY"))
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Get a free key at console.groq.com.")
        return ChatGroq(
            model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens
        )

    if provider == "openai":
        # Any OpenAI-compatible server (vLLM, LM Studio, LiteLLM, …). vLLM ignores
        # the key, but the client requires a non-empty one.
        from langchain_openai import ChatOpenAI

        base_url = os.getenv(
            provider_cfg.get("base_url_env", "OPENAI_BASE_URL"),
            provider_cfg.get("base_url_default", "http://localhost:8001/v1"),
        )
        api_key = os.getenv(provider_cfg.get("api_key_env", "OPENAI_API_KEY")) or "not-needed"
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        base_url = os.getenv(
            provider_cfg.get("base_url_env", "OLLAMA_BASE_URL"),
            provider_cfg.get("base_url_default", "http://localhost:11434"),
        )
        return ChatOllama(
            model=model, base_url=base_url, temperature=temperature, num_predict=max_tokens
        )

    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse

        region = os.getenv(
            provider_cfg.get("region_env", "AWS_REGION"),
            provider_cfg.get("region_default", "us-east-1"),
        )
        # Credentials resolve via the standard AWS chain (env vars, shared
        # config/credentials files, SSO, or instance/role profiles).
        return ChatBedrockConverse(
            model=model,
            region_name=region,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise RuntimeError(
        f"Provider '{provider}' is not implemented. "
        "Supported: openai, anthropic, groq, ollama, bedrock."
    )
