# =============================================================
# Interactive query loop.
# =============================================================
import sys
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from pipelines.rag_pipeline import RAGPipeline


def main() -> None:
    pipeline = RAGPipeline()

    print("=" * 64)
    print("RAG System Ready")
    print("Flow: Rewrite -> Classify policy -> Vector (per-policy) -> Pin tables -> Gemini")
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
            pipeline.memory.clear()
            print("[memory cleared]")
            continue

        print("\nAI Assistant:")
        print("Thinking...", end="", flush=True)
        first = True
        for piece in pipeline.stream_answer(user_query):
            if first:
                print("\r" + " " * 15 + "\r", end="", flush=True)
                first = False
            print(piece, end="", flush=True)
        print()


if __name__ == "__main__":
    main()
