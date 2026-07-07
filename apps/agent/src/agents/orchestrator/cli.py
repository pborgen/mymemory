import sys

from agents.memory.tools import API_URL, USER_EMAIL
from agents.orchestrator.agent import OrchestratorAgent

_ROUTE_LABEL = {"store": "Archivist", "recall": "Retriever", "chat": "small talk"}


def main() -> int:
    print(
        f"Orchestrator agent — acting as {USER_EMAIL} against {API_URL}\n"
        "A supervisor routes each turn to an Archivist (save), a Retriever\n"
        "(answer), or small talk; a Verifier fact-checks recalled answers.\n"
        "Type 'exit' to quit, 'reset' to clear history.\n"
        "Try: 'my plate is 8XYZ123 and my car is a blue Civic' then\n"
        "     'what car do I drive and what is my plate?'\n"
    )
    agent = OrchestratorAgent()

    while True:
        try:
            user_input = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            return 0
        if user_input.lower() == "reset":
            agent.reset()
            print("(history cleared)\n")
            continue

        try:
            for kind, text in agent.stream(user_input):
                if kind == "route":
                    print(f"  [supervisor] → {_ROUTE_LABEL.get(text, text)}")
                elif kind == "agent":
                    print(f"  [{text}] working...")
                elif kind == "tool":
                    print(f"  [tool] {text}")
                elif kind == "verify":
                    mark = "✓" if text == "grounded" else "✗"
                    print(f"  [verifier] {mark} {text}")
                else:
                    print(f"memory > {text}\n")
        except Exception as exc:  # surface config/API errors to the user
            print(f"error: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
