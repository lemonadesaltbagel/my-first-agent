import asyncio
from pathlib import Path

from dotenv import load_dotenv

from agent import Agent
from models import AgentPlan


def format_plan(plan: AgentPlan) -> str:
    lines = [
        f"\n  Summary: {plan.summary}",
        f"  Risk: {plan.risk_level}",
        "",
        "  Steps:",
    ]
    for i, step in enumerate(plan.steps, 1):
        lines.append(f"    {i}. {step}")
    if plan.files_involved:
        lines.append("")
        lines.append("  Files:")
        for f in plan.files_involved:
            lines.append(f"    - {f}")
    return "\n".join(lines)


async def main() -> None:
    load_dotenv()
    agent = Agent()

    print("Coding Agent (type 'exit' to quit, '/plan <query>' for structured planning)")
    print(f"Working directory: {Path.cwd()}")
    print()

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        if user_input.startswith("/plan "):
            query = user_input[6:].strip()
            if not query:
                print("Usage: /plan <your query>")
                continue
            print("  [planning...]")
            plan = await agent.structured_query(query, AgentPlan)
            print(format_plan(plan))
            print()
            continue

        response = await agent.chat(user_input)
        print(f"\nassistant> {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
