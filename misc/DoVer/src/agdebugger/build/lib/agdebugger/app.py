import logging
import os
from typing import List

from autogen_core import EVENT_LOGGER_NAME
from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .backend import BackendRuntimeManager
from .intervention_utils import write_file_async
from .serialization import deserialize
from .types import (
    EditHistoryMessage,
    EditQueueMessage,
    PublishMessage,
    SaveFileRequest,
    SendMessage,
)
from .utils import load_app, message_to_json

# alt would be TRACE_LOGGER_NAME
logger = logging.getLogger(EVENT_LOGGER_NAME)
logger.setLevel(logging.DEBUG)


async def get_server(module_str: str, message_history=None, state_cache=None, saved_team_id=None) -> FastAPI:
    origins = [
        "http://localhost",
        "http://localhost:5173",
        "http://localhost:*",
    ]
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api = FastAPI(root_path="/api")
    app.mount("/api", api)
    # Get the path to the frontend dist directory
    # The structure is: src/agdebugger/src/agdebugger/app.py -> src/agdebugger/frontend/dist
    current_dir = os.path.dirname(os.path.abspath(__file__))  # src/agdebugger/src/agdebugger
    agdebugger_root = os.path.dirname(os.path.dirname(current_dir))  # src/agdebugger
    ui_folder_path = os.path.join(agdebugger_root, "frontend", "dist")
    if os.environ.get("AGDEBUGGER_BACKEND_SERVE_UI", "TRUE") == "TRUE":
        app.mount("/", StaticFiles(directory=ui_folder_path, html=True), name="ui")

    # load app and make backend
    loaded_gc = await load_app(module_str)

    # 如果传入的是多session历史包，则拆解为运行所需的当前分支历史，并注入多session元信息
    history_bundle = None
    init_history = message_history
    if isinstance(message_history, dict) and ("sessions" in message_history and "current_session" in message_history):
        history_bundle = message_history
        # 运行时历史优先使用原始的 TimeStampedMessage 列表，避免反序列化复杂度
        init_history = history_bundle.get("current_history_raw", None)

    # 传递saved_team_id给backend，确保team_id一致性恢复
    backend = BackendRuntimeManager(loaded_gc, logger, init_history, state_cache, saved_team_id)

    # 如果有多session包，注入 prior_histories 与计数器（用于UI展示与操作）
    if history_bundle is not None:
        try:
            backend.prior_histories = history_bundle.get("sessions", {}) or {}
            backend.session_counter = int(history_bundle.get("current_session", 0))
            # 恢复当前分支的 reset_from，便于显示与后续编辑
            curr = backend.prior_histories.get(backend.session_counter)
            if curr is not None:
                backend.current_session_reset_from = curr.current_session_reset_from
            print(f"[INFO] Restored multi-session bundle: sessions={len(backend.prior_histories)}, current={backend.session_counter}")
        except Exception as e:
            print(f"[WARN] Failed to restore multi-session bundle: {e}")

    await backend.async_initialize()

    @api.get("/agents")
    async def get_agent_list() -> List[str]:
        if not backend.ready:
            print("Agents not ready yet...")
            return []
        return backend.agent_names

    @api.get("/getMessageQueue")
    async def get_messages():
        message_queue = [message_to_json(msg) for msg in backend.message_queue_list]
        return message_queue

    @api.get("/getSessionHistory")
    async def getSessionHistory():
        saved_sessions = backend.read_current_session_history()

        # 如果设置了display_session_id，修改返回的current_session
        if hasattr(backend, 'display_session_id') and backend.display_session_id is not None:
            display_session = backend.display_session_id
            if display_session in saved_sessions:
                return {
                    "current_session": display_session,
                    "message_history": saved_sessions,
                    "actual_session": backend.session_counter,  # 保留真实的session信息
                    "display_mode": True
                }

        return {
            "current_session": backend.session_counter,
            "message_history": saved_sessions,
            "display_mode": False
        }

    @api.get("/getSessionHistory/{session_id}")
    async def getSpecificSessionHistory(session_id: int):
        """获取特定session的历史消息"""
        saved_sessions = backend.read_current_session_history()

        if session_id not in saved_sessions:
            return {"error": f"Session {session_id} not found"}

        return {
            "session_id": session_id,
            "messages": saved_sessions[session_id].messages,
            "current_session_reset_from": saved_sessions[session_id].current_session_reset_from,
        }

    @api.post("/setCurrentDisplaySession/{session_id}")
    async def setCurrentDisplaySession(session_id: int):
        """切换当前显示的session（不改变实际运行状态，仅用于UI显示）"""
        saved_sessions = backend.read_current_session_history()

        if session_id not in saved_sessions:
            return {"error": f"Session {session_id} not found"}

        # 设置后端的显示session（新增属性）
        backend.display_session_id = session_id

        return {
            "status": "ok",
            "display_session_id": session_id,
            "message_count": len(saved_sessions[session_id].messages)
        }

    @api.post("/resetDisplaySession")
    async def resetDisplaySession():
        """重置显示模式，回到当前活跃session"""
        backend.display_session_id = None
        return {
            "status": "ok",
            "current_session": backend.session_counter
        }

    @api.get("/num_tasks")
    async def get_outstanding_tasks() -> int:
        return backend.unprocessed_messages_count

    @api.post("/drop")
    async def drop():
        if backend.unprocessed_messages_count == 0:
            return {"status": "ok"}

        backend.intervention_handler.drop = True
        await backend.process_next()
        return {"status": "ok"}

    @api.post("/step")
    async def step():
        if backend.unprocessed_messages_count == 0:
            return {"status": "ok"}
        await backend.process_next()
        return {"status": "ok"}

    @api.post("/start_loop")
    async def start_loop():
        backend.start_processing()
        return {"status": "ok"}

    @api.post("/stop_loop")
    async def stop_loop():
        await backend.stop_processing()
        return {"status": "ok"}

    @api.get("/loop_status")
    async def loop_status() -> bool:
        return backend.is_processing

    @api.get("/message_types")
    async def message_types():
        return backend.message_info

    @api.get("/topics")
    async def topics() -> List[str]:
        return backend.all_topics

    @api.get("/state/{name}/get")
    async def get_config(name: str):
        try:
            config = await backend.get_agent_config(name)
            return config
        except Exception as e:
            print("Error getting state: ", e)
            return {"status": "error", "message": str(e)}

    @api.post("/publish")
    async def publish_message(message: PublishMessage):
        if message.body is None:
            return {"status": "error", "message": "Message body cannot be None"}

        new_message = deserialize(message.body)
        backend.publish_message(new_message, message.topic)
        return {"status": "ok"}

    @api.post("/send")
    async def send_message(message: SendMessage):
        if message.body is None:
            return {"status": "error", "message": "Message body cannot be None"}
        try:
            new_message = deserialize(message.body)
            await backend.send_message(new_message, message.recipient)
        except Exception as e:
            return {"status": "error", "message": e}

        return {"status": "ok"}

    @api.post("/editQueue")
    async def edit_message_queue(edit_message: EditQueueMessage):
        print("Editing message at index ", edit_message.idx, "with new content: ", edit_message.body)

        if edit_message.body is None:
            return {"status": "error", "message": "Messgage body cannot be None"}

        try:
            new_message = deserialize(edit_message.body)
            await backend.edit_message_queue(new_message, edit_message.idx)
        except Exception as e:
            return {"status": "error", "message": e}

        return {"status": "ok"}

    @api.post("/editAndRevertHistoryMessage")
    async def edit_and_revert_message(edit_message: EditHistoryMessage):
        try:
            if edit_message.body is not None:
                new_message = deserialize(edit_message.body)
            else:
                new_message = None
            await backend.edit_and_revert_message(new_message, edit_message.timestamp)
        except Exception as e:
            return {"status": "error", "message": e}

        return {"status": "ok"}

    @api.get("/logs")
    async def get_logs():
        return backend.log_handler.get_log_messages()

    @api.post("/save_to_file")
    async def save_to_file():
        try:
            # 保存多session包格式
            history_bundle = {
                "format_version": "multi_session_v1",
                "current_session": backend.session_counter,
                "sessions": backend.read_current_session_history(),
                "current_history_raw": backend.intervention_handler.history,
            }
            await write_file_async("history.pickle", history_bundle)
            # 使用新格式保存cache，包含team_id信息以确保恢复时一致性
            cache_with_team_id = backend.save_state_with_team_id()
            await write_file_async("cache.pickle", cache_with_team_id)

            print(f"[INFO] Saved cache with team_id: {cache_with_team_id['team_id']}")
            print(f"[INFO] Saved {len(history_bundle['sessions'])} sessions (multi_session_v1)")
            return {"status": "ok"}
        except Exception as e:
            print(f"[ERROR] save_to_file failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @api.post("/save_to_file_custom")
    async def save_to_file_custom(
        request: SaveFileRequest | None = Body(default=None),
        history: str | None = Query(default=None),
        cache: str | None = Query(default=None)
    ):
        """
        自定义保存文件路径的API端点
        支持通过请求体或URL参数指定history和cache的保存路径，自动创建目录

        使用方式：
        1. POST body: {"history_path": "...", "cache_path": "..."}
        2. URL参数: ?history=...&cache=...
        """
        import os

        # 确定最终的文件路径（URL参数优先级高于请求体）
        if history or cache:
            # 使用URL参数
            history_path = history or "logs/generated/scenario_1_history.pickle"
            cache_path = cache or "logs/generated/scenario_1_cache.pickle"
        elif request:
            # 使用请求体
            history_path = request.history_path
            cache_path = request.cache_path
        else:
            # 使用默认值
            history_path = "logs/generated/scenario_1_history.pickle"
            cache_path = "logs/generated/scenario_1_cache.pickle"

        # 确保目录存在，如果路径包含目录的话
        history_dir = os.path.dirname(history_path)
        cache_dir = os.path.dirname(cache_path)

        if history_dir:
            os.makedirs(history_dir, exist_ok=True)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        try:
            # 保存文件（多session包格式）
            history_bundle = {
                "format_version": "multi_session_v1",
                "current_session": backend.session_counter,
                "sessions": backend.read_current_session_history(),
                "current_history_raw": backend.intervention_handler.history,
            }
            await write_file_async(history_path, history_bundle)
            cache_with_team_id = backend.save_state_with_team_id()
            await write_file_async(cache_path, cache_with_team_id)

            print(f"[INFO] Saved cache with team_id: {cache_with_team_id['team_id']}")
            print(f"[INFO] Files saved to: history={history_path}, cache={cache_path}")

            return {
                "status": "ok",
                "history_path": history_path,
                "cache_path": cache_path,
                "team_id": cache_with_team_id['team_id'],
                "sessions": len(history_bundle["sessions"])
            }
        except Exception as e:
            print(f"[ERROR] save_to_file_custom failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app
