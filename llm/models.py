import os
from langchain_google_genai import (
    GoogleGenerativeAIEmbeddings,
    ChatGoogleGenerativeAI,
)
from config.settings import settings


def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=settings.embedding_location,
        vertexai=True,
    )


def get_llm(
    streaming: bool = True,
    max_tokens: int | None = None,
) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=settings.llm_location,
        vertexai=True,
        temperature=settings.llm_temperature,
        # Greedy decoding on top of temperature=0: top_k=1 forces the single
        # most-likely token, top_p=0 collapses nucleus sampling. This squeezes
        # out client-side sampling variance so the same question yields the same
        # answer (server-side batching can still introduce a rare wobble).
        top_k=1,
        top_p=0.0,
        max_output_tokens=max_tokens or settings.llm_max_tokens,
        # gemini-2.5-flash is a "thinking" model: its internal reasoning
        # tokens are billed against max_output_tokens. Left on, verbose
        # thinking exhausts the budget and the visible answer truncates
        # mid-sentence. We disable it and rely on the prompt for structure.
        thinking_budget=0,
        streaming=streaming,
    )
