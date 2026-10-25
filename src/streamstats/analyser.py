from .parsers import parse_event, read_jsonl, read_csv

def analyze(event_generator):
    amount_events = 0
    amount_levels = {}
    amount_sources = {}
    earliest_timestamp = None
    latest_timestamp = None
    error_sources = {}


    for event in event_generator:
        timestamp = event.timestamp
        level = event.level.value
        source = event.source

        # count every level
        if level not in amount_levels:
            amount_levels[level] = 0
        amount_levels[level] += 1

        # count problematic sources
        if level in ["CRITICAL", "ERROR"]:
            if source not in error_sources:
                error_sources[source] = 0
            error_sources[source] += 1

        # count every source
        if source not in amount_sources:
            amount_sources[source] = 0
        amount_sources[source] += 1

        # count the amount of the events
        amount_events += 1

        # find the earliest and latest timestamps
        if earliest_timestamp is None or timestamp < earliest_timestamp:
            earliest_timestamp = timestamp
        if latest_timestamp is None or timestamp > latest_timestamp:
            latest_timestamp = timestamp

    def sort_key(top):
        return (-top[1], top[0])


    pairs = sorted(list(error_sources.items()), key=sort_key)[:5]

    return {
        "total": amount_events,
        "levels": amount_levels,
        "sources": amount_sources,
        "top5": pairs,
        "earliest": earliest_timestamp.isoformat() if earliest_timestamp is not None else None,
        "latest": latest_timestamp.isoformat() if latest_timestamp is not None else None
    }
