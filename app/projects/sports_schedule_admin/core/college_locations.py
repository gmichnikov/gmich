"""
Hardcoded mapping of college/university names to (city, state) for games where
ESPN does not provide venue address (e.g. men's college lacrosse).
Keys are matched case-insensitively against the start of team displayName.
Add entries as needed - expand from NCAA D1 lacrosse, hockey, soccer, baseball.
"""

# School name fragment (matches start of "Institution Mascot") -> (city, state)
# State must be 2-letter US code. Sort by key length desc for longest-match.
COLLEGE_LOCATIONS = {
    "United States Air Force Academy": ("USAF Academy", "CO"),
    "Air Force": ("USAF Academy", "CO"),
    "University at Albany": ("Albany", "NY"),
    "UAlbany": ("Albany", "NY"),
    "United States Military Academy": ("West Point", "NY"),
    "Army": ("West Point", "NY"),
    "Bellarmine": ("Louisville", "KY"),
    "Binghamton": ("Binghamton", "NY"),
    "Boston University": ("Boston", "MA"),
    "Brown": ("Providence", "RI"),
    "Bryant": ("Smithfield", "RI"),
    "Bucknell": ("Lewisburg", "PA"),
    "Canisius": ("Buffalo", "NY"),
    "Cleveland State": ("Cleveland", "OH"),
    "Colgate": ("Hamilton", "NY"),
    "Cornell": ("Ithaca", "NY"),
    "Dartmouth": ("Hanover", "NH"),
    "Delaware": ("Newark", "DE"),
    "University of Denver": ("Denver", "CO"),
    "Denver": ("Denver", "CO"),
    "University of Detroit Mercy": ("Detroit", "MI"),
    "Detroit Mercy": ("Detroit", "MI"),
    "Drexel": ("Philadelphia", "PA"),
    "Duke": ("Durham", "NC"),
    "Fairfield": ("Fairfield", "CT"),
    "Georgetown": ("Washington", "DC"),
    "Hampton": ("Hampton", "VA"),
    "Harvard": ("Cambridge", "MA"),
    "High Point": ("High Point", "NC"),
    "Hobart College": ("Geneva", "NY"),
    "Hofstra": ("Hempstead", "NY"),
    "College of the Holy Cross": ("Worcester", "MA"),
    "Holy Cross": ("Worcester", "MA"),
    "Iona": ("New Rochelle", "NY"),
    "Jacksonville": ("Jacksonville", "FL"),
    "Johns Hopkins University": ("Baltimore", "MD"),
    "Johns Hopkins": ("Baltimore", "MD"),
    "Lafayette": ("Easton", "PA"),
    "Lehigh": ("Bethlehem", "PA"),
    "Le Moyne": ("Syracuse", "NY"),
    "Long Island University": ("Brookville", "NY"),
    "Loyola Maryland": ("Baltimore", "MD"),
    "Loyola University Maryland": ("Baltimore", "MD"),
    "Manhattan": ("Riverdale", "NY"),
    "Marist": ("Poughkeepsie", "NY"),
    "Marquette": ("Milwaukee", "WI"),
    "University of Maryland": ("College Park", "MD"),
    "Maryland": ("College Park", "MD"),
    "UMBC": ("Catonsville", "MD"),
    "University of Massachusetts": ("Amherst", "MA"),
    "Massachusetts": ("Amherst", "MA"),
    "UMass Lowell": ("Lowell", "MA"),
    "Mercer": ("Macon", "GA"),
    "Mercyhurst": ("Erie", "PA"),
    "Merrimack": ("North Andover", "MA"),
    "University of Michigan": ("Ann Arbor", "MI"),
    "Michigan": ("Ann Arbor", "MI"),
    "Monmouth": ("West Long Branch", "NJ"),
    "Mount St. Mary's": ("Emmitsburg", "MD"),
    "United States Naval Academy": ("Annapolis", "MD"),
    "Navy": ("Annapolis", "MD"),
    "NJIT": ("Newark", "NJ"),
    "North Carolina": ("Chapel Hill", "NC"),
    "University of Notre Dame": ("Notre Dame", "IN"),
    "Notre Dame": ("Notre Dame", "IN"),
    "Ohio State": ("Columbus", "OH"),
    "University of Pennsylvania": ("Philadelphia", "PA"),
    "Pennsylvania": ("Philadelphia", "PA"),
    "Penn State": ("University Park", "PA"),
    "Princeton": ("Princeton", "NJ"),
    "Providence": ("Providence", "RI"),
    "Queens University": ("Charlotte", "NC"),
    "Quinnipiac": ("Hamden", "CT"),
    "Richmond": ("Richmond", "VA"),
    "Robert Morris": ("Moon Township", "PA"),
    "Rutgers": ("Piscataway", "NJ"),
    "Sacred Heart": ("Fairfield", "CT"),
    "St. Bonaventure": ("St. Bonaventure", "NY"),
    "St. John's": ("Jamaica", "NY"),
    "Saint Joseph's": ("Philadelphia", "PA"),
    "Siena": ("Loudonville", "NY"),
    "Stony Brook": ("Stony Brook", "NY"),
    "Syracuse": ("Syracuse", "NY"),
    "Towson": ("Towson", "MD"),
    "Utah": ("Salt Lake City", "UT"),
    "Vermont": ("Burlington", "VT"),
    "Villanova": ("Villanova", "PA"),
    "University of Virginia": ("Charlottesville", "VA"),
    "Virginia": ("Charlottesville", "VA"),
    "VMI": ("Lexington", "VA"),
    "Virginia Military Institute": ("Lexington", "VA"),
    "Wagner": ("Staten Island", "NY"),
    "Yale": ("New Haven", "CT"),
}

# Sorted by key length descending for longest-match
_SORTED_KEYS = sorted(COLLEGE_LOCATIONS.keys(), key=len, reverse=True)


def get_college_location(team_display_name: str):
    """
    Look up (city, state) for a college team when ESPN omits venue address.
    Matches team displayName (e.g. "Johns Hopkins University Blue Jays") against
    mapping keys. Returns (city, state) or (None, None) if no match.
    """
    if not team_display_name or not isinstance(team_display_name, str):
        return (None, None)
    name = team_display_name.strip()
    if not name:
        return (None, None)
    name_lower = name.lower()
    for key in _SORTED_KEYS:
        if name_lower.startswith(key.lower()):
            city, state = COLLEGE_LOCATIONS[key]
            return (city or "", state or "")
    return (None, None)
