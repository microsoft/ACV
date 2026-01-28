import threading
from typing import Any, Awaitable, Callable, List, Optional

from autogen_core import AgentId, DropMessage, InterventionHandler, MessageContext

from .types import (
    AGEPublishMessage,
    AGEResponseMessage,
    AGESendMessage,
    ScoreResult,
    TimeStampedMessage,
)


class _OverrideRule:
    def __init__(self, sender_type_prefix: str, new_text: str, remaining_messages: int = 2, source_prefix: str | None = None) -> None:
        self.sender_type_prefix = sender_type_prefix
        self.source_prefix = source_prefix
        self.new_text = new_text
        self.remaining_messages = remaining_messages

    def matches(self, sender: AgentId, message: Any) -> bool:
        try:
            if str(sender.type).startswith(self.sender_type_prefix):
                return True
        except Exception:
            pass
        # Fallback: inspect message source string
        try:
            if hasattr(message, "message") and hasattr(message.message, "source"):
                src = str(message.message.source)
                if self.source_prefix and src.startswith(self.source_prefix):
                    return True
            elif hasattr(message, "response") and hasattr(message.response, "chat_message") and hasattr(message.response.chat_message, "source"):
                src = str(message.response.chat_message.source)
                if self.source_prefix and src.startswith(self.source_prefix):
                    return True
        except Exception:
            pass
        return False


class Counter:
    def __init__(self) -> None:
        self._count: int = 0
        self.threadLock = threading.Lock()

    def increment(self) -> None:
        self.threadLock.acquire()
        self._count += 1
        self.threadLock.release()

    def get(self) -> int:
        return self._count

    def set(self, value: int) -> None:
        self.threadLock.acquire()
        self._count = value
        self.threadLock.release()

    def decrement(self) -> None:
        self.threadLock.acquire()
        self._count -= 1
        self.threadLock.release()


class AgDebuggerInterventionHandler(InterventionHandler):
    """Handles message dropping and state tracking for ag explore"""

    def __init__(
        self,
        checkpointFunc: Callable[[int], Awaitable[None]],
        history: List[TimeStampedMessage] | None = None,
    ) -> None:
        self.drop = False
        # When True, deliver messages normally but skip creating checkpoints/history entries
        self.suppress_checkpoint = False
        self.history: List[TimeStampedMessage] = [] if history is None else history
        self.timestamp_counter = Counter()
        self.checkpointFunc = checkpointFunc
        self._current_score: ScoreResult | None = None
        # Optional runtime override: replace next N messages from a given sender type with new text
        self._override_rule: Optional[_OverrideRule] = None

        if len(self.history) > 0:
            self.timestamp_counter.set(self.history[-1].timestamp + 1)

    def invalidate_cache(self) -> None:
        self._current_score = None

    def set_next_messages_override(self, sender_type_prefix: str, new_text: str, count: int = 2, source_prefix: str | None = None) -> None:
        """Override next N messages originating from agents whose type or source starts with the given prefix.
        This is used to force orchestrator follow-up messages to reflect an edited instruction
        without modifying the global task/facts/plan.
        """
        self._override_rule = _OverrideRule(sender_type_prefix, new_text, count, source_prefix)

    def _maybe_apply_override(self, message: Any, *, sender: AgentId) -> Any:
        rule = self._override_rule
        if rule is None:
            return message
        if not rule.matches(sender, message):
            return message
        # Only override textual messages
        try:
            # GroupChatMessage: has .message.content or .content in TextMessage
            if hasattr(message, "message") and hasattr(message.message, "content"):
                content = message.message.content
            elif hasattr(message, "response") and hasattr(message.response, "chat_message"):
                content = message.response.chat_message.content
            elif hasattr(message, "content"):
                content = message.content
            else:
                return message

            if isinstance(content, str):
                new_text = rule.new_text
                print(f"[INFO] Applying override: '{content[:50]}...' -> '{new_text[:50]}...'")
                # Apply override - replace the entire content with the new text
                if hasattr(message, "message") and hasattr(message.message, "content"):
                    message.message.content = new_text
                    print(f"[INFO] Override applied to message.message.content")
                elif hasattr(message, "response") and hasattr(message.response, "chat_message"):
                    message.response.chat_message.content = new_text
                    print(f"[INFO] Override applied to response.chat_message.content")
                elif hasattr(message, "content"):
                    message.content = new_text
                    print(f"[INFO] Override applied to message.content")
                # Decrement counter and clear if done
                rule.remaining_messages -= 1
                print(f"[INFO] Override rule remaining messages: {rule.remaining_messages}")
                if rule.remaining_messages <= 0:
                    self._override_rule = None
                    print(f"[INFO] Override rule exhausted, clearing")
            return message
        except Exception:
            return message

    def handle_history_add(self, message: AGEPublishMessage | AGESendMessage | AGEResponseMessage) -> None:
        curr_timestep = self.timestamp_counter.get()
        self.history.append(TimeStampedMessage(message=message, timestamp=curr_timestep))
        self.timestamp_counter.increment()

    async def on_send(
        self, message: Any, *, message_context: MessageContext, recipient: AgentId
    ) -> Any | type[DropMessage]:
        if self.drop:
            self.drop = False
            return DropMessage

        m = AGESendMessage(
            message=message,
            sender=message_context.sender,
            recipient=recipient,
            message_id=message_context.message_id,
        )
        self.invalidate_cache()
        await self.checkpointFunc(self.timestamp_counter.get())
        self.handle_history_add(m)
        return message

    async def on_publish(self, message: Any, *, message_context: MessageContext) -> Any | type[DropMessage]:
        if self.drop:
            self.drop = False
            return DropMessage

        # Apply override if configured (e.g., to force new instruction text)
        message = self._maybe_apply_override(message, sender=message_context.sender)

        m = AGEPublishMessage(
            message=message,
            sender=message_context.sender,
            topic_id=message_context.topic_id,  # type: ignore -- topic id guaranteed non-null for publish
            message_id=message_context.message_id,
        )
        self.invalidate_cache()
        if not self.suppress_checkpoint:
            await self.checkpointFunc(self.timestamp_counter.get())
            self.handle_history_add(m)
        return message

    async def on_response(self, message: Any, *, sender: AgentId, recipient: AgentId | None) -> Any | type[DropMessage]:
        if self.drop:
            self.drop = False
            return DropMessage

        # Apply override if configured (covers orchestrator GroupChatAgentResponse pathways)
        message = self._maybe_apply_override(message, sender=sender)

        m = AGEResponseMessage(
            message=message,
            sender=sender,
            recipient=recipient,
        )
        self.invalidate_cache()
        if not self.suppress_checkpoint:
            await self.checkpointFunc(self.timestamp_counter.get())
            self.handle_history_add(m)
        return message

    def get_message_at_timestamp(self, timestamp: int) -> TimeStampedMessage | None:
        return next((m for m in self.history if m.timestamp == timestamp), None)

    def purge_history_after_cutoff(self, cutoff: int) -> None:
        """
        Remove messages from history after cutoff timestamp.
        """
        self.history = [m for m in self.history if m.timestamp < cutoff]
        self.invalidate_cache()
