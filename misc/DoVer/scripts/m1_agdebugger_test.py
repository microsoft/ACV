import asyncio
import os
from types import SimpleNamespace
import sys

from pathlib import Path
from datetime import datetime

from autogen_agentchat.ui import Console
from autogen_ext.teams.magentic_one import MagenticOne
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

PROJECT_ROOT = Path(__file__).parent.parent


async def get_full_m1_team() -> MagenticOne:
    # Read model selection from environment, default to gpt-4o-20241120
    model = os.environ.get("M1_MODEL", "gpt-4o-20241120")
    print(f"🤖 Using model: {model}")
    
    client = AzureOpenAIChatCompletionClient(
        model=model,
    )

    m1 = MagenticOne(
        client=client,
    )
    return m1


async def main() -> None:
    team = await get_full_m1_team()
    await Console(team.run_stream(task="Where can I take martial arts classes within a five-minute walk from the New York Stock Exchange after work (7-9 pm)?"))


if __name__ == "__main__":
    asyncio.run(main())
