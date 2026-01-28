import json
import re

from dataclasses import dataclass
from typing import Dict, List
import traceback

from autogen_agentchat.messages import (
    AgentEvent,
    ChatMessage,
    HandoffMessage,
    MemoryQueryEvent,
    MultiModalMessage,
    StopMessage,
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ToolCallSummaryMessage,
    UserInputRequestedEvent,
)
from autogen_agentchat.teams._group_chat._events import (
    GroupChatAgentResponse,
    GroupChatMessage,
    GroupChatRequestPublish,
    GroupChatReset,
    GroupChatStart,
    GroupChatTermination,
)
from autogen_core.models import (
    AssistantMessage,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    SystemMessage,
    UserMessage,
)


@dataclass
class FieldInfo:
    name: str
    type: str
    required: bool


@dataclass
class MessageTypeDescription:
    name: str
    fields: List[FieldInfo] | None = None


def get_message_type_descriptions() -> Dict[str, MessageTypeDescription]:
    """
    Gets the message type descriptions for user-sendable messages for agentchat:
    - TextMessage, MultiModalMessage, StopMessage, HandoffMessage
    """

    return {
        # "TextMessage": MessageTypeDescription(
        #     name="TextMessage",
        #     fields=[
        #         FieldInfo(name="source", type="str", required=True),
        #         FieldInfo(name="content", type="str", required=True),
        #         FieldInfo(name="type", type="str", required=True),
        #     ],
        # ),
        # "MultiModalMessage": MessageTypeDescription(
        #     name="MultiModalMessage",
        #     fields=[
        #         FieldInfo(name="source", type="str", required=True),
        #         FieldInfo(name="content", type="List[str]", required=True),
        #         FieldInfo(name="type", type="str", required=True),
        #     ],
        # ),
        # "StopMessage": MessageTypeDescription(
        #     name="StopMessage",
        #     fields=[
        #         FieldInfo(name="source", type="str", required=True),
        #         FieldInfo(name="content", type="str", required=True),
        #         FieldInfo(name="type", type="str", required=True),
        #     ],
        # ),
        # "HandoffMessage": MessageTypeDescription(
        #     name="HandoffMessage",
        #     fields=[
        #         FieldInfo(name="source", type="str", required=True),
        #         FieldInfo(name="content", type="str", required=True),
        #         FieldInfo(name="target", type="str", required=True),
        #         FieldInfo(name="context", type="List[LLMMessage]", required=False),
        #         FieldInfo(name="type", type="str", required=True),
        #     ],
        # ),
        "GroupChatStart": MessageTypeDescription(
            name="GroupChatStart",
            fields=[
                FieldInfo(name="messages", type="List[ChatMessage]", required=False),
            ],
        ),
        "GroupChatAgentResponse": MessageTypeDescription(
            name="GroupChatAgentResponse",
            fields=[
                FieldInfo(name="agent_response", type="Response", required=True),
            ],
        ),
        "GroupChatRequestPublish": MessageTypeDescription(
            name="GroupChatRequestPublish",
            fields=None,
        ),
        "GroupChatMessage": MessageTypeDescription(
            name="GroupChatMessage",
            fields=[
                FieldInfo(name="message", type="ChatMessage", required=True),
            ],
        ),
        "GroupChatTermination": MessageTypeDescription(
            name="GroupChatTermination",
            fields=[
                FieldInfo(name="message", type="StopMessage", required=True),
            ],
        ),
        "GroupChatReset": MessageTypeDescription(
            name="GroupChatReset",
            fields=None,
        ),
    }


# ### Serialization ### -- maybe should be a class?

__message_map = {
    # agentchat messages
    "TextMessage": TextMessage,
    "MultiModalMessage": MultiModalMessage,
    "StopMessage": StopMessage,
    "HandoffMessage": HandoffMessage,
    # agentchat events
    "ToolCallRequestEvent": ToolCallRequestEvent,
    "ToolCallExecutionEvent": ToolCallExecutionEvent,
    "ToolCallSummaryMessage": ToolCallSummaryMessage,
    "UserInputRequestedEvent": UserInputRequestedEvent,
    "MemoryQueryEvent": MemoryQueryEvent,
    # group chat messages
    "GroupChatAgentResponse": GroupChatAgentResponse,
    "GroupChatMessage": GroupChatMessage,
    "GroupChatRequestPublish": GroupChatRequestPublish,
    "GroupChatReset": GroupChatReset,
    "GroupChatStart": GroupChatStart,
    "GroupChatTermination": GroupChatTermination,
    # core messages
    "AssistantMessage": AssistantMessage,
    "FunctionExecutionResult": FunctionExecutionResult,
    "FunctionExecutionResultMessage": FunctionExecutionResultMessage,
    "SystemMessage": SystemMessage,
    "UserMessage": UserMessage,
}

import datetime
from typing import Any
from pydantic import BaseModel

UNSERIALIZABLE_TYPE_NAMES = {
    "ImagingCore",
    "Image",
    "ImageFile",
    "ImageDraw",
    "ImageFont",
    "module",
    "function",
    "builtin_function_or_method",
    "method",
    "TextIOWrapper",  # file objects
}


def is_unserializable(obj: Any) -> bool:
    """Return True if the object is of a known unserializable type."""
    cls_name = obj.__class__.__name__
    return cls_name in UNSERIALIZABLE_TYPE_NAMES


