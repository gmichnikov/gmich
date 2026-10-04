"""
Minutes math, game state replay, and scoring logic for Basketball Minutes.
"""

from collections import defaultdict, namedtuple
from datetime import datetime
from app import db
from app.projects.basketball_minutes.models import (
    BkmEvent,
    BkmGame,
    BkmGameRosterEntry,
    BkmPlayer,
)

BkmStint = namedtuple("BkmStint", "player_id period start_rem_sec end_rem_sec duration_sec")


def parse_time_input(raw_str, default_sec=None):
    """
    Parse a microwave-style or mm:ss string into total seconds remaining.
    Examples:
    - '530' -> 5 minutes 30 seconds -> 330 seconds
    - '5:30' -> 330 seconds
    - '45' -> 45 seconds (or if > 59 like 90 -> 1 min 30 sec)
    - '8' -> 8 minutes (if single digit <= 20) or 8 seconds?
    Let's handle standard input gracefully:
    If contains ':', split by ':'.
    If all digits:
      - 1 or 2 digits: could be seconds (e.g. 45 -> 45s, 0 -> 0s)
        If user typed '8', let's check: if > 12 it's seconds, if <= 12 might be minutes?
        Actually microwave style:
        '800' -> 8m 00s = 480s
        '530' -> 5m 30s = 330s
        '45' -> 45s
        '0' -> 0s
    """
    if raw_str is None:
        return default_sec

    s = str(raw_str).strip()
    if not s:
        return default_sec

    if ":" in s:
        parts = s.split(":")
        try:
            m = int(parts[0])
            sec = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            return max(0, m * 60 + sec)
        except (ValueError, TypeError):
            return default_sec

    # Digits only
    if s.isdigit():
        val = int(s)
        if len(s) <= 2:
            # e.g. 45 -> 45s; 0 -> 0s
            return val
        else:
            # e.g. 530 -> min = 5, sec = 30
            m = int(s[:-2])
            sec = int(s[-2:])
            return max(0, m * 60 + sec)

    return default_sec


def format_remaining_time(seconds):
    """Formats seconds remaining as M:SS (e.g. 330 -> '5:30', 45 -> '0:45')."""
    if seconds is None:
        return "0:00"
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def format_duration(seconds):
    """
    Formats total seconds played as human-readable string:
    e.g. 330s -> '5m 30s', 45s -> '45s', 0s -> '0m'.
    """
    if not seconds:
        return "0m"
    m = seconds // 60
    s = seconds % 60
    if m > 0 and s > 0:
        return f"{m}m {s}s"
    if m > 0:
        return f"{m}m"
    return f"{s}s"


def ordered_events(game, events=None):
    if events is not None:
        return list(events)
    return (
        BkmEvent.query.filter_by(game_id=game.id)
        .order_by(BkmEvent.period, BkmEvent.id)
        .all()
    )


def game_phase(game, events=None):
    """
    Phases:
    - 'setup': No period_start event yet.
    - 'live': Period in progress (last event is period_start, sub, or score).
    - 'between': Period ended, but game not fully completed (period < period_count or pending OT).
    - 'done': Final period ended and coach marked game complete (no OT requested).
    """
    events = ordered_events(game, events)
    if not any(e.event_type == "period_start" for e in events):
        return "setup"
    last = events[-1]
    if last.event_type == "period_end":
        # If payload says game_over: True
        if last.payload.get("game_over"):
            return "done"
        if last.period >= game.period_count and last.payload.get("game_over") is not False:
            # If not explicitly continuing to OT
            return "done"
        return "between"
    return "live"


def current_period_info(game, events=None):
    events = ordered_events(game, events)
    phase = game_phase(game, events)
    
    if phase == "setup":
        return {"period": 1, "is_ot": False, "label": "Q1" if game.period_count == 4 else "H1"}
    
    last_event = events[-1]
    curr_period = last_event.period
    
    if phase == "between":
        curr_period += 1
    
    is_ot = curr_period > game.period_count
    if is_ot:
        ot_num = curr_period - game.period_count
        label = f"OT{ot_num}" if ot_num > 1 else "OT"
    elif game.period_count == 4:
        label = f"Q{curr_period}"
    elif game.period_count == 2:
        label = f"H{curr_period}"
    else:
        label = f"P{curr_period}"
        
    return {"period": curr_period, "is_ot": is_ot, "label": label}


def replay_lineup(events, draft_lineup=None):
    """
    Returns the current 5-player on-court lineup as a list of player_ids.
    """
    current = None
    for ev in events:
        if ev.event_type == "period_start":
            current = list(ev.payload.get("lineup") or [])
        elif ev.event_type == "sub":
            current = list(ev.payload.get("lineup") or [])
        elif ev.event_type == "period_end":
            current = None
    if current is None:
        return list(draft_lineup or [])
    return current


