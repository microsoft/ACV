#!/usr/bin/env python3
"""
Simulation Runner for agdebugger

Launches agdebugger and automatically sends a scenario task.
Runs continuously like the original agdebugger command until manually stopped.

Usage (run inside: conda activate dover):
  python scripts/simulation_runner.py --scenario 1 --port 8081
"""

import argparse
import json
import sys
import time
import threading
import logging
import signal
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request

# 🔇 DISABLE VERBOSE LOGS: Suppress uvicorn and other access logs
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)

# Auto-detect project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # Add project root to path

# Scenario data directory
SCENARIO_DIR = PROJECT_ROOT / "Agents_Failure_Attribution/Who&When/Hand-Crafted"
BASE_URL = "http://127.0.0.1:8081/api"  # Default, will be updated in main()
# Batch controls
RUN_DIR: Path | None = None  # logs/scenario_{sid}/{round}
AUTO_EXIT: bool = False

def load_scenario_task(scenario_id: str, task_source: str = "content") -> str:
    """Load task from scenario JSON file.

    task_source:
      - "content" (default): use the first human message's content in `history`
      - "question": use top-level `question`/`task`/`query`
    """
    scenario_file = SCENARIO_DIR / f"{scenario_id}.json"
    if not scenario_file.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_file}")

    with scenario_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # content mode: use history entry with step_idx == 0
    if (task_source or "").lower() == "content":
        hist = data.get("history")
        if isinstance(hist, list) and len(hist) > 0:
            for item in hist:
                if isinstance(item, dict) and item.get("step_idx") == 0 and item.get("content"):
                    return item["content"]

    # Fallback to question/task/query
    task = data.get("question") or data.get("task") or data.get("query")
    if not task:
        raise ValueError(f"No task found in scenario file: {scenario_file}")
    return task


