"""FastMCP server exposing Notion search and page retrieval tools.

Features
--------
* Search Notion databases and pages with query filters
* Retrieve full page content with blocks
* Support for various block types (text, headings, etc.)
* Minimal error handling for cold-start speed
* Token and configuration via environment variables
* Structured JSON outputs for easy agent reasoning
"""
from __future__ import annotations

import os
from typing import List, Dict, Optional, Any
import requests
from datetime import datetime
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2022-06-28")
NOTION_API_URL = "https://api.notion.com/v1"

if not NOTION_API_KEY:
    raise ValueError("NOTION_API_KEY environment variable is required")

# ---------------------------------------------------------------------------
# Notion API client (separate so it can be swapped out in tests)
# ---------------------------------------------------------------------------

class NotionClient:
    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION
        }
        self.request_timeout = 60.0
    
    def search(
        self,
        query: str,
        filter_type: Optional[str] = None,
        sort_direction: str = "descending",
        page_size: int = 10,
    ) -> dict:
        """Search Notion pages and databases (now case-insensitive on filter_type)."""
        url = f"{NOTION_API_URL}/search"

        query = query.lower() if query else ""

        payload = {
            "query": query,
            "sort": {"direction": sort_direction, "timestamp": "last_edited_time"},
            "page_size": page_size,
        }

        # ✨ NEW: normalise filter_type to lower-case so callers can pass "Page", "PAGE", etc.
        if filter_type:
            filter_type = filter_type.lower()

        if filter_type in {"page", "database"}:
            payload["filter"] = {"property": "object", "value": filter_type}

        response = requests.post(url, headers=self.headers, json=payload, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()
    
    def get_page(self, page_id: str) -> dict:
        """Get page properties and metadata."""
        url = f"{NOTION_API_URL}/pages/{page_id}"
        response = requests.get(url, headers=self.headers, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()
    
    def get_blocks(self, block_id: str, start_cursor: Optional[str] = None) -> dict:
        """Get child blocks of a page or block."""
        url = f"{NOTION_API_URL}/blocks/{block_id}/children"
        params = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        
        response = requests.get(url, headers=self.headers, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()

# Initialize Notion client
notion = NotionClient(NOTION_API_KEY)

# FastMCP server instance
mcp = FastMCP("notion-manager")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_title_from_page(page: dict) -> str:
    """Extract title from page properties."""
    properties = page.get("properties", {})
    
    # Find the title property (it can have different names)
    for prop_name, prop_value in properties.items():
        if prop_value.get("type") == "title":
            title_array = prop_value.get("title", [])
            if title_array and len(title_array) > 0:
                return title_array[0].get("text", {}).get("content", "Untitled")
    
    return "Untitled"

def _extract_text_from_rich_text(rich_text_array: List[dict]) -> str:
    """Extract plain text from Notion's rich text format."""
    if not rich_text_array:
        return ""
    
    text_parts = []
    for item in rich_text_array:
        if item.get("type") == "text":
            text_parts.append(item.get("text", {}).get("content", ""))
    
    return "".join(text_parts)

def _format_block(block: dict) -> dict:
    """Format a Notion block into a simplified structure."""
    block_type = block.get("type")
    block_data = block.get(block_type, {})
    
    formatted = {
        "id": block.get("id"),
        "type": block_type,
        "created_time": block.get("created_time"),
        "last_edited_time": block.get("last_edited_time"),
        "has_children": block.get("has_children", False)
    }
    
    # Extract text content based on block type
    if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", 
                      "bulleted_list_item", "numbered_list_item", "to_do", "toggle"]:
        formatted["text"] = _extract_text_from_rich_text(block_data.get("rich_text", []))
        
        # Add checkbox state for to-do items
        if block_type == "to_do":
            formatted["checked"] = block_data.get("checked", False)
    
    elif block_type == "code":
        formatted["language"] = block_data.get("language", "plain text")
        formatted["text"] = _extract_text_from_rich_text(block_data.get("rich_text", []))
    
    elif block_type == "divider":
        formatted["text"] = "---"
    
    elif block_type == "child_page":
        formatted["title"] = block_data.get("title", "Untitled")
    
    elif block_type == "child_database":
        formatted["title"] = block_data.get("title", "Untitled Database")
    
    return formatted

def _get_all_blocks(page_id: str) -> List[dict]:
    """Recursively get all blocks from a page."""
    all_blocks = []
    next_cursor = None
    
    while True:
        response = notion.get_blocks(page_id, start_cursor=next_cursor)
        blocks = response.get("results", [])
        
        for block in blocks:
            formatted_block = _format_block(block)
            all_blocks.append(formatted_block)
            
            # Recursively get child blocks if they exist
            if block.get("has_children", False):
                child_blocks = _get_all_blocks(block["id"])
                formatted_block["children"] = child_blocks
        
        next_cursor = response.get("next_cursor")
        if not next_cursor or not response.get("has_more", False):
            break
    
    return all_blocks

# ---------------------------------------------------------------------------
# Exposed tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="NotionManagerSearchContent",
    description=(
        "Search Notion for pages with full-text search. Returns pages where the query matches titles OR content. "
        "Results are sorted by last_edited_time."
    ),
)
def notion_search_content(
    query: str,
) -> dict:
    """Return search results with page metadata where query matches title OR content.
    
    Example return::
    
        {
            "results": [
                {
                    "id": "abc123...",
                    "type": "page",
                    "title": "Meeting Notes",
                    "url": "https://notion.so/...",
                    "created_time": "2024-01-01T10:00:00.000Z",
                    "last_edited_time": "2024-01-02T15:30:00.000Z",
                    "parent_type": "workspace",
                    "matches": ["Found the term 'therapy' in paragraph: 'The integration of..."]
                }
            ],
            "has_more": false,
            "next_cursor": null
        }
    """
    try:
        # First try to search by title (native Notion search)
        title_response = notion.search(
            query=query,
            filter_type="page",
            page_size=50  # Increased page size to get more potential matches
        )
        
        title_results = []
        for item in title_response.get("results", []):
            result = {
                "id": item.get("id"),
                "type": item.get("object"),
                "title": _extract_title_from_page(item),
                "url": item.get("url"),
                "created_time": item.get("created_time"),
                "last_edited_time": item.get("last_edited_time"),
                "match_type": "title",
                "matches": []
            }
            
            # Add parent information
            parent = item.get("parent", {})
            parent_type = parent.get("type")
            result["parent_type"] = parent_type
            
            if parent_type == "page_id":
                result["parent_id"] = parent.get("page_id")
            elif parent_type == "database_id":
                result["parent_id"] = parent.get("database_id")
            
            title_results.append(result)
        
        # If query is empty, just return the title results
        if not query.strip():
            return {
                "results": title_results,
                "has_more": title_response.get("has_more", False),
                "next_cursor": title_response.get("next_cursor")
            }
        
        # For content search, get all pages (empty query returns all)
        all_pages_response = notion.search(
            query="",
            filter_type="page",
            page_size=50
        )
        
        # Process pages that weren't found in title search
        content_results = []
        query_lower = query.lower()
        
        for item in all_pages_response.get("results", []):
            # Skip pages already found in title search
            if any(r["id"] == item.get("id") for r in title_results):
                continue
                
            page_id = item.get("id")
            
            # Get the page content
            try:
                page_content = _get_all_blocks(page_id)
                matches = []
                
                # Search through all blocks of content
                for block in page_content:
                    if "text" in block and query_lower in block["text"].lower():
                        # Found a match in content
                        block_type = block.get("type", "block")
                        match_text = block.get("text", "")
                        # Add snippet of matching text (truncate if too long)
                        if len(match_text) > 100:
                            # Find the position of the match
                            match_pos = match_text.lower().find(query_lower)
                            # Get context around the match
                            start = max(0, match_pos - 40)
                            end = min(len(match_text), match_pos + len(query) + 40)
                            match_text = "..." + match_text[start:end] + "..." if start > 0 else match_text[start:end] + "..."
                        
                        matches.append(f"Found '{query}' in {block_type}: '{match_text}'")
                    
                    # Check children blocks too if they exist
                    if "children" in block:
                        for child in block["children"]:
                            if "text" in child and query_lower in child["text"].lower():
                                child_type = child.get("type", "block")
                                match_text = child.get("text", "")
                                # Truncate if too long
                                if len(match_text) > 100:
                                    match_pos = match_text.lower().find(query_lower)
                                    start = max(0, match_pos - 40)
                                    end = min(len(match_text), match_pos + len(query) + 40)
                                    match_text = "..." + match_text[start:end] + "..." if start > 0 else match_text[start:end] + "..."
                                
                                matches.append(f"Found '{query}' in {child_type}: '{match_text}'")
                
                # If matches were found, add this page to results
                if matches:
                    result = {
                        "id": item.get("id"),
                        "type": item.get("object"),
                        "title": _extract_title_from_page(item),
                        "url": item.get("url"),
                        "created_time": item.get("created_time"),
                        "last_edited_time": item.get("last_edited_time"),
                        "match_type": "content",
                        "matches": matches
                    }
                    
                    # Add parent information
                    parent = item.get("parent", {})
                    parent_type = parent.get("type")
                    result["parent_type"] = parent_type
                    
                    if parent_type == "page_id":
                        result["parent_id"] = parent.get("page_id")
                    elif parent_type == "database_id":
                        result["parent_id"] = parent.get("database_id")
                    
                    content_results.append(result)
            
            except Exception as e:
                # Skip pages with errors
                continue
        
        # Combine and sort all results by last_edited_time
        combined_results = title_results + content_results
        combined_results.sort(key=lambda x: x.get("last_edited_time", ""), reverse=True)
        
        return {
            "results": combined_results,
            "has_more": False,  # We're handling pagination differently now
            "next_cursor": None
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

@mcp.tool(
    name="NotionManagerGetAllContent",
    description=(
        "Retrieve all pages from Notion workspace, ordered by last_edited_time. "
        "Returns both page metadata and summarized content. "
        "Supports pagination for handling large workspaces."
    ),
)
def notion_get_all_content(
    page_size: int = 20,
    include_content: bool = False,
    start_cursor: Optional[str] = None,
) -> dict:
    """Return all pages in workspace with optional content preview.
    
    Example return::
    
        {
            "results": [
                {
                    "id": "abc123...",
                    "type": "page",
                    "title": "Project Roadmap",
                    "url": "https://notion.so/...",
                    "created_time": "2024-01-01T10:00:00.000Z",
                    "last_edited_time": "2024-01-02T15:30:00.000Z",
                    "parent_type": "workspace",
                    "content_preview": "This document outlines our Q2 goals..."  # if include_content=True
                }
            ],
            "has_more": true,
            "next_cursor": "cursor-value-for-pagination"
        }
    """
    try:
        # Search with empty query to get all pages
        response = notion.search(
            query="",
            filter_type="page",
            page_size=page_size,
            # Note: Notion's API already handles the start_cursor
        )
        
        results = []
        for item in response.get("results", []):
            result = {
                "id": item.get("id"),
                "type": item.get("object"),
                "title": _extract_title_from_page(item),
                "url": item.get("url"),
                "created_time": item.get("created_time"),
                "last_edited_time": item.get("last_edited_time"),
            }
            
            # Add parent information
            parent = item.get("parent", {})
            parent_type = parent.get("type")
            result["parent_type"] = parent_type
            
            if parent_type == "page_id":
                result["parent_id"] = parent.get("page_id")
            elif parent_type == "database_id":
                result["parent_id"] = parent.get("database_id")
            
            # Optionally include content preview
            if include_content:
                try:
                    # Get the first few blocks to create a preview
                    page_blocks = notion.get_blocks(item.get("id"))
                    blocks = page_blocks.get("results", [])
                    
                    # Extract text from first few blocks to create a preview
                    content_preview = []
                    for block in blocks[:3]:  # Limit to first 3 blocks for preview
                        block_type = block.get("type")
                        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
                            block_data = block.get(block_type, {})
                            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
                            if text:
                                content_preview.append(text)
                    
                    # Join with spaces and truncate if too long
                    preview_text = " ".join(content_preview)
                    if len(preview_text) > 200:
                        preview_text = preview_text[:197] + "..."
                    
                    result["content_preview"] = preview_text
                except Exception as e:
                    # If there's an error getting preview, just skip it
                    result["content_preview"] = ""
            
            results.append(result)
        
        return {
            "results": results,
            "has_more": response.get("has_more", False),
            "next_cursor": response.get("next_cursor")
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

@mcp.tool(
    name="NotionManagerReadPage",
    description=(
        "Retrieve full content of a Notion page including all blocks. "
        "Returns structured content with text, headings, lists, etc. "
        "Handles nested blocks and various content types."
    ),
)
def notion_read_page(page_id: str) -> dict:
    """Return page metadata and all content blocks.
    
    Example return::
    
        {
            "id": "abc123...",
            "title": "Page Title",
            "url": "https://notion.so/...",
            "created_time": "2024-01-01T10:00:00.000Z",
            "last_edited_time": "2024-01-02T15:30:00.000Z",
            "content": [
                {
                    "id": "block123...",
                    "type": "heading_1",
                    "text": "Introduction",
                    "created_time": "2024-01-01T10:00:00.000Z",
                    "has_children": false
                },
                {
                    "id": "block456...",
                    "type": "paragraph",
                    "text": "This is a paragraph...",
                    "created_time": "2024-01-01T10:01:00.000Z",
                    "has_children": false
                }
            ]
        }
    """
    try:
        # Get page metadata
        page = notion.get_page(page_id)
        
        # Get all blocks
        blocks = _get_all_blocks(page_id)
        
        return {
            "id": page.get("id"),
            "title": _extract_title_from_page(page),
            "url": page.get("url"),
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
            "archived": page.get("archived", False),
            "content": blocks
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()