"""
Checkpoint-aware wrapper classes for AG2 components.

This module provides wrapper classes that add checkpointing capabilities to existing
AG2 classes without modifying the original AG2 codebase.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# Import AG2 components with fallback
try:
    import sys
    ag2_path = Path(__file__).parent.parent / "ag2-0.10.0"
    if ag2_path.exists() and str(ag2_path) not in sys.path:
        sys.path.insert(0, str(ag2_path))
    
    from autogen.agentchat.groupchat import GroupChat, GroupChatManager
    from autogen.agentchat.conversable_agent import ConversableAgent
    from autogen.agentchat.agent import Agent  # Add Agent import
    from autogen.agentchat.chat import ChatResult
    from autogen.code_utils import content_str
    from autogen.io.base import IOStream
    from autogen.events.agent_events import GroupChatRunChatEvent, TerminationEvent
    from autogen.exception_utils import NoEligibleSpeakerError
    
    logger.info("AG2 components imported successfully for wrappers")
    
except ImportError as e:
    logger.warning(f"AG2 components not available for wrappers: {e}")
    # Create stub classes for development
    class GroupChat: pass
    class GroupChatManager: pass
    class ConversableAgent: pass
    class IOStream: 
        @staticmethod
        def get_default(): return None
    class GroupChatRunChatEvent: pass
    class NoEligibleSpeakerError(Exception): pass

from .core import CheckpointManager, CheckpointData


class CheckpointableGroupChat:
    """
    Wrapper for GroupChat that adds basic checkpointing capabilities.
    
    This is a simple wrapper that can be used to add checkpointing to existing
    GroupChat objects without modifying them.
    """
    
    def __init__(self, groupchat: GroupChat, checkpoint_manager: CheckpointManager, problem_context: str = ""):
        self.groupchat = groupchat
        self.checkpoint_manager = checkpoint_manager
        self.problem_context = problem_context
        self.checkpoint_ids = []
        
    def save_checkpoint(self, description: str = "") -> str:
        """Save a checkpoint of the current GroupChat state."""
        checkpoint_id = self.checkpoint_manager.save_checkpoint(
            groupchat=self.groupchat,
            manager=None,  # No manager for basic wrapper
            current_round=len(self.checkpoint_ids),
            total_steps=len(self.groupchat.messages),
            problem_context=self.problem_context,
            step_description=description
        )
        self.checkpoint_ids.append((description, checkpoint_id))
        return checkpoint_id
    
    def get_checkpoint_ids(self) -> List[Tuple[str, str]]:
        """Get all checkpoint IDs created by this wrapper."""
        return self.checkpoint_ids.copy()


class CheckpointingGroupChatManager(GroupChatManager):
    """
    GroupChatManager that automatically saves checkpoints at each conversation step.
    
    This class extends AG2's GroupChatManager to add automatic checkpointing
    functionality without breaking the existing AG2 API.
    """
    
    def __init__(
        self, 
        checkpoint_manager: CheckpointManager,
        problem_context: str = "",
        **kwargs
    ):
        """
        Initialize the CheckpointingGroupChatManager.
        
        Uses super().__init__() to preserve ALL original GroupChatManager logic,
        then strategically replaces only the reply function registration.
        
        Args:
            checkpoint_manager: The checkpoint manager to use for saving state
            problem_context: Description of the problem being solved
            **kwargs: All arguments passed directly to GroupChatManager
        """
        # Store checkpoint-related attributes
        self.checkpoint_manager = checkpoint_manager
        self.problem_context = problem_context
        self.step_counter = 0
        self.checkpoint_ids = []
        
        # Call parent __init__ to get ALL the original AG2 logic
        super().__init__(**kwargs)
        
        # **STRATEGIC OVERRIDE**: Replace only the reply function that points to GroupChatManager.run_chat
        # This preserves all other AG2 logic while ensuring our run_chat method gets called
        self._replace_run_chat_registration()
        
        logger.info(f"CheckpointingGroupChatManager initialized for problem: {problem_context[:50]}...")
    
    def _replace_run_chat_registration(self):
        """
        Replace GroupChatManager.run_chat registration with our run_chat method.
        
        This is a surgical replacement that preserves all other reply function settings
        while ensuring our checkpointing run_chat method gets called instead of the original.
        """
        try:
            # Find and replace the GroupChatManager.run_chat registration
            for i, reply_func_tuple in enumerate(self._reply_func_list):
                func = reply_func_tuple.get('reply_func')  # Correct key is 'reply_func'
                
                # Check if this is the GroupChatManager.run_chat registration
                if (func and hasattr(func, '__qualname__') and 
                    'GroupChatManager.run_chat' in func.__qualname__):
                    
                    # Create new tuple with our run_chat method but preserving all other settings
                    # IMPORTANT: Use CheckpointingGroupChatManager.run_chat (unbound) not self.run_chat (bound)
                    new_reply_func_tuple = reply_func_tuple.copy()
                    new_reply_func_tuple['reply_func'] = CheckpointingGroupChatManager.run_chat
                    self._reply_func_list[i] = new_reply_func_tuple
                    
                    logger.info("Successfully replaced GroupChatManager.run_chat with CheckpointingGroupChatManager.run_chat")
                    break
                    
                # Also handle async version if present  
                elif (func and hasattr(func, '__qualname__') and 
                      'GroupChatManager.a_run_chat' in func.__qualname__ and
                      hasattr(self, 'a_run_chat')):
                    
                    new_reply_func_tuple = reply_func_tuple.copy()
                    new_reply_func_tuple['reply_func'] = CheckpointingGroupChatManager.a_run_chat
                    self._reply_func_list[i] = new_reply_func_tuple
                    
                    logger.info("Successfully replaced GroupChatManager.a_run_chat with CheckpointingGroupChatManager.a_run_chat")
            
        except Exception as e:
            logger.warning(f"Could not replace reply function registration: {e}")
            # The system will still work, but will use original GroupChatManager.run_chat

    def run_chat(
        self,
        messages: list[dict[str, Any]] | None = None,
        sender: Any | None = None,
        config: Any | None = None,
    ) -> tuple[bool, str | None]:
        """Run a group chat with checkpointing - EXACT AG2 STRUCTURE."""
        iostream = IOStream.get_default()

        if messages is None:
            messages = self._oai_messages[sender]
        message = messages[-1]
        speaker = sender
        groupchat = config
        send_introductions = getattr(groupchat, "send_introductions", False)
        silent = getattr(self, "_silent", False)
        termination_reason = None

        # CHECKPOINT: Initial state
        self._save_checkpoint(
            step=0,
            groupchat=groupchat,
            messages=messages,
            speaker=speaker,
            message_content="Conversation start",
            action="conversation_start"
        )

        # Send introductions if configured - EXACT AG2 LOGIC
        if send_introductions:
            intro = groupchat.introductions_msg()
            for agent in groupchat.agents:
                self.send(intro, agent, request_reply=False, silent=True)

        # Client cache setup - EXACT AG2 LOGIC
        if self.client_cache is not None:
            for a in groupchat.agents:
                a.previous_cache = a.client_cache
                a.client_cache = self.client_cache
                
        # MAIN CONVERSATION LOOP - EXACT AG2 STRUCTURE
        for i in range(groupchat.max_round):
            self._last_speaker = speaker
            groupchat.append(message, speaker)
            
            # Broadcast the message to all agents except the speaker - EXACT AG2 LOGIC
            for agent in groupchat.agents:
                if agent != speaker:
                    inter_reply = groupchat._run_inter_agent_guardrails(
                        src_agent_name=speaker.name,
                        dst_agent_name=agent.name,
                        message_content=message,
                    )
                    if inter_reply is not None:
                        replacement = (
                            {"content": inter_reply, "name": speaker.name}
                            if not isinstance(inter_reply, dict)
                            else inter_reply
                        )
                        self.send(replacement, agent, request_reply=False, silent=True)
                    else:
                        self.send(message, agent, request_reply=False, silent=True)

            # CHECKPOINT: Message appended and broadcast
            self._save_checkpoint(
                step=len(groupchat.messages),
                groupchat=groupchat,
                messages=groupchat.messages,
                speaker=speaker,
                message_content=str(message.get("content", "")),
                action="message_appended",
                round_number=i
            )

            # Termination checks - EXACT AG2 LOGIC
            if self._is_termination_msg(message):
                termination_reason = f"Termination message condition on the GroupChatManager '{self.name}' met"
                break
            elif i == groupchat.max_round - 1:
                termination_reason = f"Maximum rounds ({groupchat.max_round}) reached"
                break
                
            try:
                # Select the next speaker - EXACT AG2 LOGIC
                speaker = groupchat.select_speaker(speaker, self)
                if not silent:
                    iostream = IOStream.get_default()
                    iostream.send(GroupChatRunChatEvent(speaker=speaker, silent=silent))

                guardrails_activated = False
                guardrails_reply = groupchat._run_input_guardrails(speaker, speaker._oai_messages[self])

                if guardrails_reply is not None:
                    guardrails_activated = True
                    reply = guardrails_reply
                else:
                    reply = speaker.generate_reply(sender=self)
            except KeyboardInterrupt:
                if groupchat.admin_name in groupchat.agent_names:
                    speaker = groupchat.agent_by_name(groupchat.admin_name)
                    reply = speaker.generate_reply(sender=self)
                else:
                    raise
            except NoEligibleSpeakerError:
                termination_reason = "No next speaker selected"
                break

            if reply is None:
                termination_reason = "No reply generated"
                break

            if not guardrails_activated:
                guardrails_reply = groupchat._run_output_guardrails(speaker, reply)
                if guardrails_reply is not None:
                    guardrails_activated = True
                    reply = guardrails_reply

            # Check for "clear history" phrase - EXACT AG2 LOGIC
            if groupchat.enable_clear_history and isinstance(reply, dict) and reply.get("content"):
                raw_content = reply.get("content")
                normalized_content = (
                    content_str(raw_content)
                    if isinstance(raw_content, (str, list)) or raw_content is None
                    else str(raw_content)
                )
                if "CLEAR HISTORY" in normalized_content.upper():
                    reply["content"] = normalized_content
                    reply["content"] = self.clear_agents_history(reply, groupchat)

            # The speaker sends the message - EXACT AG2 LOGIC
            speaker.send(reply, self, request_reply=False, silent=silent)
            message = self.last_message(speaker)

            # CHECKPOINT: Speaker reply generated
            self._save_checkpoint(
                step=len(groupchat.messages) + 0.5,  # Between message generation and next loop
                groupchat=groupchat,
                messages=groupchat.messages,
                speaker=speaker,
                message_content=str(reply) if reply else "None",
                action="speaker_reply_generated",
                round_number=i
            )
            
        # Client cache restoration - EXACT AG2 LOGIC
        if self.client_cache is not None:
            for a in groupchat.agents:
                a.client_cache = a.previous_cache
                a.previous_cache = None

        if termination_reason:
            iostream.send(
                TerminationEvent(
                    termination_reason=termination_reason, sender=self, recipient=speaker if speaker else None
                )
            )

        # FINAL CHECKPOINT
        self._save_checkpoint(
            step=len(groupchat.messages),
            groupchat=groupchat,
            messages=groupchat.messages,
            speaker=speaker,
            message_content="Conversation ended",
            action="conversation_end",
            termination_reason=termination_reason
        )

        return True, None

    def clear_agents_history(self, reply: Dict[str, Any], groupchat: "GroupChat") -> str:
        """
        Clears history of messages for all agents or a selected one. 
        EXACT copy of AG2's clear_agents_history method.
        """
        try:
            iostream = IOStream.get_default()
        except:
            iostream = None

        raw_reply_content = reply.get("content")
        if isinstance(raw_reply_content, str):
            reply_content = raw_reply_content
        elif isinstance(raw_reply_content, (list, type(None))):
            try:
                reply_content = content_str(raw_reply_content)
                reply["content"] = reply_content
            except:
                reply_content = str(raw_reply_content)
                reply["content"] = reply_content
        else:
            reply_content = str(raw_reply_content)
            reply["content"] = reply_content

        # Split the reply into words
        words = reply_content.split()
        # Find the position of "clear" to determine where to start processing
        clear_word_index = next(i for i in reversed(range(len(words))) if words[i].upper() == "CLEAR")
        # Extract potential agent name and steps
        words_to_check = words[clear_word_index + 2 : clear_word_index + 4]
        nr_messages_to_preserve = None
        nr_messages_to_preserve_provided = False
        agent_to_memory_clear = None

        for word in words_to_check:
            if word.isdigit():
                nr_messages_to_preserve = int(word)
                nr_messages_to_preserve_provided = True
            elif word[:-1].isdigit():  # for the case when number of messages is followed by dot or other sign
                nr_messages_to_preserve = int(word[:-1])
                nr_messages_to_preserve_provided = True
            else:
                for agent in groupchat.agents:
                    if agent.name == word or agent.name == word[:-1]:
                        agent_to_memory_clear = agent
                        break

        # preserve last tool call message if clear history called inside of tool response
        if "tool_responses" in reply and not nr_messages_to_preserve:
            nr_messages_to_preserve = 1
            logger.warning(
                "The last tool call message will be saved to prevent errors caused by tool response without tool call."
            )

        # clear history
        if iostream:
            try:
                from autogen.events.agent_events import ClearAgentsHistoryEvent
                iostream.send(
                    ClearAgentsHistoryEvent(agent=agent_to_memory_clear, nr_events_to_preserve=nr_messages_to_preserve)
                )
            except:
                pass

        if agent_to_memory_clear:
            agent_to_memory_clear.clear_history(nr_messages_to_preserve=nr_messages_to_preserve)
        else:
            if nr_messages_to_preserve:
                # clearing history for groupchat here
                temp = groupchat.messages[-nr_messages_to_preserve:]
                groupchat.messages.clear()
                groupchat.messages.extend(temp)
            else:
                # clearing history for groupchat here
                groupchat.messages.clear()
            # clearing history for agents
            for agent in groupchat.agents:
                agent.clear_history(nr_messages_to_preserve=nr_messages_to_preserve)

        # Reconstruct the reply without the "clear history" command and parameters
        skip_words_number = 2 + int(bool(agent_to_memory_clear)) + int(nr_messages_to_preserve_provided)
        reply_content = " ".join(words[:clear_word_index] + words[clear_word_index + skip_words_number :])

        return reply_content
    
    def _save_checkpoint(
        self, 
        step: int,
        groupchat: "GroupChat",
        messages: List[Dict[str, Any]],
        speaker: "ConversableAgent", 
        message_content: str,
        action: str,
        **kwargs
    ) -> Optional[str]:
        """Save a checkpoint using centralized checkpoint creation logic from core.py."""
        try:
            # Use the centralized checkpoint creation method from CheckpointManager
            # This eliminates logic duplication and ensures consistency
            saved_checkpoint_id = self.checkpoint_manager.create_conversation_checkpoint(
                step=step,
                action=action,
                groupchat=groupchat,
                manager=self,
                speaker=speaker,
                message_content=message_content,
                problem_context=self.problem_context,
                **kwargs
            )
            
            # Update internal tracking
            self.checkpoint_ids.append((f"{action}: {message_content[:50]}...", saved_checkpoint_id))
            
            logger.info(f"Checkpoint saved: {saved_checkpoint_id} (Step {step}, {action})")
            self.step_counter += 1
            return saved_checkpoint_id
            
        except Exception as e:
            logger.error(f"Checkpoint save failed: {e}")
            return None
    
    def get_checkpoint_ids(self) -> List[Tuple[str, str]]:
        """Get all checkpoint IDs created during the conversation."""
        return self.checkpoint_ids.copy()
    
    def get_checkpoint_count(self) -> int:
        """Get the total number of checkpoints created."""
        return len(self.checkpoint_ids)

    def continue_from_loaded_state(self, max_additional_rounds: int = 5) -> tuple[bool, str | None]:
        """
        Continue conversation from current loaded state using the same AG2 structure.
        
        Args:
            max_additional_rounds: Maximum additional rounds to allow
            
        Returns:
            tuple[bool, str | None]: (success, termination_reason)
        """
        logger.info(f"🔄 Continuing from loaded state with max {max_additional_rounds} additional rounds")
        
        groupchat = self._groupchat
        if not groupchat:
            raise ValueError("No GroupChat configured - cannot continue conversation")
            
        # Get the current state
        current_messages = len(groupchat.messages)
        logger.info(f"📋 Current state: {current_messages} messages in GroupChat")
        
        if current_messages == 0:
            raise ValueError("No messages in GroupChat - nothing to continue from")
        
        # Get the last message and speaker to continue from
        last_message = groupchat.messages[-1]
        last_speaker_name = last_message.get('name')
        last_speaker = groupchat.agent_by_name(last_speaker_name) if last_speaker_name else None
        
        if not last_speaker:
            raise ValueError(f"Cannot find last speaker '{last_speaker_name}' in GroupChat agents")
            
        logger.info(f"👤 Continuing from last speaker: {last_speaker.name}")
        logger.info(f"💬 Last message: {str(last_message.get('content', ''))[:100]}...")
        
        # Verify that agents have proper message histories
        logger.info("🔍 Verifying agent message histories...")
        for agent in groupchat.agents:
            if hasattr(agent, '_oai_messages'):
                total_messages = sum(len(msgs) for msgs in agent._oai_messages.values())
        
        # Update max_round to allow additional conversation
        original_max_round = groupchat.max_round
        groupchat.max_round = current_messages + max_additional_rounds
        logger.info(f"📊 Updated max_round from {original_max_round} to {groupchat.max_round}")
        
        try:
            logger.info(f"💬 Continuing conversation from round {current_messages}...")
            
            # Client cache setup - EXACT AG2 LOGIC
            if self.client_cache is not None:
                for a in groupchat.agents:
                    a.previous_cache = a.client_cache
                    a.client_cache = self.client_cache
            
            # Continue with AG2 structure starting from current position
            iostream = IOStream.get_default()
            silent = getattr(self, "_silent", False)
            termination_reason = None
            speaker = last_speaker
            message = last_message
            
            # MAIN CONVERSATION LOOP - same as run_chat but starting from current_messages
            for i in range(current_messages, groupchat.max_round):
                # Skip the first iteration's message processing since it's already in GroupChat
                if i > current_messages:
                    self._last_speaker = speaker
                    groupchat.append(message, speaker)
                    
                    # Broadcast the message to all agents except the speaker
                    for agent in groupchat.agents:
                        if agent != speaker:
                            inter_reply = groupchat._run_inter_agent_guardrails(
                                src_agent_name=speaker.name,
                                dst_agent_name=agent.name,
                                message_content=message,
                            )
                            if inter_reply is not None:
                                replacement = (
                                    {"content": inter_reply, "name": speaker.name}
                                    if not isinstance(inter_reply, dict)
                                    else inter_reply
                                )
                                self.send(replacement, agent, request_reply=False, silent=True)
                            else:
                                self.send(message, agent, request_reply=False, silent=True)

                    # CHECKPOINT: Message appended and broadcast
                    self._save_checkpoint(
                        step=len(groupchat.messages),
                        groupchat=groupchat,
                        messages=groupchat.messages,
                        speaker=speaker,
                        message_content=str(message.get("content", "")),
                        action="message_appended",
                        round_number=i
                    )

                # Termination checks - EXACT AG2 LOGIC
                if self._is_termination_msg(message):
                    termination_reason = f"Termination message condition on the GroupChatManager '{self.name}' met"
                    break
                elif i == groupchat.max_round - 1:
                    termination_reason = f"Maximum rounds ({groupchat.max_round}) reached"
                    break
                    
                try:
                    # Select the next speaker - EXACT AG2 LOGIC
                    speaker = groupchat.select_speaker(speaker, self)
                    if not silent:
                        iostream = IOStream.get_default()
                        iostream.send(GroupChatRunChatEvent(speaker=speaker, silent=silent))

                    guardrails_activated = False
                    guardrails_reply = groupchat._run_input_guardrails(speaker, speaker._oai_messages[self])

                    if guardrails_reply is not None:
                        guardrails_activated = True
                        reply = guardrails_reply
                    else:
                        reply = speaker.generate_reply(sender=self)
                except KeyboardInterrupt:
                    if groupchat.admin_name in groupchat.agent_names:
                        speaker = groupchat.agent_by_name(groupchat.admin_name)
                        reply = speaker.generate_reply(sender=self)
                    else:
                        raise
                except NoEligibleSpeakerError:
                    termination_reason = "No next speaker selected"
                    break

                if reply is None:
                    termination_reason = "No reply generated"
                    break

                if not guardrails_activated:
                    guardrails_reply = groupchat._run_output_guardrails(speaker, reply)
                    if guardrails_reply is not None:
                        guardrails_activated = True
                        reply = guardrails_reply

                # Check for "clear history" phrase - EXACT AG2 LOGIC
                if groupchat.enable_clear_history and isinstance(reply, dict) and reply.get("content"):
                    raw_content = reply.get("content")
                    normalized_content = (
                        content_str(raw_content)
                        if isinstance(raw_content, (str, list)) or raw_content is None
                        else str(raw_content)
                    )
                    if "CLEAR HISTORY" in normalized_content.upper():
                        reply["content"] = normalized_content
                        reply["content"] = self.clear_agents_history(reply, groupchat)

                # The speaker sends the message - EXACT AG2 LOGIC
                speaker.send(reply, self, request_reply=False, silent=silent)
                message = self.last_message(speaker)

                # CHECKPOINT: Speaker reply generated
                self._save_checkpoint(
                    step=len(groupchat.messages) + 0.5,
                    groupchat=groupchat,
                    messages=groupchat.messages,
                    speaker=speaker,
                    message_content=str(reply) if reply else "None",
                    action="speaker_reply_generated",
                    round_number=i
                )
            
            # Send termination event if needed
            if termination_reason:
                iostream.send(
                    TerminationEvent(
                        termination_reason=termination_reason, 
                        sender=self, 
                        recipient=speaker if speaker else None
                    )
                )
            
            # Final checkpoint
            self._save_checkpoint(
                step=len(groupchat.messages),
                groupchat=groupchat,
                messages=groupchat.messages,
                speaker=speaker,
                message_content="Continuation completed",
                action="continuation_end",
                termination_reason=termination_reason
            )
            
            logger.info(f"✅ Conversation continuation completed")
            logger.info(f"📊 Final state: {len(groupchat.messages)} messages")
            if termination_reason:
                logger.info(f"🛑 Final termination reason: {termination_reason}")
            
            return True, termination_reason
            
        except Exception as e:
            logger.error(f"Error during continuation: {e}")
            raise
        finally:
            # Always restore original max_round and client cache
            groupchat.max_round = original_max_round
            if self.client_cache is not None:
                for a in groupchat.agents:
                    if hasattr(a, 'previous_cache'):
                        a.client_cache = a.previous_cache
                        a.previous_cache = None


def create_checkpointing_manager(
    checkpoint_manager: CheckpointManager,
    groupchat: GroupChat,
    problem_context: str = "",
    **kwargs
) -> CheckpointingGroupChatManager:
    """
    Factory function to create a CheckpointingGroupChatManager.
    
    Args:
        checkpoint_manager: The checkpoint manager to use
        groupchat: The GroupChat to manage
        problem_context: Description of the problem being solved
        **kwargs: Additional arguments for GroupChatManager
        
    Returns:
        CheckpointingGroupChatManager: Configured checkpointing manager
    """
    return CheckpointingGroupChatManager(
        checkpoint_manager=checkpoint_manager,
        problem_context=problem_context,
        name=kwargs.get('name', 'chat_manager'),
        groupchat=groupchat,
        **kwargs
    )