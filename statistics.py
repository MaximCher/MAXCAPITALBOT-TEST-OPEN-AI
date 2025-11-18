"""
Statistics module for MAXCAPITAL Bot.

Tracks:
- User sessions (started conversations)
- Lead conversions (users who became leads)
- Intent distribution
- User journey analytics
- Service interests
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import db

STATS_FILE = "bot_statistics.json"


class BotStatistics:
    """Manages bot usage statistics."""
    
    def __init__(self, stats_file: str = STATS_FILE):
        self.stats_file = stats_file
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict[str, Any]:
        """Load statistics from file."""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Initialize default structure
        return {
            "sessions": {},  # user_id -> session data
            "daily_stats": {},  # date -> stats
            "intent_stats": {},  # intent -> count
            "lead_conversions": 0,
            "total_sessions": 0,
            "total_leads": 0
        }
    
    def _save_stats(self):
        """Save statistics to file."""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving statistics: {e}")
    
    def start_session(self, user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str] = None):
        """Record a new user session."""
        # Try to use database first
        if db.database.is_available():
            try:
                # Upsert user
                db_user_id = db.database.upsert_user(
                    telegram_user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                
                if db_user_id:
                    # Create session in database
                    db_session_id = db.database.create_session(
                        user_id=db_user_id,
                        telegram_user_id=user_id,
                        status="active"
                    )
                    
                    if db_session_id:
                        # Also save to JSON for backward compatibility
                        today = datetime.now().strftime("%Y-%m-%d")
                        if today not in self.stats["daily_stats"]:
                            self.stats["daily_stats"][today] = {
                                "sessions": 0,
                                "leads": 0,
                                "intents": {}
                            }
                        
                        session_id = f"{user_id}_{datetime.now().timestamp()}"
                        self.stats["sessions"][session_id] = {
                            "user_id": user_id,
                            "db_session_id": db_session_id,
                            "username": username,
                            "first_name": first_name,
                            "started_at": datetime.now().isoformat(),
                            "messages": [],
                            "intents": [],
                            "converted_to_lead": False,
                            "lead_id": None,
                            "contact_id": None
                        }
                        
                        self.stats["total_sessions"] += 1
                        self.stats["daily_stats"][today]["sessions"] += 1
                        self._save_stats()
                        
                        return session_id
            except Exception as e:
                print(f"Error creating session in database: {e}")
        
        # Fallback to JSON only
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {
                "sessions": 0,
                "leads": 0,
                "intents": {}
            }
        
        session_id = f"{user_id}_{datetime.now().timestamp()}"
        self.stats["sessions"][session_id] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "started_at": datetime.now().isoformat(),
            "messages": [],
            "intents": [],
            "converted_to_lead": False,
            "lead_id": None,
            "contact_id": None
        }
        
        self.stats["total_sessions"] += 1
        self.stats["daily_stats"][today]["sessions"] += 1
        self._save_stats()
        
        return session_id
    
    def add_message(self, session_id: str, message: str, intent: Optional[str], detected_services: Optional[List[Dict[str, str]]] = None):
        """Add a message to session."""
        # Try to add to database first
        if db.database.is_available() and session_id in self.stats["sessions"]:
            session = self.stats["sessions"][session_id]
            db_session_id = session.get("db_session_id")
            
            if db_session_id:
                try:
                    service_codes = [s.get("code") for s in (detected_services or [])]
                    db.database.add_message(
                        session_id=db_session_id,
                        message_text=message,
                        message_type="user",
                        detected_intent=intent,
                        detected_services=service_codes if service_codes else None
                    )
                    
                    # Also add service interests
                    if detected_services:
                        for service in detected_services:
                            db.database.add_service_interest(
                                session_id=db_session_id,
                                service_code=service.get("code", ""),
                                service_name=service.get("name", ""),
                                interest_level="interested"
                            )
                        
                        # Update session status to "interested" if services detected
                        db.database.update_session(
                            session_id=db_session_id,
                            status="interested"
                        )
                except Exception as e:
                    print(f"Error adding message to database: {e}")
        
        # Also save to JSON
        if session_id in self.stats["sessions"]:
            session = self.stats["sessions"][session_id]
            session["messages"].append({
                "text": message,
                "intent": intent,
                "timestamp": datetime.now().isoformat()
            })
            
            if intent:
                session["intents"].append(intent)
                if "intent_stats" not in self.stats:
                    self.stats["intent_stats"] = {}
                self.stats["intent_stats"][intent] = self.stats["intent_stats"].get(intent, 0) + 1
                
                today = datetime.now().strftime("%Y-%m-%d")
                if today in self.stats["daily_stats"]:
                    if "intents" not in self.stats["daily_stats"][today]:
                        self.stats["daily_stats"][today]["intents"] = {}
                    self.stats["daily_stats"][today]["intents"][intent] = \
                        self.stats["daily_stats"][today]["intents"].get(intent, 0) + 1
            
            self._save_stats()
    
    def convert_to_lead(self, session_id: str, lead_id: int, contact_id: Optional[int] = None, services_interested: Optional[List[str]] = None):
        """Mark session as converted to lead."""
        # Update database first
        if db.database.is_available() and session_id in self.stats["sessions"]:
            session = self.stats["sessions"][session_id]
            db_session_id = session.get("db_session_id")
            
            if db_session_id:
                try:
                    db.database.update_session(
                        session_id=db_session_id,
                        status="converted_to_lead",
                        services_interested=services_interested,
                        lead_id=lead_id,
                        contact_id=contact_id
                    )
                except Exception as e:
                    print(f"Error updating session in database: {e}")
        
        # Also update JSON
        if session_id in self.stats["sessions"]:
            session = self.stats["sessions"][session_id]
            if not session["converted_to_lead"]:
                session["converted_to_lead"] = True
                session["lead_id"] = lead_id
                session["contact_id"] = contact_id
                session["converted_at"] = datetime.now().isoformat()
                
                self.stats["lead_conversions"] += 1
                self.stats["total_leads"] += 1
                
                today = datetime.now().strftime("%Y-%m-%d")
                if today in self.stats["daily_stats"]:
                    self.stats["daily_stats"][today]["leads"] += 1
                
                self._save_stats()
    
    def get_session(self, user_id: int) -> Optional[str]:
        """Get active session ID for user."""
        # Find most recent session for user
        user_sessions = [
            (sid, s) for sid, s in self.stats["sessions"].items()
            if s["user_id"] == user_id
        ]
        
        if user_sessions:
            # Sort by started_at, get most recent
            user_sessions.sort(key=lambda x: x[1]["started_at"], reverse=True)
            return user_sessions[0][0]
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        # Try to get from database first
        if db.database.is_available():
            try:
                db_stats = db.database.get_statistics()
                # Merge with JSON stats for backward compatibility
                json_stats = self._get_json_statistics()
                
                return {
                    "total_visitors": db_stats.get("total_visitors", json_stats.get("total_sessions", 0)),
                    "total_interested": db_stats.get("total_interested", 0),
                    "total_leads": db_stats.get("total_leads", json_stats.get("total_leads", 0)),
                    "conversion_rate": round(
                        (db_stats.get("total_leads", 0) / db_stats.get("total_visitors", 1) * 100) 
                        if db_stats.get("total_visitors", 0) > 0 else 0, 
                        2
                    ),
                    "service_distribution": db_stats.get("service_distribution", {}),
                    "intent_distribution": json_stats.get("intent_distribution", {}),
                    "daily_stats": db_stats.get("daily_stats", json_stats.get("last_7_days", [])),
                    "lead_conversions": db_stats.get("total_leads", json_stats.get("lead_conversions", 0))
                }
            except Exception as e:
                print(f"Error getting statistics from database: {e}")
        
        # Fallback to JSON only
        return self._get_json_statistics()
    
    def _get_json_statistics(self) -> Dict[str, Any]:
        """Get statistics from JSON file (fallback)."""
        total_sessions = self.stats["total_sessions"]
        total_leads = self.stats["total_leads"]
        conversion_rate = (total_leads / total_sessions * 100) if total_sessions > 0 else 0
        
        # Last 7 days stats
        last_7_days = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            if date in self.stats["daily_stats"]:
                last_7_days.append({
                    "date": date,
                    **self.stats["daily_stats"][date]
                })
        
        # Convert daily stats intents to dict
        last_7_days_clean = []
        for day in last_7_days:
            day_clean = dict(day)
            if "intents" in day_clean and isinstance(day_clean["intents"], dict):
                day_clean["intents"] = dict(day_clean["intents"])
            last_7_days_clean.append(day_clean)
        
        return {
            "total_sessions": total_sessions,
            "total_leads": total_leads,
            "conversion_rate": round(conversion_rate, 2),
            "intent_distribution": self.stats.get("intent_stats", {}),
            "last_7_days": last_7_days_clean,
            "lead_conversions": self.stats["lead_conversions"]
        }
    
    def get_user_journey(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user journey for specific user."""
        session_id = self.get_session(user_id)
        if session_id and session_id in self.stats["sessions"]:
            return self.stats["sessions"][session_id]
        return None


# Global statistics instance
stats = BotStatistics()