def compute_stints_and_minutes(game, events=None):
    """
    Replays events to calculate exact playing stints and total seconds played for each player.
    Returns:
    - stints: list of BkmStint
    - player_seconds: dict {player_id: total_seconds}
    - period_player_seconds: dict {(player_id, period): seconds}
    """
    events = ordered_events(game, events)
    stints = []
    
    # Active players tracking: player_id -> (period, start_rem_sec)
    active = {}
    period_start_sec = game.period_minutes * 60

    for ev in events:
        if ev.event_type == "period_start":
            active.clear()
            p_sec = int(ev.payload.get("period_seconds") or (game.period_minutes * 60))
            period_start_sec = p_sec
            lineup = ev.payload.get("lineup") or []
            for pid in lineup:
                active[int(pid)] = (ev.period, p_sec)
                
        elif ev.event_type == "sub":
            rem_sec = int(ev.remaining_seconds)
            new_lineup = set(int(x) for x in (ev.payload.get("lineup") or []))
            curr_active_ids = set(active.keys())
            
            # Players subbed off
            subbed_off = curr_active_ids - new_lineup
            for pid in subbed_off:
                start_p, start_rem = active.pop(pid)
                dur = max(0, start_rem - rem_sec)
                stints.append(BkmStint(player_id=pid, period=start_p, start_rem_sec=start_rem, end_rem_sec=rem_sec, duration_sec=dur))
                
            # Players subbed on
            subbed_on = new_lineup - curr_active_ids
            for pid in subbed_on:
                active[pid] = (ev.period, rem_sec)
                
        elif ev.event_type == "period_end":
            rem_sec = int(ev.remaining_seconds)
            for pid, (start_p, start_rem) in list(active.items()):
                dur = max(0, start_rem - rem_sec)
                stints.append(BkmStint(player_id=pid, period=start_p, start_rem_sec=start_rem, end_rem_sec=rem_sec, duration_sec=dur))
            active.clear()

    player_seconds = defaultdict(int)
    period_player_seconds = defaultdict(int)

    for stint in stints:
        player_seconds[stint.player_id] += stint.duration_sec
        period_player_seconds[(stint.player_id, stint.period)] += stint.duration_sec

    return stints, player_seconds, period_player_seconds


def compute_scoring(game, events=None):
    """
    Computes points and shooting stats from score events.
    Returns:
    - total_points: int
    - player_stats: dict of player_id -> {
        'points': int,
        'fg2_made': int,
        'fg3_made': int,
        'ft_made': int,
        'ft_miss': int,
        'ft_att': int,
        'period_points': defaultdict(int)
      }
    """
    events = ordered_events(game, events)
    total_points = 0
    player_stats = defaultdict(lambda: {
        "points": 0,
        "fg2_made": 0,
        "fg3_made": 0,
        "ft_made": 0,
        "ft_miss": 0,
        "ft_att": 0,
        "period_points": defaultdict(int),
    })

    for ev in events:
        if ev.event_type == "score":
            pid = int(ev.payload.get("player_id"))
            shot_type = ev.payload.get("shot_type")
            pts = int(ev.payload.get("points") or 0)
            
            total_points += pts
            p = player_stats[pid]
            p["points"] += pts
            p["period_points"][ev.period] += pts
            
            if shot_type == "1pt":
                p["ft_made"] += 1
                p["ft_att"] += 1
            elif shot_type == "miss_ft":
                p["ft_miss"] += 1
                p["ft_att"] += 1
            elif shot_type == "2pt":
                p["fg2_made"] += 1
            elif shot_type == "3pt":
                p["fg3_made"] += 1

    return total_points, player_stats


def get_game_roster(game):
    """
    Returns list of (player, is_present) ordered by player sort_order.
    """
    players = BkmPlayer.query.filter_by(team_id=game.team_id).order_by(BkmPlayer.sort_order, BkmPlayer.id).all()
    entries = {
        re.player_id: re.is_present
        for re in BkmGameRosterEntry.query.filter_by(game_id=game.id).all()
    }
    return [(p, entries.get(p.id, True)) for p in players]


def last_event_time(game, events=None):
    """Returns the last known remaining_seconds from the active period, or default period seconds."""
    events = ordered_events(game, events)
    if not events:
        return game.period_minutes * 60
    
    # Filter for events in current period
    curr_events = [e for e in events if e.period == game.current_period]
    if not curr_events:
        return game.period_minutes * 60
    
    last = curr_events[-1]
    if last.event_type == "period_start":
        return int(last.payload.get("period_seconds") or (game.period_minutes * 60))
    return int(last.remaining_seconds)
