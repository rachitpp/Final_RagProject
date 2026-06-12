# =============================================================
# Interactive query loop.
# =============================================================
import sys
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from pipelines.rag_pipeline import RAGPipeline
from conversation.memory import ConversationMemory
from config.settings import settings


def main() -> None:
    pipeline = RAGPipeline()
    # The CLI is single-user, so it owns one memory directly (the pipeline is
    # stateless; the web layer keeps one memory per conversation instead).
    memory = ConversationMemory(max_turns=settings.history_window)

    print("=" * 64)
    print("RAG System Ready")
    print("Flow: Rewrite -> Route (domestic/foreign/leave) -> Hybrid (BM25 + Vector, per-scope) -> Pin tables -> Gemini (+tools)")
    print("Commands: '0' to exit, 'reset' to clear conversation memory")
    print("=" * 64)

    while True:
        try:
            user_query = input("\nUser:\n").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_query:
            continue
        if user_query == "0":
            print("Goodbye!")
            break
        if user_query.lower() == "reset":
            memory.clear()
            print("[memory cleared]")
            continue

        print("\nAI Assistant:")
        print("Thinking...", end="", flush=True)
        first = True
        parts: list[str] = []
        for piece in pipeline.stream_answer(user_query, memory.turns()):
            if first:
                print("\r" + " " * 15 + "\r", end="", flush=True)
                first = False
            parts.append(piece)
            print(piece, end="", flush=True)
        print()
        memory.add(user_query, "".join(parts))


if __name__ == "__main__":
    main()
