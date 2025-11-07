#!/usr/bin/env python3

import os
import sys
import glob
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

class NotionAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION
        }
    
    def clear_all_children(self, parent_id):
        print(f"Getting all child blocks from parent: {parent_id}")
        
        child_blocks = self.get_all_child_blocks(parent_id)
        
        if not child_blocks:
            print("No child blocks found.")
            return
        
        print(f"Found {len(child_blocks)} child blocks to delete")
        
        for block in child_blocks:
            block_id = block.get("id")
            block_type = block.get("type")
            
            try:
                if block_type == "child_page":
                    print(f"Archiving child page: {block_id}")
                    self.archive_page(block_id)
                else:
                    print(f"Deleting {block_type} block: {block_id}")
                    self.delete_block(block_id)
            except Exception as e:
                print(f"Error processing block {block_id}: {e}")
        
        print("All child blocks cleared successfully")
    
    def get_all_child_blocks(self, parent_id):
        all_blocks = []
        next_cursor = None
        
        while True:
            response = self.get_child_blocks(parent_id, next_cursor)
            all_blocks.extend(response.get("results", []))
            
            next_cursor = response.get("next_cursor")
            if not response.get("has_more", False) or not next_cursor:
                break
        
        return all_blocks
    
    def get_child_blocks(self, block_id, next_cursor=None):
        url = f"{NOTION_API_URL}/blocks/{block_id}/children"
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get child blocks: {response.status_code} - {response.text}")
    
    def archive_page(self, page_id):
        url = f"{NOTION_API_URL}/pages/{page_id}"
        data = {"archived": True}
        
        response = requests.patch(url, headers=self.headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to archive page: {response.status_code} - {response.text}")
    
    def delete_block(self, block_id):
        url = f"{NOTION_API_URL}/blocks/{block_id}"
        
        response = requests.delete(url, headers=self.headers)
        if response.status_code == 200:
            return True
        else:
            raise Exception(f"Failed to delete block: {response.status_code} - {response.text}")
    
    def create_page(self, parent_id, title, content_blocks):
        url = f"{NOTION_API_URL}/pages"
        
        parent_data = {}
        if parent_id.startswith('database:'):
            parent_data["database_id"] = parent_id.replace('database:', '')
        else:
            parent_data["page_id"] = parent_id
        
        data = {
            "parent": parent_data,
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            },
            "children": content_blocks
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to create page: {response.status_code} - {response.text}")

def parse_markdown_to_blocks(markdown_content):
    blocks = []
    lines = markdown_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        if line.startswith('```'):
            language = line[3:].strip() or "plain text"
            code_lines = []
            i += 1
            
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            if code_lines:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": '\n'.join(code_lines)}
                        }],
                        "language": language
                    }
                })
            i += 1
            continue
        
        if line.startswith('#'):
            level = 1
            while level < len(line) and line[level] == '#':
                level += 1
            
            text = line[level:].strip()
            level = min(level, 3)
            
            heading_type = f"heading_{level}"
            blocks.append({
                "object": "block",
                "type": heading_type,
                heading_type: {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": text}
                    }]
                }
            })
            i += 1
            continue
        
        if line in ['---', '***', '___']:
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {}
            })
            i += 1
            continue
        
        if line.startswith('- ') or line.startswith('* '):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": line[2:].strip()}
                    }]
                }
            })
            i += 1
            continue
        
        if line[0].isdigit() and line[1:3] == '. ':
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": line[line.index('.') + 1:].strip()}
                    }]
                }
            })
            i += 1
            continue
        
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": line}
                }]
            }
        })
        i += 1
    
    return blocks

def extract_title_from_markdown(markdown_content):
    lines = markdown_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    
    return None

def load_and_upload_markdown_files(directory):
    api_key = os.getenv('NOTION_API_KEY')
    parent_id = os.getenv('NOTION_PARENT_ID')
    
    if not api_key:
        print("Error: NOTION_API_KEY not found in .env file")
        sys.exit(1)
    
    if not parent_id:
        print("Error: NOTION_PARENT_ID not found in .env file")
        sys.exit(1)
    
    notion = NotionAPI(api_key)
    
    print("Clearing existing content...")
    notion.clear_all_children(parent_id)
    print()
    
    md_files = glob.glob(os.path.join(directory, '*.md'))
    
    if not md_files:
        print(f"No .md files found in {directory}")
        return
    
    print(f"Found {len(md_files)} .md files to upload")
    successful = 0
    failed = 0
    
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            title = extract_title_from_markdown(content)
            
            if not title:
                filename = os.path.basename(md_file)
                title = os.path.splitext(filename)[0]
                print(f"Warning: No heading found in {filename}, using filename as title")
            
            blocks = parse_markdown_to_blocks(content)
            
            new_page = notion.create_page(parent_id, title, blocks)
            print(f"Successfully uploaded: {os.path.basename(md_file)} with title '{title}' (ID: {new_page['id']})")
            successful += 1
            
        except Exception as e:
            print(f"Error uploading {os.path.basename(md_file)}: {e}")
            failed += 1
    
    print(f"\nUpload complete:")
    print(f"Successfully uploaded: {successful}")
    print(f"Failed to upload: {failed}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python add_markdown_to_notion.py <item_id>")
        sys.exit(1)
    
    try:
        item_id = int(sys.argv[1])
    except ValueError:
        print("Error: Item ID must be an integer")
        sys.exit(1)
    
    directory = f'data/converted/item{item_id}'
    
    print(f"Processing item {item_id}")
    print(f"Directory: {directory}")
    
    if not os.path.exists(directory):
        print(f"Error: Directory {directory} does not exist")
        sys.exit(1)
    
    load_and_upload_markdown_files(directory)

if __name__ == '__main__':
    main()