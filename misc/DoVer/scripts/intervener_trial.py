#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
import time
import re
from urllib.request import urlopen, Request


PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# Default; will be overridden at runtime based on --port
BASE_URL = "http://127.0.0.1:8081/api"


def http_get_json(path: str):
    raw = None
    with urlopen(Request(f"{BASE_URL}{path}"), timeout=10) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def http_post_json(path: str, payload: dict | None = None):
    data = (json.dumps(payload or {})).encode("utf-8")
    with urlopen(
        Request(
            f"{BASE_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        ),
        timeout=20,
    ) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def wait_server(timeout: float = 90.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            http_get_json("/loop_status")
            return True
        except Exception:
            time.sleep(1.0)
    return False


def wait_until_idle(poll: float = 1.0, stable: int = 2, max_wait: float = 600.0) -> bool:
    t0 = time.time()
    ok = 0
    while time.time() - t0 < max_wait:
        try:
            n = http_get_json("/num_tasks")
            n = int(n if isinstance(n, int) else n.get("value", 0))
            q = http_get_json("/getMessageQueue")
            qlen = len(q) if isinstance(q, list) else int(q or 0)
            if n == 0 and qlen == 0:
                ok += 1
                if ok >= stable:
                    return True
            else:
                ok = 0
        except Exception:
            ok = 0
        time.sleep(poll)
    return False


def _get_session_message_count() -> int:
    try:
        sess = http_get_json("/getSessionHistory")
        cur = sess.get("current_session")
        mh = sess.get("message_history", {})
        if isinstance(cur, int) and cur in mh:
            return len(mh[cur].get("messages", []))
        if isinstance(mh, dict) and str(cur) in mh:
            return len(mh[str(cur)].get("messages", []))
        return 0
    except Exception:
        return 0


def _wait_for_message_count_increase(baseline: int, timeout: float = 300.0, poll: float = 2.0) -> bool:
    print("\u23f3 \u7b49\u5f85\u5386\u53f2\u6d88\u606f\u6570\u589e\u957f\u4ee5\u786e\u8ba4\u524d\u5411\u63a8\u7406\u5f00\u59cb...")
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        cnt = _get_session_message_count()
        if last != cnt:
            print(f"\ud83d\udcca \u5386\u53f2\u6d88\u606f\u6570: {cnt}")
            last = cnt
        if cnt > baseline:
            print("\u2705 \u68c0\u6d4b\u5230\u5386\u53f2\u589e\u957f\uff0c\u5df2\u5f00\u59cb\u524d\u5411\u63a8\u7406")
            return True
        time.sleep(poll)
    print("\u26a0\ufe0f \u7b49\u5f85\u5386\u53f2\u589e\u957f\u8d85\u65f6")
    return False


def get_groupchat_steps(session: dict) -> list[dict]:
    cur = session.get("current_session")
    mh = session.get("message_history", {})
    messages = mh.get(str(cur), {}).get("messages", []) if isinstance(mh, dict) else []
    steps = []
    for it in messages:
        msg = (it or {}).get("message", {})
        if msg.get("type") != "GroupChatAgentResponse":
            continue
        chat = msg.get("response", {}).get("chat_message", {})
        steps.append(
            {
                "timestamp": it.get("timestamp"),
                "name": msg.get("name") or chat.get("source"),
                "content": chat.get("content"),
                "type": chat.get("type"),
                "message": msg,
            }
        )
    return steps


def verify_edit_applied(ts: int, expected_content) -> bool:
    try:
        sess = http_get_json("/getSessionHistory")
        cur = sess.get("current_session")
        mh = sess.get("message_history", {})
        session = mh.get(str(cur), {}) if isinstance(mh, dict) else {}
        msgs = session.get("messages", []) if isinstance(session, dict) else []
        for it in msgs:
            if it.get("timestamp") == ts:
                msg = (it or {}).get("message", {})
                chat = (msg.get("response", {}) or {}).get("chat_message", {})
                return chat.get("content") == expected_content
    except Exception:
        pass
    return False


def _has_groupchat_termination() -> bool:
    try:
        sess = http_get_json("/getSessionHistory")
        cur = sess.get("current_session")
        mh = sess.get("message_history", {})
        cur_key = str(cur) if isinstance(mh, dict) and str(cur) in mh else cur
        session = mh.get(cur_key, {}) if isinstance(mh, dict) else None
        messages = session.get("messages", []) if isinstance(session, dict) else []
        for item in reversed(messages):
            msg = item.get("message", {}) if isinstance(item, dict) else {}
            if msg.get("type") == "GroupChatTermination":
                return True
        return False
    except Exception:
        return False


def wait_until_terminated(poll_interval: float = 1.0, max_wait_sec: int = 900) -> bool:
    print("\u23f3 \u7b49\u5f85 GroupChatTermination \u4e8b\u4ef6...")
    start = time.time()
    while time.time() - start < max_wait_sec:
        if _has_groupchat_termination():
            print("\u2705 \u5df2\u68c0\u6d4b\u5230 GroupChatTermination")
            return True
        time.sleep(poll_interval)
    print("\u26a0\ufe0f \u7b49\u5f85\u7ec8\u6b62\u4e8b\u4ef6\u8d85\u65f6")
    return False


def build_new_content(original_type: str, suggestion: dict, original_content: object) -> object:
    """Build new content according to category with append/replace policy.
    - orchestrator_instruction: REPLACE original content with corrected instruction
    - orchestrator_ledger: Replace Task Full Ledger sections (Facts/Plan)
    - subagent_instruction: APPEND guidance to original content
    Content type preserved:
    - TextMessage -> string (append with two newlines and [INTERVENTION])
    - MultiModalMessage -> list[str,...] (append a new text element)
    """
    s = suggestion.get("suggestions", {})
    cat = suggestion.get("category", "other")

    # Build human-readable intervention text from suggestions
    if cat == "orchestrator_ledger":
        ledger = s.get("ledger", {})
        plan_edits = ledger.get("plan_edits", [])
        snippets = "\n".join([x for x in plan_edits if isinstance(x, str)]).strip()

        def _parse_tag_blocks(src: str, tags: list[str]) -> dict[str, str]:
            """Extract content blocks following specific [TAG] markers.
            Robust to bracket usage inside content (e.g., "[book title]").
            Returns {tag: joined_content} with each tag's segments concatenated.
            """
            if not src:
                return {}
            tag_pattern = r"\[(" + "|".join(map(re.escape, tags)) + r")\]\s*:?"
            regex = re.compile(tag_pattern)
            parts: dict[str, list[str]] = {}
            matches = list(regex.finditer(src))
            if not matches:
                return {}
            for idx, m in enumerate(matches):
                tag = m.group(1)
                content_start = m.end()
                content_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(src)
                block = src[content_start:content_end].strip()
                if block:
                    parts.setdefault(tag, []).append(block)
            return {k: "\n".join(v).strip() for k, v in parts.items()}

        blocks = _parse_tag_blocks(snippets, ["FACTS_REPLACEMENT", "PLAN_REPLACEMENT"])
        facts_new = blocks.get("FACTS_REPLACEMENT", "")
        plan_new = blocks.get("PLAN_REPLACEMENT", "")
        base = ""
        if isinstance(original_content, list):
            base = "\n".join([x for x in original_content if isinstance(x, str)])
        elif isinstance(original_content, str):
            base = original_content
        else:
            base = str(original_content or "")
        facts_h = "Here is an initial fact sheet to consider:"
        plan_h = "Here is the plan to follow as best as possible:"
        def _replace_between(text, header, end_header, body):
            if not body:
                return text
            i = text.find(header)
            if i == -1:
                return text
            s2 = i + len(header)
            while s2 < len(text) and text[s2] in " \t\r\n":
                s2 += 1
            e2 = text.find(end_header, s2) if end_header else -1
            if e2 == -1:
                e2 = len(text)
            before = text[:s2]
            after = text[e2:]
            mid = body.strip()
            if after and not after.startswith("\n"):
                return before + mid + "\n" + after
            return before + mid + after
        updated = _replace_between(base, facts_h, plan_h, facts_new)
        updated = _replace_between(updated, plan_h, None, plan_new)
        text = (updated.strip() or (snippets or (suggestion.get("raw") or "")).strip())
    elif cat == "orchestrator_instruction":
        text = s.get("new_instruction") or "Please refine instruction as suggested."
    elif cat == "subagent_instruction":
        sg = s.get("subagent_guidance", {})
        pif = sg.get("previous_instruction_fix")
        text = (str(pif) if pif is not None else (suggestion.get("raw") or "")).strip()
    else:
        text = suggestion.get("raw") or json.dumps(suggestion, ensure_ascii=False)

    # Replacement for orchestrator_instruction
    if cat in ("orchestrator_instruction","orchestrator_ledger","subagent_instruction"):
        if original_type == "MultiModalMessage":
            return [text]
        return text

    # Otherwise: append to original content
    if original_type == "MultiModalMessage":
        base = list(original_content) if isinstance(original_content, list) else []
        base.append(f"[INTERVENTION] {text}")
        return base
    # Text/other
    base = original_content if isinstance(original_content, str) else ""
    base = base.rstrip()
    appended = f"{base}\n\n[INTERVENTION] {text}" if base else f"[INTERVENTION] {text}"
    return appended



def main():
    ap = argparse.ArgumentParser(description="Trial Intervener")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--round", default="1")
    ap.add_argument("--trial", type=int)
    ap.add_argument(
        "--model",
        default="gpt-4o",

        help="Model to use for the restored run (default: gpt-4o)",
    )
    ap.add_argument("--port", default="7111", help="Port for restored UI")
    args = ap.parse_args()

    sid = str(args.scenario)
    round_id = str(args.round)
    trial_req = args.trial if args.trial is not None else None

    trial_sugg_path = LOGS_DIR / f"scenario_{sid}" / round_id / f"intervention_trial_scenario_{sid}.json"
    if not trial_sugg_path.exists():
        alt = LOGS_DIR / f"scenario_{sid}" / round_id / "intervention_trial.json"
        trial_sugg_path = alt if alt.exists() else trial_sugg_path
    if not trial_sugg_path.exists():
        raise SystemExit(f"Trial interventions not found: {trial_sugg_path}")

    suggestions = json.loads(trial_sugg_path.read_text(encoding="utf-8"))
    if not isinstance(suggestions, list) or not suggestions:
        raise SystemExit("Empty trial interventions")

    history_pickle = LOGS_DIR / f"scenario_{sid}" / round_id / f"scenario_{sid}_history.pickle"
    cache_pickle = LOGS_DIR / f"scenario_{sid}" / round_id / f"scenario_{sid}_cache.pickle"
    if not history_pickle.exists():
        raise SystemExit(f"History pickle not found: {history_pickle}")

    results = []
    found = False

    for t in sorted(suggestions, key=lambda x: int(x.get("trial_index", 0))):
        if trial_req is not None:
            try:
                if int(t.get("trial_index", 0)) != int(trial_req):
                    continue
            except Exception:
                continue
        trial_idx = int(t.get("trial_index", 0))
        step_idx = int(t.get("step"))
        category = t.get("category", "other")

        env = os.environ.copy()
        # Ensure UTF-8 stdout/stderr for child Python to avoid Windows cp1252 emoji issues
        env["PYTHONIOENCODING"] = env.get("PYTHONIOENCODING", "utf-8")
        env["PYTHONUTF8"] = env.get("PYTHONUTF8", "1")
        out_dir_env = LOGS_DIR / f"scenario_{sid}" / round_id / f"trial_{trial_idx}"
        env["M1_SESSION_OUT_DIR"] = str(out_dir_env)
        env["AGDEBUGGER_UVICORN_ACCESS_LOG"] = "false"
        env["AGDEBUGGER_UVICORN_LOG_LEVEL"] = "warning"
        env["M1_SCENARIO_ID"] = sid
        # Align with simulation_runner: pass model via env for m1_agdebugger_test
        env["M1_MODEL"] = args.model

        proc = subprocess.Popen([
            "python", str(PROJECT_ROOT / "scripts" / "state_loader.py"),
            "--history", str(history_pickle),
            "--cache", str(cache_pickle),
            "--port", str(args.port),
        ], cwd=str(PROJECT_ROOT), env=env)

        try:
            # Ensure HTTP helpers target the same port as state_loader
            global BASE_URL
            BASE_URL = f"http://127.0.0.1:{args.port}/api"
            if not wait_server(90):
                raise SystemExit("Backend not reachable")

            session = http_get_json("/getSessionHistory")
            steps = get_groupchat_steps(session)
            if not (0 <= step_idx < len(steps)):
                raise SystemExit(f"Step idx out of range: {step_idx} (total {len(steps)})")

            target_idx = step_idx
            def _is_orch(n):
                try:
                    return isinstance(n, str) and ("orchestrator" in n.lower())
                except Exception:
                    return False
            if category == "subagent_instruction":
                for i in range(step_idx - 1, -1, -1):
                    if _is_orch(steps[i].get("name")):
                        target_idx = i
                        break
            elif category in ("orchestrator_instruction", "orchestrator_ledger"):
                for i in range(min(step_idx, len(steps) - 1), -1, -1):
                    if _is_orch(steps[i].get("name")):
                        target_idx = i
                        break

            step = steps[target_idx]
            ts = step.get("timestamp")
            orig_msg = step.get("message") or {}
            orig_chat = (orig_msg.get("response", {}) or {}).get("chat_message", {})
            orig_type = orig_chat.get("type", "TextMessage")
            orig_content = orig_chat.get("content")

            new_content = build_new_content(orig_type, t, orig_content)
            chat_message = {
                **{k: v for k, v in orig_chat.items() if k != "content"},
                "id": orig_chat.get("id"),
                "created_at": orig_chat.get("created_at"),
                "content": new_content,
                "type": orig_type,
            }
            edited_message = {
                **{k: v for k, v in orig_msg.items() if k != "response"},
                "response": {
                    "chat_message": chat_message,
                    "inner_messages": (orig_msg.get("response", {}) or {}).get("inner_messages"),
                },
            }

            http_post_json("/editAndRevertHistoryMessage", {"timestamp": ts, "body": edited_message})

            applied = verify_edit_applied(ts, new_content)
            if not applied:
                try:
                    queue = http_get_json("/getMessageQueue") or []
                    target_q = None
                    for i, qmsg in enumerate(queue):
                        if not isinstance(qmsg, dict):
                            continue
                        if qmsg.get("type") != edited_message.get("type"):
                            continue
                        if qmsg.get("name") != (orig_msg.get("name") or (orig_chat.get("source") if isinstance(orig_chat, dict) else None)):
                            continue
                        qchat = (qmsg.get("response", {}) or {}).get("chat_message", {})
                        if json.dumps(qchat.get("content"), sort_keys=True, ensure_ascii=False) == json.dumps(orig_content, sort_keys=True, ensure_ascii=False):
                            target_q = i
                            break
                    if target_q is not None:
                        http_post_json("/editQueue", {"idx": target_q, "body": edited_message})
                except Exception:
                    pass

            baseline_cnt = _get_session_message_count()
            http_post_json("/start_loop")
            _wait_for_message_count_increase(baseline_cnt, timeout=600.0, poll=2.0)
            if not wait_until_terminated(max_wait_sec=900):
                wait_until_idle(poll=2.0, stable=2, max_wait=900)

            out_dir = out_dir_env
            out_dir.mkdir(parents=True, exist_ok=True)
            hist_pkl = out_dir / f"scenario_{sid}_trial_{trial_idx}_history.pickle"
            cache_pkl = out_dir / f"scenario_{sid}_trial_{trial_idx}_cache.pickle"
            logs_json = out_dir / f"scenario_{sid}_trial_{trial_idx}_logs.json"
            sess_json = out_dir / f"scenario_{sid}_trial_{trial_idx}_history.json"

            try:
                http_post_json("/save_to_file_custom", {"history_path": str(hist_pkl), "cache_path": str(cache_pkl)})
            except Exception:
                http_post_json(f"/save_to_file_custom?history={hist_pkl}&cache={cache_pkl}")
            try:
                logs = http_get_json("/logs")
                logs_json.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            try:
                sess = http_get_json("/getSessionHistory")
                sess_json.write_text(json.dumps(sess, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

            results.append({
                "status": "ok",
                "scenario": sid,
                "trial_index": trial_idx,
                "edited_step": step_idx,
                "timestamp": ts,
                "output_dir": str(out_dir),
            })
            found = True
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    if trial_req is not None and not found:
        raise SystemExit(f"Requested trial not found: {trial_req}")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
