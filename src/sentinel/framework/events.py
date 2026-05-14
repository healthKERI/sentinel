"""
Event data classes for the Sentinel Framework.

Defines structured event data passed to handlers when KEL/TEL/Credential files change.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class BaseEvent:
    """
    Base class for all file change events.

    Attributes:
        aid: Identifier prefix extracted from filename
        filepath: Absolute path to the .cesr file
        data: Raw CESR file contents
        timestamp: File modification time
        hby: Optional Habery instance for KERI operations
        essr: Optional API client for healthKERI
        db: Optional database instance
    """

    aid: str
    filepath: str
    data: bytes
    timestamp: int

    # Optional: only populated if run() was given KERI infrastructure
    hby: Optional[object] = None
    essr: Optional[object] = None
    db: Optional[object] = None


@dataclass
class KELEvent(BaseEvent):
    """
    Event for Key Event Log changes.

    Dispatched when a KEL (.cesr) file is created or modified in the kel/ directory.
    """

    pass


@dataclass
class TELEvent(BaseEvent):
    """
    Event for Transaction Event Log changes.

    Dispatched when a TEL (.cesr) file is created or modified in the tel/ directory.
    """

    pass


@dataclass
class CredentialEvent(BaseEvent):
    """
    Event for Credential changes.

    Dispatched when a credential (.cesr) file is created or modified in the cred/ directory.
    """

    pass
