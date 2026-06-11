import sys

from agents.memory.agent import MemoryAgent
from agents.memory.tools import API_URL, USER_EMAIL


def main() -> int:
    print(
        f"Memory agent — acting as {USER_EMAIL} against {API_URL}\n"
        "Type 'exit' to quit, 'reset' to clear history.\n"
        "Try: 'my car license plate is 8XYZ123' then 'what is my license plate?'\n"
    )
    agent = MemoryAgent()

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
                if kind == "tool":
                    print(f"  [tool] {text}")
                else:
                    print(f"memory > {text}\n")
        except Exception as exc:  # surface config/API errors to the user
            print(f"error: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