def deep_serialize(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return {k: deep_serialize(v) for k, v in obj.__dict__.items()}

    elif isinstance(obj, list):
        return [deep_serialize(item) for item in obj]

    elif isinstance(obj, dict):
        return {k: deep_serialize(v) for k, v in obj.items()}

    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()

    elif is_unserializable(obj):
        return f"[Unserializable: {obj.__class__.__name__}]"

    elif hasattr(obj, '__dict__'):
        return {k: deep_serialize(v) for k, v in vars(obj).items()}

    else:
        return obj



def serialize(message: ChatMessage | AgentEvent | LLMMessage | None) -> dict:
    try:
        if message is None:
            return {"type": "None"}

        type_name = type(message).__name__

        # print(f"[DEBUG `serialize`] message before serializing = {message}")

        # Try to serialize using model_dump()
        # serialized_message = message.model_dump()

        serialized_message = deep_serialize(message)

        # Always ensure type field is present
        serialized_message["type"] = type_name

        # print(f"[DEBUG `serialize`] serialized_message = {serialized_message}")

        return serialized_message

    except Exception as e:
        print(f"[WARN] Unable to serialize message: {message}, Error: {e}")
        return {"type": type(message).__name__ if message else "unknown", "error": "serialization_failed"}


def deserialize(
    message_dict: Dict | str,
) -> ChatMessage | AgentEvent | LLMMessage | None:
    try:
        if isinstance(message_dict, str):
            message_dict = json.loads(message_dict)

        # Tolerant fix: if a MultiModalMessage was edited into a single string, coerce to list[str]
        def _coerce_multimodal_content_if_needed(d: Dict) -> Dict:
            try:
                if isinstance(d, dict) and d.get("type") == "MultiModalMessage":
                    content = d.get("content")
                    if isinstance(content, str):
                        print("[DEBUG][deserialize] Coercing MultiModalMessage.content from str to list[str]...")
                        parts = [s.strip() for s in re.split(r"\n+", content) if s and s.strip()]
                        if len(parts) <= 1:
                            parts = [s.strip() for s in content.split(",") if s and s.strip()]
                        if not parts:
                            parts = [content.strip()]
                        d = {**d, "content": parts}
                        print(f"[DEBUG][deserialize] Coerced content -> {parts[:2]}{'...' if len(parts)>2 else ''}")
                return d
            except Exception as e:
                print(f"[DEBUG][deserialize] Coerce MultiModalMessage failed: {e}")
                return d

        message_dict = _coerce_multimodal_content_if_needed(message_dict)

        message_type = message_dict["type"]  # type: ignore

        if message_type == "None":
            return None

        # Special handling for GroupChatStart with nested messages
        if message_type == "GroupChatStart" and "messages" in message_dict:
            # Recursively deserialize nested messages
            if message_dict["messages"] is not None:
                deserialized_messages = []
                for msg in message_dict["messages"]:
                    if isinstance(msg, dict) and "type" in msg:
                        # Recursively deserialize each message
                        deserialized_msg = deserialize(msg)
                        if deserialized_msg is not None:
                            deserialized_messages.append(deserialized_msg)
                    else:
                        # Already deserialized message
                        deserialized_messages.append(msg)

                # Create a new dict with deserialized messages
                new_dict = message_dict.copy()
                new_dict["messages"] = deserialized_messages
                new_message_class = __message_map[message_type]
                new_message = new_message_class(**new_dict)
        # Special handling for GroupChatAgentResponse with nested Response
        elif message_type == "GroupChatAgentResponse" and "response" in message_dict:
            from autogen_agentchat.base import Response

            response_dict = message_dict["response"]
            if "chat_message" in response_dict and isinstance(response_dict["chat_message"], dict):
                # Deserialize the nested chat_message (tolerate bad MultiModal content)
                cm_dict = _coerce_multimodal_content_if_needed(response_dict["chat_message"])  # type: ignore
                chat_message = deserialize(cm_dict)
                if chat_message is not None:
                    response = Response(chat_message=chat_message, inner_messages=response_dict.get("inner_messages"))
                    new_message_class = __message_map[message_type]
                    new_message = new_message_class(response=response, name=message_dict["name"])
                else:
                    return None
            else:
                new_message_class = __message_map[message_type]
                new_message = new_message_class(**message_dict)
        # Special handling for GroupChatMessage with nested message
        elif message_type == "GroupChatMessage" and "message" in message_dict:
            message_data = message_dict["message"]
            if isinstance(message_data, dict) and "type" in message_data:
                # Deserialize the nested message
                nested_message = deserialize(message_data)
                if nested_message is not None:
                    new_message_class = __message_map[message_type]
                    new_message = new_message_class(message=nested_message)
                else:
                    return None
            else:
                new_message_class = __message_map[message_type]
                new_message = new_message_class(**message_dict)
        else:
            new_message_class = __message_map[message_type]
            new_message = new_message_class(**message_dict)

        # print(f"[DEBUG `deserialize`] new_message after deserializing = {new_message}")

        return new_message
    except Exception as e:
        print(
            f"[WARN] Unable to deserialize message dict into Pydantic class. Error: {str(e)}.\nMessage dict: ",
            message_dict,
        )
        return None