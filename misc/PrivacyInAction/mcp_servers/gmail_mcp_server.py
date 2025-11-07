"""FastMCP server exposing advanced Gmail search and retrieval tools.

Features
--------
* Search Gmail with rich query syntax (same as Gmail web UI).
* Optional pagination (``nextPageToken``).
* Include snippet previews **or full plain-text bodies** in search results.
* Retrieve individual messages with decoded plain-text bodies.
* Minimal error handling & no global discovery cache for cold-start speed.
* Token path and scopes are configurable via environment variables.
* Structured JSON outputs that are easy for the calling agent to reason about.
"""
from __future__ import annotations

import os
import base64
from typing import List, Dict, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP
from email.message import EmailMessage
from privacygate import AGENT_PRIVACY_GATE

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCOPES = [
    "https://mail.google.com/"
]
TOKEN_FILE = os.getenv("GMAIL_TOKEN_PATH", "token.json")


# ---------------------------------------------------------------------------
# Gmail service factory (separate so it can be swapped out in tests)
# ---------------------------------------------------------------------------

def get_gmail_service():
    """Return an authorised Gmail ``Resource`` instance."""
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # ``cache_discovery=False`` prevents slow disk writes in some environments
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


gmail = get_gmail_service()

# FastMCP server instance ----------------------------------------------------
mcp = FastMCP("gmail-search-advanced")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _headers_from_payload(message: dict) -> dict:
    hdrs = {h["name"]: h["value"] for h in message["payload"]["headers"]}
    return {
        "id": message["id"],
        "subject": hdrs.get("Subject", ""),
        "from": hdrs.get("From", ""),
        "date": hdrs.get("Date", ""),
    }


def _decode_base64url(data: str | bytes | None) -> str:
    if not data:
        return ""
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64decode(data).decode("utf-8", "ignore")


def _extract_plain_text(message: dict) -> str:
    """Walk the MIME tree and return the first ``text/plain`` part found."""
    payload = message.get("payload", {})

    # Single-part message
    if not payload.get("parts"):
        return _decode_base64url(payload.get("body", {}).get("data"))

    stack = payload["parts"].copy()
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            return _decode_base64url(part.get("body", {}).get("data"))
        # Multipart parts can themselves contain sub-parts
        stack.extend(part.get("parts", []))
    return ""  # fallback if no plain text part exists


# ---------------------------------------------------------------------------
# Exposed tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="gmail_search_messages",
    description=(
        "Search Gmail and return message metadata. Supports Gmail's search "
        "query language. Optional pagination via ``page_token``. Set "
        "``include_snippet=True`` to include the message snippet preview. "
        "Set ``include_body=True`` to retrieve the decoded plain-text body "
        "for each result (may increase latency)."
    ),
)

def gmail_search_messages(
    query: str,
    max_results: int = 10,
    include_snippet: bool = False,
    include_body: bool = False,
    page_token: Optional[str] = None,
) -> dict:
    """Return a dict with ``messages`` list plus ``nextPageToken`` if more.

    Example::

        {
            "messages": [
                {
                    "id": "18c1…",
                    "subject": "Hello world",
                    "from": "Alice <alice@example.com>",
                    "date": "Thu, 1 May 2025 09:00:00 +0900",
                    "snippet": "Hi Bob — just a quick note…",  # if requested
                    "body": "Hi Bob, …"                             # if requested
                }
            ],
            "nextPageToken": "…"  # present when further pages exist
        }
    """
    try:
        res = gmail.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
            pageToken=page_token,
        ).execute()
    except HttpError as e:
        return {"error": str(e)}

    out: List[Dict[str, str]] = []
    for msg_meta in res.get("messages", []):
        # Choose retrieval format based on whether we need the body.
        fmt = "full" if include_body else "metadata"
        try:
            meta = gmail.users().messages().get(
                userId="me",
                id=msg_meta["id"],
                format=fmt,
                metadataHeaders=["Subject", "From", "Date"] if fmt == "metadata" else None,
            ).execute()
        except HttpError:
            # Skip messages we cannot retrieve
            continue

        summary = _headers_from_payload(meta)
        if include_snippet:
            summary["snippet"] = meta.get("snippet", "")
        if include_body:
            summary["body"] = _extract_plain_text(meta)
        out.append(summary)

    return {
        "messages": out,
        "nextPageToken": res.get("nextPageToken"),
        "resultSizeEstimate": res.get("resultSizeEstimate"),
    }


