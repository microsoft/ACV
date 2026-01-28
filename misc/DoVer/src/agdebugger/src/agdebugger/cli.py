import asyncio
import os
import pickle
import webbrowser

import typer
import uvicorn
from typing_extensions import Annotated

from .app import get_server

cli_app = typer.Typer()


@cli_app.command()
def run(
    module: str,
    host: str = "127.0.0.1",
    port: int = 8081,
    workers: int = 1,
    reload: Annotated[bool, typer.Option("--reload")] = False,
    launch: Annotated[bool, typer.Option("--launch")] = False,
    history: str | None = None,
    cache: str | None = None,
):
    """
    Run the AGEDebugger app.

    Args:
        module (str): description of agent app loader
        host (str, optional): Host to run the UI on. Defaults to 127.0.0.1 (localhost).
        port (int, optional): Port to run the UI on. Defaults to 8081.
        workers (int, optional): Number of workers to run the UI with. Defaults to 1.
        reload (bool, optional): Whether to reload the UI on code changes. Defaults to False.
        open (bool, optional): Whether to open the UI in the browser. Defaults to False.
        history (str, optional): Path to a history file to load.
        cache (str, optional): Path to a cache file to load.
        scorer (str, optional): name of score function
    """
    loaded_history = None
    loaded_cache = None
    saved_team_id = None  # New: team_id used to save history

    if history is not None:
        with open(history, "rb") as f:
            history_data = pickle.load(f)
            # Compatible with new and old history formats: if it is a multi-session package, extract the current branch message and the complete session tree
            if isinstance(history_data, dict) and (
                "sessions" in history_data and "current_session" in history_data
            ):
                bundle = history_data
                print(
                    f"[INFO] Loaded multi-session history: {len(bundle['sessions'])} sessions, current={bundle['current_session']}"
                )
                # Pass the current branch message as message_history; the complete package is injected during backend initialization
                current_session = bundle["current_session"]
                sessions = bundle["sessions"]
                # Convert sessions[current_session].messages to a simplified json list of TimeStampedMessage (the backend accepts already jsonized messages)
                # Pass the bundle directly to get_server through message_history, and the backend identifies and disassembles it
                loaded_history = bundle
            else:
                # Old format: pass in list directly
                loaded_history = history_data

    if cache is not None:
        with open(cache, "rb") as f:
            cache_data = pickle.load(f)
            # Compatible with new and old cache formats: check if team_id information is included
            if isinstance(cache_data, dict) and "team_id" in cache_data:
                # New format: dictionary containing team_id and state
                loaded_cache = cache_data["state"]
                saved_team_id = cache_data["team_id"]
                print(f"[INFO] Loaded team_id from cache: {saved_team_id}")
            else:
                # Old format compatibility: use directly as state
                loaded_cache = cache_data
                print("[WARN] Cache file is in old format, team_id consistency cannot be guaranteed")

    if launch:
        webbrowser.open(f"http://{host}:{port}")

    asyncio.run(async_run(module, loaded_history, loaded_cache, saved_team_id, host, port, workers, reload))


async def async_run(module, loaded_history, loaded_cache, saved_team_id, host, port, workers, reload):
    # Pass saved_team_id to the server to ensure team_id consistency
    server_app = await get_server(module, loaded_history, loaded_cache, saved_team_id)

    # Respect environment overrides for logs
    access_log_env = os.environ.get("AGDEBUGGER_UVICORN_ACCESS_LOG", "false").lower()
    log_level_env = os.environ.get("AGDEBUGGER_UVICORN_LOG_LEVEL", "warning").lower()
    access_log = access_log_env in ("1", "true", "yes")

    config = uvicorn.Config(
        server_app,
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        access_log=access_log,
        log_level=log_level_env,
    )
    server = uvicorn.Server(config)

    print("Starting server...")
    await server.serve()


def main_cli():
    cli_app()
