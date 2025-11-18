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
                "state": "greeting",  # greeting, consulting, collecting_data, completed
                "conversation_history": [],
                "detected_intent": None,
                "detected_services": [],  # List of services detected
                "selected_services": [],  # List of services user is interested in
                "confirmed_intent": False,
                "collected_info": {
                    "first_name": None,
                    "last_name": None,
                    "phone": None
                },
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
        info: Optional[Dict[str, Any]] = None,
        detected_services: Optional[List[Dict[str, str]]] = None,
        selected_services: Optional[List[Dict[str, str]]] = None
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
        
        if detected_services is not None:
            # Merge detected services, avoiding duplicates
            existing_codes = {s.get("code") for s in user_state.get("detected_services", [])}
            for service in detected_services:
                if service.get("code") not in existing_codes:
                    user_state.setdefault("detected_services", []).append(service)
        
        if selected_services is not None:
            # Merge selected services, avoiding duplicates
            existing_codes = {s.get("code") for s in user_state.get("selected_services", [])}
            for service in selected_services:
                if service.get("code") not in existing_codes:
                    user_state.setdefault("selected_services", []).append(service)
        
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
        collected_info = user_state.get("collected_info", {})
        
        # Ready if:
        # 1. We have phone number (REQUIRED!)
        # 2. User has services or intent detected
        # Phone is the most important - if we have it and services, create lead
        
        has_phone = bool(collected_info.get("phone"))
        if not has_phone:
            return False  # Phone is mandatory
        
        has_services = (
            len(user_state.get("selected_services", [])) > 0 or
            len(user_state.get("detected_services", [])) > 0 or
            user_state.get("detected_intent") is not None
        )
        
        # If we have phone and services, create lead
        # Don't require confirmed_intent if we have services detected
        current_state = user_state.get("state", "greeting")
        
        return (
            has_phone and
            has_services and
            current_state in ["collecting_data", "consulting", "completed", "greeting"]  # Allow all states if we have phone and services
        )
    
    def has_collected_all_data(self, user_id: int) -> bool:
        """Check if all required data is collected."""
        user_state = self.get_state(user_id)
        collected_info = user_state.get("collected_info", {})
        return (
            collected_info.get("first_name") and
            collected_info.get("last_name") and
            collected_info.get("phone")
        )


# Global conversation state manager
conversation_state = ConversationState()

