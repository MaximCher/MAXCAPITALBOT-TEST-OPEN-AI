"""
Conversation State Management for MAXCAPITAL Bot.

Manages conversation states and context for each user session.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import os


CONVERSATION_STATE_FILE = "conversation_states.json"


class ConversationState:
    """Manages conversation state for a user."""
    
    def __init__(self, state_file: str = CONVERSATION_STATE_FILE):
        self.state_file = state_file
        self.states = self._load_states()
    
    def _load_states(self) -> Dict[str, Any]:
        """Load conversation states from file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {}
    
    def _save_states(self):
        """Save conversation states to file."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving conversation states: {e}")
    
    def get_state(self, user_id: int) -> Dict[str, Any]:
        """Get conversation state for user."""
        user_key = str(user_id)
        if user_key not in self.states:
            self.states[user_key] = {
                "state": "greeting",  # greeting, consulting, confirming, completed
                "conversation_history": [],
                "detected_intent": None,
                "confirmed_intent": False,
                "collected_info": {},
                "last_updated": datetime.now().isoformat()
            }
            self._save_states()
        
        return self.states[user_key]
    
    def update_state(
        self,
        user_id: int,
        state: Optional[str] = None,
        message: Optional[str] = None,
        intent: Optional[str] = None,
        confirmed: Optional[bool] = None,
        info: Optional[Dict[str, Any]] = None
    ):
        """Update conversation state for user."""
        user_key = str(user_id)
        user_state = self.get_state(user_id)
        
        if state:
            user_state["state"] = state
        
        if message:
            # Add to conversation history (keep last 20 messages)
            user_state["conversation_history"].append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
            # Keep only last 20 messages
            if len(user_state["conversation_history"]) > 20:
                user_state["conversation_history"] = user_state["conversation_history"][-20:]
        
        if intent:
            user_state["detected_intent"] = intent
        
        if confirmed is not None:
            user_state["confirmed_intent"] = confirmed
        
        if info:
            user_state["collected_info"].update(info)
        
        user_state["last_updated"] = datetime.now().isoformat()
        self._save_states()
    
    def add_assistant_message(self, user_id: int, message: str):
        """Add assistant message to conversation history."""
        user_state = self.get_state(user_id)
        user_state["conversation_history"].append({
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 20 messages
        if len(user_state["conversation_history"]) > 20:
            user_state["conversation_history"] = user_state["conversation_history"][-20:]
        user_state["last_updated"] = datetime.now().isoformat()
        self._save_states()
    
    def get_conversation_history(self, user_id: int) -> List[Dict[str, str]]:
        """Get conversation history formatted for AI."""
        user_state = self.get_state(user_id)
        # Format for AI API (only role and content)
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in user_state["conversation_history"]
        ]
    
    def reset_state(self, user_id: int):
        """Reset conversation state for user."""
        user_key = str(user_id)
        if user_key in self.states:
            del self.states[user_key]
            self._save_states()
    
    def is_ready_for_lead(self, user_id: int) -> bool:
        """Check if conversation is ready to create lead."""
        user_state = self.get_state(user_id)
        # Ready if:
        # 1. Intent is detected
        # 2. User confirmed their intention
        # 3. State is confirming or consulting with confirmation
        return (
            user_state.get("detected_intent") is not None and
            user_state.get("confirmed_intent") is True and
            user_state["state"] in ["confirming", "consulting"]
        )


# Global conversation state manager
conversation_state = ConversationState()

