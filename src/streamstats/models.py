from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Level(Enum):
    critical = "CRITICAL"
    error = "ERROR"
    warning = "WARNING"
    info = "INFO"
    debug = "DEBUG"

@dataclass
class Event:
    timestamp: datetime     #TODO:common timezone as UTC if not given
    level: Level
    source: str
    message: str
