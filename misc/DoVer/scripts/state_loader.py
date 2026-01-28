#!/usr/bin/env python3
"""
State Loader for agdebugger

Purpose:
- Restore a previous run's state using the saved pickle files (history/cache)
- Launch the agdebugger WebUI with the restored session(s)
- Behaves like running the CLI directly and stays running until Ctrl+C

Run from the scripts/ directory (after `conda activate dover`):
  # Option A: by scenario id (uses ../logs/scenario_{id}/...)
  python scripts/state_loader.py --scenario 1

  # Option B: by explicit files
  python scripts/state_loader.py \
    --history ../logs/scenario_1/scenario_1_history.pickle \
    --cache   ../logs/scenario_1/scenario_1_cache.pickle

Notes on relative paths:
- This script is intended to be executed from the scripts/ directory
- It uses paths relative to the project root by going up one level (..)
- Adjust the module path or file paths if your layout differs
"""

import argparse
import os
import sys
from pathlib import Path

# Auto-detect project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # Add project root to path

# Default team module to load for agdebugger
DEFAULT_TEAM_MODULE = "scripts.m1_agdebugger_test:get_full_m1_team"


def resolve_paths(scenario: str | None, history: str | None, cache: str | None) -> tuple[Path, Path | None]:
    """Resolve effective history/cache paths.
    Priority: explicit --history/--cache > --scenario default folder.
    Returns (history_path, cache_path_or_none)
    """
    if history:
        history_path = Path(history)
    elif scenario:
        # Use project root
        history_path = PROJECT_ROOT / "logs" / f"scenario_{scenario}" / f"scenario_{scenario}_history.pickle"
    else:
        raise ValueError("Either --history or --scenario must be provided")

    cache_path = None
    if cache:
        cache_path = Path(cache)
    elif scenario:
        cand = PROJECT_ROOT / "logs" / f"scenario_{scenario}" / f"scenario_{scenario}_cache.pickle"
        if cand.exists():
            cache_path = cand

    return history_path, cache_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Restore agdebugger state from saved pickle files and launch UI")
    ap.add_argument("--scenario", help="Scenario id to auto-pick files from ../logs/scenario_{id}/...")
    ap.add_argument("--history", help="Path to history pickle (multi-session bundle supported)")
    ap.add_argument("--cache", help="Path to cache pickle (with team_id if available)")
    ap.add_argument("--module", default=DEFAULT_TEAM_MODULE, help="Team module to load (default: %(default)s)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default="8081")
    ap.add_argument("--quiet", action="store_true", help="Reduce uvicorn access logs")
    args = ap.parse_args()

    try:
        history_path, cache_path = resolve_paths(args.scenario, args.history, args.cache)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(2)

    if not history_path.exists():
        print(f"❌ History file not found: {history_path}")
        sys.exit(2)
    if cache_path is not None and not cache_path.exists():
        print(f"⚠️  Cache file not found, will proceed without cache: {cache_path}")
        cache_path = None

    # Optionally reduce uvicorn access logs via CLI env switches (supported by our CLI)
    if args.quiet:
        os.environ["AGDEBUGGER_UVICORN_ACCESS_LOG"] = "false"
        os.environ["AGDEBUGGER_UVICORN_LOG_LEVEL"] = "warning"

    # Prepare CLI argv exactly like calling `agdebugger` binary
    sys.argv = [
        "agdebugger",
        args.module,
        "--host", args.host,
        "--port", args.port,
        # "--launch",
        "--history", str(history_path),
    ]
    if cache_path is not None:
        sys.argv.extend(["--cache", str(cache_path)])

    print("🚀 Launching agdebugger with restored state:")
    print(f"   module  : {args.module}")
    print(f"   history : {history_path}")
    print(f"   cache   : {cache_path if cache_path else '(none)'}")
    print(f"   url     : http://{args.host}:{args.port}")
    print("   Press Ctrl+C to stop.")

    # Run the CLI (blocks until terminated)
    try:
        from autogen_ext.teams.magentic_one import MagenticOne
        _orig_m1_init = MagenticOne.__init__
        import os as _os
        sid_env = _os.environ.get("M1_SCENARIO_ID") or args.scenario
        run_dir = _os.environ.get("M1_SESSION_OUT_DIR") or str(PROJECT_ROOT / "logs" / f"scenario_{sid_env}")
        from pathlib import Path as _P
        rd = _P(run_dir)
        sd = rd / "websurfer_screenshot"
        dd = rd / "downloads"
        # dd = "C:/Users/v-mingm/Downloads"
        wd = rd / "workspace"
        vd = rd / "record"
        try:
            sd.mkdir(parents=True, exist_ok=True); dd.mkdir(parents=True, exist_ok=True); wd.mkdir(parents=True, exist_ok=True); vd.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        def _patched_m1_init(self, client, hil_mode=False, input_func=None, code_executor=None, websurfer_kwargs=None, filesurfer_base_path=None, code_executor_kwargs=None):
            if websurfer_kwargs is None:
                _headless = (_os.environ.get("M1_WS_HEADLESS", "false").lower() == "true")
                _animate = (_os.environ.get("M1_WS_ANIMATE", "false").lower() == "true")
                _record = (_os.environ.get("M1_WS_RECORD_VIDEO", "true").lower() == "true")
                _slowmo = int(_os.environ.get("M1_WS_SLOW_MO", "200"))
                _browser = _os.environ.get("M1_WS_BROWSER_CHANNEL", "msedge")
                _search = _os.environ.get("M1_WS_SEARCH_ENGINE", "google")
                _bdir = _os.environ.get("M1_WS_BROWSER_DATA_DIR", str(PROJECT_ROOT / "logs" / "websurfer_profile"))
                _ua = _os.environ.get("M1_WS_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0")
                websurfer_kwargs = {
                    "debug_dir": str(sd),
                    "to_save_screenshots": True,
                    "downloads_folder": str(dd),
                    "headless": _headless,
                    "animate_actions": _animate,
                    "record_video": _record,
                    "search_engine": _search,
                    "browser_data_dir": _bdir,
                    "browser_channel": _browser,
                    "playwright_launch_options": {"slow_mo": _slowmo, "args": ["--disable-blink-features=AutomationControlled", "--disable-infobars"]},
                    "playwright_context_options": {                                                                                                                                                                                                                                            
                                                    "record_video_dir": str(vd),                                                                                                                                                                                                                                               
                                                    "user_agent": _ua,                                                                                                                                                                                                                                                         
                                                    "locale": "en-US",                                                                                                                                                                                                                                                         
                                                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"}                                                                                                                                                                                                                   
                                                    }
                }
            if filesurfer_base_path is None:
                filesurfer_base_path = _os.environ.get("M1_FS_BASE_PATH", str(rd))
            if code_executor_kwargs is None:
                code_executor_kwargs = {"work_dir": _os.environ.get("M1_CODE_WORK_DIR", str(wd))}
            return _orig_m1_init(self, client, hil_mode, input_func, code_executor, websurfer_kwargs, filesurfer_base_path, code_executor_kwargs)
        MagenticOne.__init__ = _patched_m1_init
        try:
            from autogen_ext.agents.file_surfer import FileSurfer
            _orig_fs_init = FileSurfer.__init__
            def _patched_fs_init(self, name, model_client, description=FileSurfer.DEFAULT_DESCRIPTION, base_path=None):
                if base_path is None:
                    base_path = str(PROJECT_ROOT)
                return _orig_fs_init(self, name, model_client, description, base_path)
            FileSurfer.__init__ = _patched_fs_init
        except Exception:
            pass
    except Exception:
        pass
    from agdebugger.cli import main_cli
    main_cli()


if __name__ == "__main__":
    main()