def send_task_when_ready(task: str, max_wait: int = 60):
    """Wait for backend and send task as a single GroupChatStart to orchestrator"""
    print(f"📋 Will send task: {task[:80]}...")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            # 1) wait for backend ready
            with urlopen(Request(f"{BASE_URL}/loop_status"), timeout=3) as resp:
                resp.read()

            # 2) resolve orchestrator recipient from /agents (includes team-id suffix)
            with urlopen(Request(f"{BASE_URL}/agents"), timeout=5) as resp:
                agents = json.loads(resp.read().decode("utf-8"))
            if not agents:
                time.sleep(1)
                continue
            orchestrator = next((n for n in agents if "orchestrator" in n.lower()), agents[0])

            print(f"✅ Backend ready, sending GroupChatStart to: {orchestrator}")
            time.sleep(1)

            # 3) send only GroupChatStart (UI also shows this as the first message)
            text_msg = {"source": "user", "content": task, "type": "TextMessage"}
            gcs_body = {"messages": [text_msg], "type": "GroupChatStart"}
            payload = {"type": "GroupChatStart", "recipient": orchestrator, "body": gcs_body}
            data = json.dumps(payload).encode("utf-8")
            with urlopen(Request(f"{BASE_URL}/send", data=data, headers={"Content-Type": "application/json"}, method="POST"), timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            print(f"📤 GroupChatStart sent: {result}")

            # 4) start processing loop
            with urlopen(Request(f"{BASE_URL}/start_loop", data=b'{}', headers={"Content-Type": "application/json"}, method="POST"), timeout=10) as resp:
                loop_result = json.loads(resp.read().decode("utf-8"))
            print(f"🚀 Processing started: {loop_result}")
            return

        except Exception:
            time.sleep(2)
    print("❌ Backend not ready within timeout, task not sent")


# --- Minimal helpers for waiting and saving (run from scripts/ dir) ---

def _http_get_json(path: str):
    with urlopen(Request(f"{BASE_URL}{path}"), timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _http_post_json(path: str, payload: dict | None = None):
    data = (json.dumps(payload or {})).encode("utf-8")
    with urlopen(Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST"), timeout=15) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _get_session_message_count() -> int:
    """Return the number of messages in the current session history (best-effort)."""
    try:
        sess = _http_get_json("/getSessionHistory")
        cur = sess.get("current_session")
        mh = sess.get("message_history", {})
        if cur is None or str(cur) not in mh:
            # Some servers use int keys; handle both
            if isinstance(cur, int) and cur in mh:
                return len(mh[cur].get("messages", []))
            return 0
        return len(mh[str(cur)].get("messages", [])) if isinstance(mh, dict) else 0
    except Exception:
        return 0


def _get_logs_count() -> int:
    """Return number of log entries (best-effort)."""
    try:
        logs = _http_get_json("/logs")
        return len(logs) if isinstance(logs, list) else 0
    except Exception:
        return 0


def _has_groupchat_termination() -> bool:
    """Return True if any relevant session contains a GroupChatTermination event."""
    try:
        payload = _http_get_json("/getSessionHistory")
        message_history = payload.get("message_history", {})

        def _resolve_messages(session_id: object) -> list[dict]:
            if not isinstance(message_history, dict):
                return []
            for key in (session_id, str(session_id) if session_id is not None else None):
                if key is None:
                    continue
                session = message_history.get(key)
                if isinstance(session, dict):
                    messages = session.get("messages")
                    if isinstance(messages, list):
                        return messages
            return []

        candidates: list[object] = []
        seen: set[str] = set()

        def _append_candidate(candidate: object) -> None:
            if candidate is None:
                return
            key = str(candidate)
            if key in seen:
                return
            seen.add(key)
            candidates.append(candidate)

        _append_candidate(payload.get("actual_session"))
        _append_candidate(payload.get("current_session"))

        if isinstance(message_history, dict) and message_history:
            try:
                last_key = max(
                    message_history.keys(),
                    key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)),
                )
            except Exception:
                last_key = next(iter(message_history.keys()))
            _append_candidate(last_key)
            for key in message_history.keys():
                _append_candidate(key)

        for candidate in candidates:
            messages = _resolve_messages(candidate)
            for item in reversed(messages):
                msg = item.get("message", {}) if isinstance(item, dict) else {}
                if msg.get("type") == "GroupChatTermination":
                    return True
        return False
    except Exception:
        return False


def wait_until_terminated(poll_interval: float = 1.0, max_wait_sec: int = 1800) -> bool:
    """Poll session history for GroupChatTermination; return True when observed, else False on timeout."""
    print("⏳ Waiting for GroupChatTermination event...")
    start = time.time()
    while time.time() - start < max_wait_sec:
        if _has_groupchat_termination():
            print("✅ Detected GroupChatTermination")
            return True
        time.sleep(poll_interval)
    print("⚠️  Timeout while waiting for termination event")
    return False


def wait_until_idle(poll_interval: float = 2.0, stable_checks: int = 2, max_wait_sec: int = 600) -> bool:
    """
    Wait until the backend finishes processing.
    Conditions for done (must be stable for `stable_checks` polls):
      - loop_status == False (not processing) AND
      - num_tasks == 0 AND
      - message_queue length == 0
    Returns True if done-before-timeout, else False.
    """
    print("⏳ Waiting for processing to complete...")
    start = time.time()
    stable = 0
    last_snapshot = None

    while time.time() - start < max_wait_sec:
        try:
            # Read status from three lightweight endpoints
            loop_status = _http_get_json("/loop_status")
            num = _http_get_json("/num_tasks")
            queue = _http_get_json("/getMessageQueue")

            # Normalize types
            if isinstance(num, dict):
                num = num.get("value", 0)
            try:
                qlen = len(queue) if isinstance(queue, list) else int(queue or 0)
            except Exception:
                qlen = 0
            try:
                processing = bool(loop_status)
            except Exception:
                processing = False

            snapshot = {"processing": processing, "num": int(num), "qlen": int(qlen)}
            if snapshot != last_snapshot:
                print(f"📊 Status => processing={snapshot['processing']} num_tasks={snapshot['num']} queue_len={snapshot['qlen']}")
                last_snapshot = snapshot

            # Check idle condition (don't require loop_status=False before stopping)
            if snapshot["num"] == 0 and snapshot["qlen"] == 0:
                stable += 1
                if stable >= stable_checks:
                    print("✅ Detected idle state (num_tasks=0, queue_len=0). Stopping loop...")
                    # Ensure loop is stopped (idempotent)
                    try:
                        _http_post_json("/stop_loop")
                    except Exception:
                        pass
                    # Optional: wait briefly for loop_status to turn False
                    end_wait = time.time() + 10
                    while time.time() < end_wait:
                        try:
                            proc2 = bool(_http_get_json("/loop_status"))
                            if not proc2:
                                break
                        except Exception:
                            break
                        time.sleep(0.5)
                    print("✅ Processing completed!")
                    return True
            else:
                stable = 0
        except Exception as e:
            # transient errors are fine during spin-up/spin-down
            pass

        time.sleep(poll_interval)

    print("⚠️  Timeout waiting for idle state; proceeding to save anyway")
    return False


def save_artifacts(sid: str) -> dict:
    """
    Save history/cache and JSON artifacts to logs/scenario_{sid}/.
    """
    # Output directory (supports per-round subdirectory)
    out_dir = RUN_DIR if RUN_DIR is not None else (PROJECT_ROOT / "logs" / f"scenario_{sid}")
    out_dir.mkdir(parents=True, exist_ok=True)

    hist_path = out_dir / f"scenario_{sid}_history.pickle"
    cache_path = out_dir / f"scenario_{sid}_cache.pickle"
    logs_path = out_dir / f"scenario_{sid}_logs.json"
    sess_json_path = out_dir / f"scenario_{sid}_history.json"

    print("💾 Saving artifacts...")
    # 1) ask backend to save pickles to our target paths
    try:
        _http_post_json("/save_to_file_custom", {"history_path": str(hist_path), "cache_path": str(cache_path)})
        print("  📦 Saved history/cache pickles")
    except Exception as e:
        print(f"  ⚠️ Failed to save pickles: {e}")

    # 2) fetch logs and session history json
    try:
        logs = _http_get_json("/logs")
        with logs_path.open("w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        print("  📋 Saved logs JSON")
    except Exception as e:
        print(f"  ⚠️ Failed to save logs: {e}")

    try:
        sess = _http_get_json("/getSessionHistory")
        with sess_json_path.open("w", encoding="utf-8") as f:
            json.dump(sess, f, ensure_ascii=False, indent=2)
        print("  📝 Saved session history JSON")
    except Exception as e:
        print(f"  ⚠️ Failed to save session history: {e}")

    print("✅ All artifacts saved!")
    return {
        "history_pickle": str(hist_path),
        "cache_pickle": str(cache_path),
        "logs_json": str(logs_path),
        "session_history_json": str(sess_json_path),
    }


def monitor_and_save(sid: str):
    """Wait for a definitive end signal then save. Simpler and robust.
    Strategy:
      1) Wait for GroupChatTermination to appear in session history
      2) Stop loop (idempotent) and wait briefly for backend to flush
      3) Ensure history stabilized for a short quiet window, then save
    """
    terminated = wait_until_terminated(poll_interval=1.0, max_wait_sec=900)
    if not terminated:
        print("⚠️  Timeout waiting for GroupChatTermination; saving anyway")

    # Ensure loop is stopped (safe if already stopped)
    try:
        _http_post_json("/stop_loop")
    except Exception:
        pass

    # Give backend a brief flush window and wait for history to stabilize
    import time as _t
    last_count = -1
    stable = 0
    for _ in range(10):  # up to ~5s
        try:
            sess = _http_get_json("/getSessionHistory")
            cur = sess.get("current_session"); mh = sess.get("message_history", {})
            session = mh.get(str(cur), mh.get(cur, {})) if isinstance(mh, dict) else {}
            msgs = session.get("messages", []) if isinstance(session, dict) else []
            cnt = len(msgs)
            if cnt == last_count:
                stable += 1
                if stable >= 2:  # two consecutive polls unchanged
                    break
            else:
                stable = 0
                last_count = cnt
        except Exception:
            pass
        _t.sleep(0.5)

    save_artifacts(sid)

    # Auto-exit the runner (and close Web UI) if requested
    from signal import SIGINT
    import os as _os
    if AUTO_EXIT:
        try:
            _os.kill(_os.getpid(), SIGINT)
        except Exception:
            pass


def main():
    global BASE_URL

    parser = argparse.ArgumentParser(description="Simulation runner for agdebugger")
    parser.add_argument("--scenario", default="1", help="Scenario ID (default: 1)")
    parser.add_argument("--port", default="8081", help="AgDebugger port (default: 8081)")
    parser.add_argument("--model", default="gpt-4o", help="Model to use (default: gpt-4o)")
    parser.add_argument("--add-system-prompt", action="store_true", help="Include system prompt before the orchestrator message thread")
    parser.add_argument(
        "--system-prompt-template",
        default="1",
        choices=["1", "2"],
        help="Select the base system prompt template when --add-system-prompt is enabled (default: 1)",
    )
    parser.add_argument("--round", help="Round tag for this run, e.g., 1, 2, 3")
    parser.add_argument("--auto-exit", action="store_true", help="Exit runner automatically after artifacts are saved")
    parser.add_argument("--task-source", default="content", choices=["content", "question"], help="Select task content: 'content' uses first human history entry; 'question' uses top-level question/task/query")
    args = parser.parse_args()


    # Update BASE_URL to use the specified port
    global BASE_URL, RUN_DIR, AUTO_EXIT
    BASE_URL = f"http://127.0.0.1:{args.port}/api"

    # Compute run directory (supports rounds)
    RUN_DIR = PROJECT_ROOT / "logs" / f"scenario_{args.scenario}"
    if args.round:
        RUN_DIR = RUN_DIR / str(args.round)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    # Auto-exit control
    AUTO_EXIT = bool(args.auto_exit)

    # 🔇 ADDITIONAL LOG SUPPRESSION: Set environment variables for uvicorn via agdebugger CLI
    import os
    os.environ["AGDEBUGGER_UVICORN_ACCESS_LOG"] = "false"  # disable access logs like GET /api/...
    os.environ["AGDEBUGGER_UVICORN_LOG_LEVEL"] = "warning"  # reduce server log level
    # Pass scenario ID to m1_agdebugger_test (manage injection logic here if customizing subdirectories)
    os.environ["M1_SCENARIO_ID"] = args.scenario
    # Pass model selection to m1_agdebugger_test
    os.environ["M1_MODEL"] = args.model
    os.environ["M1_SYSTEM_PROMPT_TEMPLATE"] = str(args.system_prompt_template)


    # Minimal injection: pass websurfer_kwargs via monkey patch so callers don't need to change m1_agdebugger_test
    try:
        from autogen_ext.teams.magentic_one import MagenticOne  # type: ignore
        _orig_m1_init = MagenticOne.__init__  # keep original

        def _patched_m1_init(
            self,
            client,
            hil_mode: bool = False,
            input_func=None,
            code_executor=None,
            websurfer_kwargs: dict | None = None,
            filesurfer_base_path: str | None = None,
            code_executor_kwargs: dict | None = None,
        ):
            sid = args.scenario
            run_dir = RUN_DIR if RUN_DIR is not None else (PROJECT_ROOT / "logs" / f"scenario_{sid}")
            screenshot_dir = run_dir / "websurfer_screenshot"
            downloads_dir = run_dir / "downloads"
            workspace_dir = run_dir / "workspace"
            record_dir = run_dir / "record"
            try:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                downloads_dir.mkdir(parents=True, exist_ok=True)
                workspace_dir.mkdir(parents=True, exist_ok=True)
                record_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            browser_data_dir: str = os.environ.get(
                "M1_WS_BROWSER_DATA_DIR",
                str(PROJECT_ROOT / "logs" / "websurfer_profile"),
            )
            if websurfer_kwargs is None:
                websurfer_kwargs = {
                    "debug_dir": str(screenshot_dir),
                    "to_save_screenshots": True,
                    "downloads_folder": str(downloads_dir),
                    "headless": False,
                    "animate_actions": False,
                    "record_video": True,
                    "search_engine": "google",
                    "browser_data_dir": browser_data_dir,
                    "browser_channel": "msedge",
                    "playwright_launch_options": {
                        "slow_mo": 200,
                        "args": [
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                        ],
                    },
                    "playwright_context_options": {
                        "record_video_dir": str(record_dir),
                        # "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
                        "locale": "en-US",
                        "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    },
                }
            if filesurfer_base_path is None:
                filesurfer_base_path = str(run_dir)
            if code_executor_kwargs is None:
                code_executor_kwargs = {
                    "work_dir": str(workspace_dir),
                }

            return _orig_m1_init(
                self,
                client,
                hil_mode,
                input_func,
                code_executor,
                websurfer_kwargs,
                filesurfer_base_path,
                code_executor_kwargs,
                add_system_prompt=bool(args.add_system_prompt),
            )

        MagenticOne.__init__ = _patched_m1_init  # type: ignore
        # Also patch FileSurfer to allow accessing project-root files (logs/ etc.)
        try:
            from autogen_ext.agents.file_surfer import FileSurfer  # type: ignore
            _orig_fs_init = FileSurfer.__init__  # keep original

            def _patched_fs_init(self, name, model_client, description=FileSurfer.DEFAULT_DESCRIPTION, base_path=None):
                # If no base_path is provided, default to project root so logs/ are accessible
                if base_path is None:
                    base_path = str(PROJECT_ROOT)
                return _orig_fs_init(self, name, model_client, description, base_path)

            FileSurfer.__init__ = _patched_fs_init  # type: ignore
        except Exception as e:
            print(f"⚠️ Failed to patch FileSurfer base_path: {e}")

        print(f"🖼️ WebSurfer shots: {PROJECT_ROOT / 'logs' / f'scenario_{args.scenario}' / 'websurfer_screenshot'} | downloads: {PROJECT_ROOT / 'logs' / f'scenario_{args.scenario}' / 'downloads'}")
    except Exception as e:
        print(f"⚠️ Failed to inject websurfer_kwargs: {e}")




    try:
        # Load scenario task with selectable source (default: content)
        task = load_scenario_task(args.scenario, args.task_source)
        print(f"🎯 Scenario {args.scenario} loaded (task_source={args.task_source})")

        # Start background thread to send task when ready
        task_thread = threading.Thread(
            target=send_task_when_ready,
            args=(task,),
            daemon=True
        )
        task_thread.start()

        # Start background monitor to wait until idle and save artifacts once
        saver_thread = threading.Thread(
            target=monitor_and_save,
            args=(args.scenario,),
            daemon=True
        )
        saver_thread.start()

        # 🔧 MODULE PATH: agdebugger CLI arguments (adjust module path if needed)
        sys.argv = [
            "agdebugger",
            "scripts.m1_agdebugger_test:get_full_m1_team",  # Module path relative to project root
            # "--launch",
            "--port", str(args.port)
        ]

        print("🚀 Starting AgDebugger...")
        print("   Web UI will open automatically")
        print("   Task will be sent automatically when ready")
        print("   Press Ctrl+C to stop")

        # Run agdebugger CLI (blocks until Ctrl+C)
        from agdebugger.cli import main_cli
        main_cli()

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
