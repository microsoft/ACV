import asyncio
import logging
from typing import Any, Dict, List

from autogen_agentchat.teams import BaseGroupChat
from autogen_agentchat.messages import TextMessage  # for generic message edits
from autogen_agentchat.teams._group_chat._events import (
    GroupChatAgentResponse,
    GroupChatStart,
)
from autogen_core import AgentId, DefaultTopicId, SingleThreadedAgentRuntime, TopicId
from autogen_core._queue import Queue
from autogen_core._single_threaded_agent_runtime import (
    PublishMessageEnvelope,
    ResponseMessageEnvelope,
    RunContext,
    SendMessageEnvelope,
)

from .intervention import AgDebuggerInterventionHandler
from .log import ListHandler  # , LogToHistoryHandler
from .serialization import get_message_type_descriptions
from .types import (
    AgentInfo,
    AGEPublishMessage,
    AGESendMessage,
    MessageHistorySession,
    ScoreResult,
)
from .utils import message_to_json


async def wait_for_future(fut):  # type: ignore
    await fut


class BackendRuntimeManager:
    def __init__(
        self,
        groupchat: BaseGroupChat,
        logger: logging.Logger,
        message_history=None,
        state_cache=None,
        saved_team_id=None,  # 新增：保存的team_id，用于恢复一致性
    ):
        self._groupchat = groupchat
        self._saved_team_id = saved_team_id  # 新增：存储要恢复的team_id
        self.message_info = get_message_type_descriptions()
        self.prior_histories: Dict[int, MessageHistorySession] = {}
        self.session_counter = 0
        self.current_session_reset_from: int | None = None
        self.display_session_id: int | None = None  # 新增：用于UI显示的session ID
        self.agent_checkpoints = {} if state_cache is None else state_cache
        self.run_context: RunContext | None = None
        self.intervention_handler = AgDebuggerInterventionHandler(self.checkpoint_agents, message_history)
        self.all_topics: List[str] = []
        self.log_handler = ListHandler()
        logger.addHandler(self.log_handler)
        self.ready = False

        print("Initial Backend loaded.")

    async def async_initialize(self) -> None:
        # 如果有保存的team_id，强制恢复team_id一致性
        if self._saved_team_id:
            print(f"[INFO] Restoring team_id consistency: {self._saved_team_id}")
            self._restore_team_id_consistency(self._saved_team_id)

        if not self.groupchat._initialized:
            await self.groupchat._init(self.runtime)

        # manually add all topics from the chat
        self.all_topics = [
            self.groupchat._group_topic_type,
            self.groupchat._output_topic_type,
            self.groupchat._group_chat_manager_topic_type,
            *self.groupchat._participant_topic_types,
        ]

        # add intervention handler since runtime already initialized
        if self.runtime._intervention_handlers is None:
            self.runtime._intervention_handlers = []
        self.runtime._intervention_handlers.append(self.intervention_handler)

        # load the last checkpoint - N.B. might be earlier than last message so we get the max key
        if len(self.intervention_handler.history) > 0:
            last_checkpoint_time = max(self.agent_checkpoints.keys())
            print("resetting to checkpoint: ", last_checkpoint_time)
            checkpoint = self.agent_checkpoints.get(last_checkpoint_time)
            if checkpoint is not None:
                await self.runtime.load_state(checkpoint)

        self.ready = True
        print("Finished backend async load")

    def _restore_team_id_consistency(self, saved_team_id: str) -> None:
        """
        恢复team_id一致性：强制设置groupchat的team_id为保存的值，
        并重新构造所有基于team_id的topic类型，确保Agent ID匹配
        """
        print(f"[DEBUG] Original team_id: {self._groupchat._team_id}")
        print(f"[DEBUG] Restoring to team_id: {saved_team_id}")

        # 强制覆盖team_id
        self._groupchat._team_id = saved_team_id

        # 重新构造所有基于team_id的topic类型，确保与历史消息中的Agent ID一致
        self._groupchat._group_topic_type = f"group_topic_{saved_team_id}"
        self._groupchat._group_chat_manager_topic_type = f"{self._groupchat._group_chat_manager_name}_{saved_team_id}"
        self._groupchat._participant_topic_types = [
            f"{participant.name}_{saved_team_id}" for participant in self._groupchat._participants
        ]
        self._groupchat._output_topic_type = f"output_topic_{saved_team_id}"

        print(f"[DEBUG] Restored team_id consistency. New topics: {self._groupchat._participant_topic_types}")

    @property
    def groupchat(self) -> BaseGroupChat:
        return self._groupchat

    @property
    def runtime(self) -> SingleThreadedAgentRuntime:
        return self.groupchat._runtime

    @property
    def agent_key(self) -> str:
        return self.groupchat._team_id

    @property
    def current_score(self) -> ScoreResult | None:
        return self.intervention_handler._current_score

    @property
    def agent_names(self) -> List[str]:
        return list(self.runtime._known_agent_names)

    @property
    def message_queue_list(self) -> List[PublishMessageEnvelope | SendMessageEnvelope | ResponseMessageEnvelope]:
        # read and serialize without having to reconstruct a new Queue each time
        return list(self.runtime._message_queue._queue)  # type: ignore

    @property
    def unprocessed_messages_count(self):
        return self.runtime.unprocessed_messages_count

    @property
    def is_processing(self) -> bool:
        return self.runtime._run_context is not None

    def start_processing(self) -> None:
        self.runtime.start()

    async def process_next(self):
        await self.runtime.process_next()

    async def stop_processing(self) -> None:
        await self.runtime.stop_when_idle()
        # OR maybe below to stop immediatley
        # await self.runtime.stop()

    async def checkpoint_agents(self, timestamp: int) -> None:
        checkpoint = await self.runtime.save_state()
        self.agent_checkpoints[timestamp] = checkpoint

    def save_state_with_team_id(self) -> dict:
        """
        保存包含team_id的完整状态，确保后续恢复时能保持team_id一致性
        返回格式：{"team_id": str, "state": dict}
        """
        return {
            "team_id": self.groupchat._team_id,
            "state": self.agent_checkpoints
        }

    def get_current_history(self):
        return [message_to_json(m.message, m.timestamp) for m in self.intervention_handler.history]

    def save_history_session_from_reset(self, new_reset_from: int) -> None:
        self.prior_histories[self.session_counter] = MessageHistorySession(
            messages=self.get_current_history(),
            current_session_reset_from=self.current_session_reset_from,
            next_session_starts_at=None,
            current_session_score=self.current_score,
        )

        self.session_counter += 1
        self.current_session_reset_from = new_reset_from

    def read_current_session_history(self):
        saved_sessions = self.prior_histories.copy()

        # save current messages
        saved_sessions[self.session_counter] = MessageHistorySession(
            messages=self.get_current_history(),
            current_session_reset_from=self.current_session_reset_from,
            next_session_starts_at=None,
            current_session_score=self.current_score,
        )
        return saved_sessions

    async def get_agent_config(self, agent_name) -> AgentInfo:
        agent_id = await self.runtime.get(agent_name, key=self.agent_key)

        if agent_id in self.runtime._instantiated_agents:
            agent_state = await self.runtime.agent_save_state(agent_id)
        else:
            agent_state = "Agent not instantiated yet!"

        return AgentInfo(config={}, state=agent_state)

    def publish_message(self, new_message: Any, topic: str | TopicId):
        """
        PUBLISH new message to the runtime.
        """
        if isinstance(topic, str):
            topic = DefaultTopicId(topic)

        asyncio.create_task(wait_for_future(self.runtime.publish_message(new_message, topic)))

    async def publish_message_sync(self, new_message: Any, topic: str | TopicId):
        """
        PUBLISH new message to the runtime synchronously.
        Used for edit_and_revert to ensure proper message handling.
        """
        if isinstance(topic, str):
            topic = DefaultTopicId(topic)

        await self.runtime.publish_message(new_message, topic)

    async def publish_message_async(self, new_message: Any, topic: str | TopicId):
        """
        PUBLISH new message to the runtime (async version for edit_and_revert).
        """
        if isinstance(topic, str):
            topic = DefaultTopicId(topic)

        await self.runtime.publish_message(new_message, topic)

    async def send_message(self, new_message: Any, recipient: str | AgentId, sender=None):
        """
        SEND new message to the runtime.
        """
        agent_id = await self.runtime.get(recipient, key=self.agent_key)
        return asyncio.create_task(wait_for_future(self.runtime.send_message(new_message, agent_id, sender=sender)))

    async def edit_message_queue(self, new_message: Any, edit_idx: int):
        """
        Edit existing message in the runtime queue.
        """
        if edit_idx >= self.runtime._message_queue.qsize():
            raise IndexError(f"Index out of range in queue {edit_idx}")

        # #1 simple way -- directly edit queue array
        # backend.runtime._message_queue._queue[editMessage.idx].message = newMessage

        # #2 more robust -- make new queue
        current_queue = []
        while not self.runtime._message_queue.empty():
            current_queue.append(self.runtime._message_queue.get_nowait())

        current_queue[edit_idx].message = new_message

        newQueue = Queue()
        for item in current_queue:
            await newQueue.put(item)
        self.runtime._message_queue = newQueue

    async def edit_and_revert_message(self, new_message: Any | None, cutoff_timestamp: int):
        # Stop processing if running (but don't auto-restart for manual control)
        if self.is_processing:
            await self.stop_processing()

        current_message = self.intervention_handler.get_message_at_timestamp(cutoff_timestamp)
        if current_message is None:
            raise ValueError(f"Unable to find message in history with timestamp {cutoff_timestamp}")

        # Save a snapshot of the session prior to reset and trim history
        self.save_history_session_from_reset(cutoff_timestamp)
        self.intervention_handler.purge_history_after_cutoff(cutoff_timestamp)

        # Determine edited content
        if new_message is None:
            new_message = current_message.message.message

        # Load the agent state checkpoint BEFORE re-sending so state matches history
        checkpoint = self.agent_checkpoints.get(cutoff_timestamp, None)
        if checkpoint is not None:
            await self.runtime.load_state(checkpoint)
        else:
            print("[WARN] Was unable to find agent state checkpoint for time ", cutoff_timestamp)

        # Update orchestrator's internal state IMMEDIATELY after loading checkpoint
        # This ensures the orchestrator has the correct state before any message processing
        orchestrator_updated = await self._update_orchestrator_internal_state(current_message.message.message, new_message)

        # If this is an edit to a participant agent's response (e.g., WebSurfer), reflect it in
        # the orchestrator's message thread so inner loop reasons over the edited content.
        participant_response_updated = False
        if not orchestrator_updated:
            try:
                src_name = None
                if hasattr(new_message, 'response') and hasattr(new_message.response, 'chat_message'):
                    src_name = getattr(new_message.response.chat_message, 'source', None)
                # Only sync participant responses; skip orchestrator messages here
                if src_name and 'Orchestrator' in str(src_name):
                    participant_response_updated = False
                else:
                    participant_response_updated = self._update_participant_response_in_orchestrator_thread(
                        current_message.message.message, new_message
                    )
                    if participant_response_updated:
                        print("[DEBUG][inject] Participant response synced into orchestrator thread.")
            except Exception as e:
                print(f"[DEBUG][inject] Participant response sync failed: {e}")
                participant_response_updated = False

        # Only set override for short instruction edits coming from orchestrator (not ledger/participant edits)
        if not orchestrator_updated and not participant_response_updated:
            try:
                edited_text = self._extract_message_content(new_message)
                # Be permissive: detect source from any supported message shape
                src_name = self._get_message_source_any(new_message) or self._get_message_source_any(current_message.message.message)
                if isinstance(edited_text, str) and edited_text and src_name and ('Orchestrator' in str(src_name)):
                    self.intervention_handler.set_next_messages_override(
                        sender_type_prefix=str(self.groupchat._group_chat_manager_name),
                        new_text=edited_text,
                        count=3,
                        source_prefix="MagenticOneOrchestrator",
                    )
            except Exception:
                pass

        # Clear message queue AFTER loading checkpoint to avoid interfering with state restoration
        self.runtime._message_queue = Queue()

        # Temporarily disable intervention handler history/checkpoint, but do not Drop the message
        original_drop = self.intervention_handler.drop
        self.intervention_handler.drop = False
        self.intervention_handler.suppress_checkpoint = True

        try:

            # Re-inject the (edited) message to continue from the cutoff
            # Use async methods to ensure proper timing and event handling
            if isinstance(current_message.message, AGEPublishMessage):
                await self.publish_message_sync(new_message, current_message.message.topic_id)
            elif isinstance(current_message.message, AGESendMessage):
                await self.send_message(
                    new_message, current_message.message.recipient, sender=current_message.message.sender
                )
            else:
                raise ValueError(
                    f"Failed to re-send message after history reset. Unsure how to handle message of type: {current_message.message}"
                )
        finally:
            # Restore intervention handler state
            self.intervention_handler.drop = original_drop
            if hasattr(self.intervention_handler, 'suppress_checkpoint'):
                self.intervention_handler.suppress_checkpoint = False

    def _update_participant_response_in_orchestrator_thread(self, original_message, edited_message) -> bool:
        """If the user edited a participant agent's GroupChatAgentResponse (e.g., WebSurfer),
        reflect that edit inside the orchestrator's _message_thread so the inner loop reasons over
        the cleaned/modified content instead of the original.

        Returns True if an in-thread replacement was applied.
        """
        try:
            # Identify agent name and text content
            def _get_source_and_content(msg: Any) -> tuple[str | None, Any | None]:
                try:
                    if hasattr(msg, 'response') and hasattr(msg.response, 'chat_message'):
                        cm = msg.response.chat_message
                        return (getattr(cm, 'source', None), getattr(cm, 'content', None))
                    if hasattr(msg, 'message') and hasattr(msg.message, 'source'):
                        return (getattr(msg.message, 'source', None), getattr(msg.message, 'content', None))
                    if hasattr(msg, 'source'):
                        return (getattr(msg, 'source'), getattr(msg, 'content', None))
                except Exception:
                    return (None, None)
                return (None, None)

            src_orig, content_orig = _get_source_and_content(original_message)
            src_edit, content_edit = _get_source_and_content(edited_message)
            if not (src_orig or src_edit):
                return False
            # If no actual change, nothing to do
            if content_orig == content_edit:
                return False

            # Locate orchestrator agent instance
            orchestrator = None
            for agent_id, agent in self.runtime._instantiated_agents.items():
                if hasattr(agent, '_message_thread') and hasattr(agent, '_name') and 'Orchestrator' in str(type(agent).__name__):
                    orchestrator = agent
                    break
            if orchestrator is None:
                return False

            # Replace the last message in the thread with matching source and content
            thread = getattr(orchestrator, '_message_thread', None)
            if not isinstance(thread, list):
                return False

            replaced = False
            for i in range(len(thread) - 1, -1, -1):
                msg = thread[i]
                try:
                    if getattr(msg, 'source', None) in [src_orig, src_edit]:
                        if hasattr(msg, 'content'):
                            msg.content = content_edit
                            replaced = True
                            break
                except Exception:
                    continue

            return replaced
        except Exception:
            return False

        # Do NOT auto-restart processing - user will manually Start/Step

    async def _update_orchestrator_internal_state(self, original_message, edited_message) -> bool:
        """Synchronize the orchestrator's internal state with an edited message.

        Returns True iff the edit looks like a Task Full Ledger edit (so future decisions should be driven by
        the updated _task/_facts/_plan and updated thread), and False for short instruction edits that should
        be reinforced via the override mechanism.
        """
        try:
            if not hasattr(self.groupchat, '_group_chat_manager_name'):
                return False

            # Determine if the original/edited message belongs to the orchestrator
            def _get_source_name(msg: Any) -> str | None:
                try:
                    if hasattr(msg, 'response') and hasattr(msg.response, 'chat_message') and hasattr(msg.response.chat_message, 'source'):
                        return str(msg.response.chat_message.source)
                    if hasattr(msg, 'name'):
                        return str(msg.name)
                    if hasattr(msg, 'message') and hasattr(msg.message, 'source'):
                        return str(msg.message.source)
                    if hasattr(msg, 'source'):
                        return str(msg.source)
                except Exception:
                    return None
                return None

            src_original = _get_source_name(original_message)
            src_edited = _get_source_name(edited_message)
            if not ((src_original and 'Orchestrator' in src_original) or (src_edited and 'Orchestrator' in src_edited)):
                return False

            original_content = self._extract_message_content(original_message)
            edited_content = self._extract_message_content(edited_message)
            if not (original_content and edited_content and original_content != edited_content):
                return False

            # Detect a Task Full Ledger edit in a task-agnostic way (by section markers)
            low = edited_content.lower()
            is_full_ledger = (
                ('we are working to address the following user request:' in low)
                or ('here is an initial fact sheet' in low)
                or ('here is the plan' in low)
            )

            # Locate orchestrator instance
            orchestrator = None
            orchestrator_agent_id = f"{self.groupchat._group_chat_manager_name}_{self.groupchat._team_id}"
            for agent_id, agent in self.runtime._instantiated_agents.items():
                if agent_id.key == orchestrator_agent_id:
                    orchestrator = agent
                    break
            if orchestrator is None:
                for agent_id, agent in self.runtime._instantiated_agents.items():
                    if 'Orchestrator' in agent_id.key or 'orchestrator' in agent_id.key:
                        orchestrator = agent
                        break
            if orchestrator is None:
                for agent_id, agent in self.runtime._instantiated_agents.items():
                    if hasattr(agent, '_message_thread') and hasattr(agent, '_name') and 'Orchestrator' in str(type(agent).__name__):
                        orchestrator = agent
                        break
            if orchestrator is None:
                return False

            # Update orchestrator's message thread to reflect the edited content and truncate after the edit point
            try:
                if hasattr(orchestrator, '_message_thread'):
                    thread = orchestrator._message_thread

                    # Find and replace the orchestrator's own message that contains the original content
                    updated = False
                    updated_index = None
                    for i in range(len(thread) - 1, -1, -1):
                        msg = thread[i]
                        if hasattr(msg, 'source') and hasattr(msg, 'content') and msg.source == orchestrator._name:
                            if isinstance(msg.content, str) and original_content.strip() in msg.content:
                                thread[i] = TextMessage(
                                    content=edited_content,
                                    source=msg.source,
                                    id=getattr(msg, 'id', None),
                                    metadata=getattr(msg, 'metadata', {}),
                                    created_at=getattr(msg, 'created_at', None),
                                )
                                updated = True
                                updated_index = i
                                break

                    if updated and updated_index is not None and len(thread) > (updated_index + 1):
                        orchestrator._message_thread = thread[: updated_index + 1]
                    elif not updated:
                        # No exact match found
                        if is_full_ledger:
                            # Replace thread with the edited ledger so the inner loop restarts from it
                            orchestrator._message_thread = [TextMessage(content=edited_content, source=orchestrator._name)]
                        else:
                            # Append edited content as a new message from orchestrator
                            orchestrator._message_thread.append(TextMessage(content=edited_content, source=orchestrator._name))

                    # Align internal fields if this was a full ledger edit
                    if is_full_ledger:
                        try:
                            p_task, p_facts, p_plan = self._parse_task_facts_plan_from_full_ledger(edited_content)
                            if p_facts:
                                setattr(orchestrator, '_facts', p_facts)
                                try:
                                    print(f"[DEBUG][ledger-sync] Updated _facts (first 200 chars): {p_facts[:200]}")
                                except Exception:
                                    pass
                            if p_plan:
                                setattr(orchestrator, '_plan', p_plan)
                                try:
                                    print(f"[DEBUG][ledger-sync] Updated _plan (first 200 chars): {p_plan[:200]}")
                                except Exception:
                                    pass
                            # Only replace _task when explicitly provided in the edited ledger
                            if p_task and p_task.strip():
                                setattr(orchestrator, '_task', p_task)
                                try:
                                    print(f"[DEBUG][ledger-sync] Updated _task (first 200 chars): {p_task[:200]}")
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    return is_full_ledger

            except Exception:
                return is_full_ledger

        except Exception:
            return False


    def _parse_task_facts_plan_from_full_ledger(self, text: str) -> tuple[str | None, str | None, str | None]:
        """Best-effort parse of the MagenticOne full ledger text to extract task, facts, plan.
        We rely on the headings baked into ORCHESTRATOR_TASK_LEDGER_FULL_PROMPT.
        Returns a tuple (task, facts, plan) where each element may be None if not found.
        """
        if not isinstance(text, str):
            return (None, None, None)

        def _between(s: str, start: str, end: str | None) -> str | None:
            try:
                i = s.find(start)
                if i == -1:
                    return None
                i += len(start)
                if end is None:
                    return s[i:].strip() or None
                j = s.find(end, i)
                if j == -1:
                    return s[i:].strip() or None
                return s[i:j].strip() or None
            except Exception:
                return None

        # Markers from the prompt
        m_task = "We are working to address the following user request:"
        m_team = "To answer this request we have assembled the following team:"
        m_facts = "Here is an initial fact sheet to consider:"
        m_plan = "Here is the plan to follow as best as possible:"

        # Extract sections allowing for extra blank lines
        task = _between(text, m_task, m_team)
        facts = _between(text, m_facts, m_plan)
        plan = _between(text, m_plan, None)
        return (task, facts, plan)


    def _extract_message_content(self, message):
        """Extract text content from various message types"""
        if hasattr(message, 'response') and hasattr(message.response, 'chat_message'):
            return message.response.chat_message.content
        elif hasattr(message, 'content'):
            return message.content
        elif hasattr(message, 'message') and hasattr(message.message, 'content'):
            return message.message.content
        return None


    def _get_message_source_any(self, msg: Any) -> str | None:
        try:
            if hasattr(msg, 'response') and hasattr(msg.response, 'chat_message') and hasattr(msg.response.chat_message, 'source'):
                return str(msg.response.chat_message.source)
            if hasattr(msg, 'message') and hasattr(msg.message, 'source'):
                return str(msg.message.source)
            if hasattr(msg, 'source'):
                return str(msg.source)
        except Exception:
            return None
        return None
