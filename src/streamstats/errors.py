class StreamStatsError(Exception):
    """Common application error."""


class FormatError(StreamStatsError):
    """Unsupported format."""


class EventError(StreamStatsError):
    """Invalid event."""


class TimestampError(StreamStatsError):
    """Timestamp seems to be broken."""


class CLIError(StreamStatsError):
    """CLI configuration error."""
