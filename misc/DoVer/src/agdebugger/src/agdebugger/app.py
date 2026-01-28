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

    # If a multi-session history package is passed in, disassemble it into the current branch history required for operation and inject multi-session meta-information
    history_bundle = None
    init_history = message_history
    if isinstance(message_history, dict) and ("sessions" in message_history and "current_session" in message_history):
        history_bundle = message_history
        # Runtime history prioritizes using the original TimeStampedMessage list to avoid deserialization complexity
        init_history = history_bundle.get("current_history_raw", None)

    # Pass saved_team_id to backend to ensure team_id consistency recovery
    backend = BackendRuntimeManager(loaded_gc, logger, init_history, state_cache, saved_team_id)

    # If there is a multi-session package, inject prior_histories and counters (for UI display and operation)
    if history_bundle is not None:
        try:
            backend.prior_histories = history_bundle.get("sessions", {}) or {}
            backend.session_counter = int(history_bundle.get("current_session", 0))
            # Restore the reset_from of the current branch for easy display and subsequent editing
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

        # If display_session_id is set, modify the returned current_session
        if hasattr(backend, 'display_session_id') and backend.display_session_id is not None:
            display_session = backend.display_session_id
            if display_session in saved_sessions:
                return {
                    "current_session": display_session,
                    "message_history": saved_sessions,
                    "actual_session": backend.session_counter,  # Keep real session information
                    "display_mode": True
                }

        return {
            "current_session": backend.session_counter,
            "message_history": saved_sessions,
            "display_mode": False
        }

    @api.get("/getSessionHistory/{session_id}")
    async def getSpecificSessionHistory(session_id: int):
        """Get history messages of a specific session"""
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
        """Switch the currently displayed session (does not change the actual running state, only for UI display)"""
        saved_sessions = backend.read_current_session_history()

        if session_id not in saved_sessions:
            return {"error": f"Session {session_id} not found"}

        # Set the backend display session (new attribute)
        backend.display_session_id = session_id

        return {
            "status": "ok",
            "display_session_id": session_id,
            "message_count": len(saved_sessions[session_id].messages)
        }

    @api.post("/resetDisplaySession")
    async def resetDisplaySession():
        """Reset display mode, return to current active session"""
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
            # Save multi-session package format
            history_bundle = {
                "format_version": "multi_session_v1",
                "current_session": backend.session_counter,
                "sessions": backend.read_current_session_history(),
                "current_history_raw": backend.intervention_handler.history,
            }
            await write_file_async("history.pickle", history_bundle)
            # Use new format to save cache, including team_id information to ensure consistency during recovery
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
        API endpoint for custom saved file path
        Supports specifying the save path of history and cache through request body or URL parameters, automatically creating directories

        Usage:
        1. POST body: {"history_path": "...", "cache_path": "..."}
        2. URL parameters: ?history=...&cache=...
        """
        import os

        # Determine the final file path (URL parameters have higher priority than request body)
        if history or cache:
            # Use URL parameters
            history_path = history or "logs/generated/scenario_1_history.pickle"
            cache_path = cache or "logs/generated/scenario_1_cache.pickle"
        elif request:
            # Use request body
            history_path = request.history_path
            cache_path = request.cache_path
        else:
            # Use default value
            history_path = "logs/generated/scenario_1_history.pickle"
            cache_path = "logs/generated/scenario_1_cache.pickle"

        # Ensure the directory exists if the path contains a directory
        history_dir = os.path.dirname(history_path)
        cache_dir = os.path.dirname(cache_path)

        if history_dir:
            os.makedirs(history_dir, exist_ok=True)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        try:
            # Save file (multi-session package format)
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