@mcp.tool(
    name="gmail_get_message",
    description="Retrieve a full Gmail message with decoded plain-text body.",
)

def gmail_get_message(message_id: str) -> dict:
    """Return headers, snippet and decoded ``text/plain`` body for a message."""
    try:
        msg = gmail.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
    except HttpError as e:
        return {"error": str(e)}

    info = _headers_from_payload(msg)
    info["snippet"] = msg.get("snippet", "")
    info["body"] = _extract_plain_text(msg)

    return info

@mcp.tool(
    name="gmail_get_all_messages",
    description=(
        "Retrieve all messages from the Gmail inbox with pagination support. "
        "Can include snippet previews or full plain-text bodies in results. "
        "Results are ordered by date with newest messages first."
    ),
)
def gmail_get_all_messages(
    max_results: int = 20,
    include_snippet: bool = False,
    include_body: bool = False,
    page_token: Optional[str] = None,
) -> dict:
    """Return a dict with all messages from inbox plus nextPageToken if more exist.
    
    Example::
    
        {
            "messages": [
                {
                    "id": "18c1…",
                    "subject": "Hello world",
                    "from": "Alice <alice@example.com>",
                    "date": "Thu, 1 May 2025 09:00:00 +0900",
                    "snippet": "Hi Bob — just a quick note…",  # if requested
                    "body": "Hi Bob, …"                        # if requested
                }
            ],
            "nextPageToken": "…",  # present when further pages exist
            "resultSizeEstimate": 1542  # approximate total number of messages
        }
    """
    try:
        # The empty query will retrieve all messages
        res = gmail.users().messages().list(
            userId="me",
            maxResults=max_results,
            pageToken=page_token,
        ).execute()
    except HttpError as e:
        return {"error": str(e)}

    out: List[Dict[str, str]] = []
    for msg_meta in res.get("messages", []):
        # Choose retrieval format based on whether we need the body
        fmt = "full" if include_body else "metadata"
        try:
            meta = gmail.users().messages().get(
                userId="me",
                id=msg_meta["id"],
                format=fmt,
                metadataHeaders=["Subject", "From", "Date"] if fmt == "metadata" else None,
            ).execute()
        except HttpError:
            # Skip messages we cannot retrieve
            continue

        summary = _headers_from_payload(meta)
        if include_snippet:
            summary["snippet"] = meta.get("snippet", "")
        if include_body:
            summary["body"] = _extract_plain_text(meta)
        out.append(summary)

    return {
        "messages": out,
        "nextPageToken": res.get("nextPageToken"),
        "resultSizeEstimate": res.get("resultSizeEstimate"),
    }

@mcp.tool(
    name="gmail_send_message",
    description=(
        "Send an e-mail through the authenticated user’s Gmail account.\n"
        "Required: ▸ to (list[str]) ▸ subject (str) ▸ body (str, plain-text)\n"
        "Optional: cc, bcc, sender (override the default From).\n"
        # "Privacy Gate: this send function may leak user's information in previous tool call observation."
        # "Thus please adhere to the following privacy instructions:\n"
        # f"{AGENT_PRIVACY_GATE}"
    ),
)
def gmail_send_message(
    *,
    to: List[str],
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    sender: Optional[str] = None,
) -> dict:
    """
    Build a simple RFC-5322 message and send it.
    Returns the API’s full response (contains the message id).
    """
    # ---------- build the MIME message ----------
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    if sender:
        msg["From"] = sender  # otherwise Gmail sets the account’s default
    msg.set_content(body)

    raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    # ---------- call the Gmail API ----------
    try:
        res = gmail.users().messages().send(
            userId="me",
            body={"raw": raw_msg},
        ).execute()
        return res   # includes id, threadId, labelIds
    except HttpError as e:
        return {"error": str(e)}

# ---------------------------------------------------------------------------
# CLI entry-point (handy during local development)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()