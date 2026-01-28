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
    saved_team_id = None  # 新增：用于保存历史的team_id

    if history is not None:
        with open(history, "rb") as f:
            history_data = pickle.load(f)
            # 兼容新旧history格式：若为多session包，则提取当前分支消息和完整session树
            if isinstance(history_data, dict) and (
                "sessions" in history_data and "current_session" in history_data
            ):
                bundle = history_data
                print(
                    f"[INFO] Loaded multi-session history: {len(bundle['sessions'])} sessions, current={bundle['current_session']}"
                )
                # 将当前分支消息作为 message_history 传入；完整包在后端初始化时再注入
                current_session = bundle["current_session"]
                sessions = bundle["sessions"]
                # 将 sessions[current_session].messages 转为 TimeStampedMessage 列表的简化json（后端接受已是json化消息）
                # 直接把 bundle 通过 message_history 传给 get_server，后端识别并拆解
                loaded_history = bundle
            else:
                # 旧格式：直接传入列表
                loaded_history = history_data

    if cache is not None:
        with open(cache, "rb") as f:
            cache_data = pickle.load(f)
            # 兼容新旧cache格式：检查是否包含team_id信息
            if isinstance(cache_data, dict) and "team_id" in cache_data:
                # 新格式：包含team_id和state的字典
                loaded_cache = cache_data["state"]
                saved_team_id = cache_data["team_id"]
                print(f"[INFO] Loaded team_id from cache: {saved_team_id}")
            else:
                # 旧格式兼容：直接当作state使用
                loaded_cache = cache_data
                print("[WARN] Cache file is in old format, team_id consistency cannot be guaranteed")

    if launch:
        webbrowser.open(f"http://{host}:{port}")

    asyncio.run(async_run(module, loaded_history, loaded_cache, saved_team_id, host, port, workers, reload))


async def async_run(module, loaded_history, loaded_cache, saved_team_id, host, port, workers, reload):
    # 传递saved_team_id给server，确保team_id一致性
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
