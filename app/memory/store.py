from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str

class MemoryStore:
    def __init__(self, max_turns: int = 10) -> None:
        self.max_turns = max_turns
        self._sessions: Dict[str, List[Message]] = {}

    def get(self, session_id: str) -> List[Message]:
        return list(self._sessions.get(session_id, []))

    def add(self, session_id: str, role: str, content: str) -> None:
        msgs = self._sessions.setdefault(session_id, [])
        msgs.append(Message(role=role, content=content))

        # keep only last N turns (2 messages per turn)
        max_msgs = self.max_turns * 2
        if len(msgs) > max_msgs:
            self._sessions[session_id] = msgs[-max_msgs:]