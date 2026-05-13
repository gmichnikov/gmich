from sqlalchemy import and_, or_, func, false
from app.projects.camps.models import Camp, CampSession, CampTag, CampTagCategory, camps_camp_tag
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

    # 3. Age and Grade Filters (Union Rule)
    # A camp qualifies if ANY of its sessions match (Age OR Grade)
    age_min = params.get('age_min', type=int)
    age_max = params.get('age_max', type=int)
    grade_min = params.get('grade_min', type=int)
    grade_max = params.get('grade_max', type=int)

    if any(v is not None for v in [age_min, age_max, grade_min, grade_max]):
        session_filters = []
        
        # Age overlap logic: max(low1, low2) <= min(high1, high2)
        # Here: max(session.age_min, filter_age_min) <= min(session.age_max, filter_age_max)
        if age_min is not None or age_max is not None:
            f_min = age_min if age_min is not None else 0
            f_max = age_max if age_max is not None else 100
            
            age_cond = and_(
                CampSession.age_min.isnot(None),
                CampSession.age_max.isnot(None),
                func.greatest(CampSession.age_min, f_min) <= func.least(CampSession.age_max, f_max)
            )
            session_filters.append(age_cond)
            
        # Grade overlap logic
        if grade_min is not None or grade_max is not None:
            f_min = grade_min if grade_min is not None else -1
            f_max = grade_max if grade_max is not None else 12
            
            grade_cond = and_(
                CampSession.grade_min.isnot(None),
                CampSession.grade_max.isnot(None),
                func.greatest(CampSession.grade_min, f_min) <= func.least(CampSession.grade_max, f_max)
            )
            session_filters.append(grade_cond)
            
        if session_filters:
            # Union rule: session matches Age OR Grade
            query = query.filter(Camp.sessions.any(or_(*session_filters)))

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

    return query
