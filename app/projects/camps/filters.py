from collections import defaultdict
from sqlalchemy import and_, or_, func, false
from app.projects.camps.age_grade_bridge import (
    session_matches_age_filter,
    session_matches_grade_filter,
)
from app.projects.camps.models import Camp, CampSession, CampTag, CampTagCategory, camps_camp_tag
from app.projects.camps.session_schedule import typical_inclusive_days
from app.projects.camps.session_times import (
    END_AFTER_OPTIONS,
    START_BEFORE_OPTIONS,
    session_matches_time_filters,
)
from datetime import date, timedelta

def apply_filters(query, params):
    """
    Applies filters to a Camp query based on URL parameters.
    Returns the filtered query.
    """
    # 1. Town Filter (OR within facet)
    towns = params.getlist('town')
    if towns:
        query = query.filter(Camp.city.in_(towns))

    # 2. Tag Filters (OR within category, AND across categories)
    # We need to find all categories that have at least one tag selected
    categories = CampTagCategory.query.all()
    for cat in categories:
        tag_ids = params.getlist(f'tag_{cat.id}')
        if tag_ids:
            # Camp must have at least one of these tags
            query = query.filter(Camp.tags.any(CampTag.id.in_(tag_ids)))

    # 3. Age and Grade filters
    # Union across facets: if both age and grade params are set, a session qualifies if it
    # matches EITHER facet (same as before).
    # Within each facet, we match direct ranges and bridge to the other field when missing
    # (approximate mapping in age_grade_bridge.py).
    age_min = params.get("age_min", type=int)
    age_max = params.get("age_max", type=int)
    grade_min = params.get("grade_min", type=int)
    grade_max = params.get("grade_max", type=int)

    has_age_facet = age_min is not None or age_max is not None
    has_grade_facet = grade_min is not None or grade_max is not None

    if has_age_facet or has_grade_facet:

        def session_ok(s):
            parts = []
            if has_age_facet:
                parts.append(session_matches_age_filter(s, age_min, age_max))
            if has_grade_facet:
                parts.append(session_matches_grade_filter(s, grade_min, grade_max))
            return any(parts)

        matching_ids = {s.camp_id for s in CampSession.query.all() if session_ok(s)}
        if not matching_ids:
            query = query.filter(false())
        else:
            query = query.filter(Camp.id.in_(matching_ids))

    # 4. Week Filter (OR within facet)
    week_mondays = params.getlist('week')
    if week_mondays:
        week_conditions = []
        for monday_str in week_mondays:
            try:
                monday_date = date.fromisoformat(monday_str)
                sunday_date = monday_date + timedelta(days=6)
                
                # Session overlaps [monday, sunday]
                # Overlap: max(s.start, w.start) <= min(s.end, w.end)
                week_cond = and_(
                    func.greatest(CampSession.start_date, monday_date) <= func.least(CampSession.end_date, sunday_date)
                )
                week_conditions.append(week_cond)
            except ValueError:
                continue
        
        if week_conditions:
            query = query.filter(Camp.sessions.any(or_(*week_conditions)))

    # 5. Time filter (same session must meet start-before and/or end-after when both set)
    start_key = params.get("start_before")
    end_key = params.get("end_after")
    sb_mins = START_BEFORE_OPTIONS.get(start_key) if start_key else None
    ea_mins = END_AFTER_OPTIONS.get(end_key) if end_key else None

    if sb_mins is not None or ea_mins is not None:
        session_query = CampSession.query
        if sb_mins is not None:
            session_query = session_query.filter(CampSession.start_time.isnot(None))
        if ea_mins is not None:
            session_query = session_query.filter(CampSession.end_time.isnot(None))

        matching_camp_ids = {
            s.camp_id
            for s in session_query.all()
            if session_matches_time_filters(s, sb_mins, ea_mins)
        }
        if not matching_camp_ids:
            query = query.filter(false())
        else:
            query = query.filter(Camp.id.in_(matching_camp_ids))

    # 6. Typical days per session block (mode of inclusive day count; 4 = e.g. Mon–Thu, 5 = Mon–Fri)
    week_days = params.get("week_days")
    if week_days in ("4", "5"):
        target = int(week_days)
        by_camp = defaultdict(list)
        for s in CampSession.query.all():
            by_camp[s.camp_id].append(s)
        matching_camp_ids = {
            cid
            for cid, sessions in by_camp.items()
            if typical_inclusive_days(sessions) == target
        }
        if not matching_camp_ids:
            query = query.filter(false())
        else:
            query = query.filter(Camp.id.in_(matching_camp_ids))

    return query
