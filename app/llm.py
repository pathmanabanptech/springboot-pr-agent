from langchain_core.language_models import BaseChatModel


def get_llm(provider: str, model: str, api_key: str, max_tokens: int = 4096) -> BaseChatModel:
    """Return a BaseChatModel for the given provider using a lazy import."""
    p = provider.lower()

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key, max_tokens=max_tokens)

    if p == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key, max_tokens=max_tokens)

    if p == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, max_output_tokens=max_tokens)

    if p == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        endpoint = HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=api_key,
            max_new_tokens=max_tokens,
        )
        return ChatHuggingFace(llm=endpoint)

    raise ValueError(
        f"Unsupported MODEL_PROVIDER: '{provider}'. "
        "Choose one of: anthropic, openai, google, huggingface"
    )
