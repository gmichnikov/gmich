"""Curated water bodies. Polygons come later; this list is the catalog users pick from."""

from app.projects.been.parsing import VisitInputError

ACTIVITIES = (
    ("swam", "Swam"),
    ("boated", "Boated"),
    ("ferry", "Ferry"),
    ("dived", "Dived"),
    ("sailed", "Sailed"),
)

ACTIVITY_LABELS = dict(ACTIVITIES)

_KIND_LABELS = (
    ("ocean", "Oceans"),
    ("sea", "Seas, gulfs, and bays"),
    ("lake", "Lakes"),
    ("river", "Rivers"),
)


def _bodies(kind, pairs):
    return [{"slug": slug, "name": name, "kind": kind} for slug, name in pairs]


WATER_BODIES = [
    *_bodies(
        "ocean",
        [
            ("arctic-ocean", "Arctic Ocean"),
            ("atlantic-ocean", "Atlantic Ocean"),
            ("indian-ocean", "Indian Ocean"),
            ("pacific-ocean", "Pacific Ocean"),
            ("southern-ocean", "Southern Ocean"),
        ],
    ),
    *_bodies(
        "sea",
        [
            ("adriatic-sea", "Adriatic Sea"),
            ("aegean-sea", "Aegean Sea"),
            ("andaman-sea", "Andaman Sea"),
            ("arabian-sea", "Arabian Sea"),
            ("balearic-sea", "Balearic Sea"),
            ("baltic-sea", "Baltic Sea"),
            ("barents-sea", "Barents Sea"),
            ("barnegat-bay", "Barnegat Bay"),
            ("beaufort-sea", "Beaufort Sea"),
            ("bering-sea", "Bering Sea"),
            ("black-sea", "Black Sea"),
            ("caribbean-sea", "Caribbean Sea"),
            ("caspian-sea", "Caspian Sea"),
            ("chesapeake-bay", "Chesapeake Bay"),
            ("coral-sea", "Coral Sea"),
            ("dead-sea", "Dead Sea"),
            ("delaware-bay", "Delaware Bay"),
            ("east-china-sea", "East China Sea"),
            ("english-channel", "English Channel"),
            ("gulf-of-alaska", "Gulf of Alaska"),
            ("gulf-of-california", "Gulf of California"),
            ("gulf-of-maine", "Gulf of Maine"),
            ("gulf-of-mexico", "Gulf of Mexico"),
            ("hudson-bay", "Hudson Bay"),
            ("ionian-sea", "Ionian Sea"),
            ("irish-sea", "Irish Sea"),
            ("labrador-sea", "Labrador Sea"),
            ("ligurian-sea", "Ligurian Sea"),
            ("long-island-sound", "Long Island Sound"),
            ("mediterranean-sea", "Mediterranean Sea"),
            ("north-sea", "North Sea"),
            ("norwegian-sea", "Norwegian Sea"),
            ("persian-gulf", "Persian Gulf"),
            ("philippine-sea", "Philippine Sea"),
            ("puget-sound", "Puget Sound"),
            ("raritan-bay", "Raritan Bay"),
            ("red-sea", "Red Sea"),
            ("san-francisco-bay", "San Francisco Bay"),
            ("sea-of-japan", "Sea of Japan"),
            ("south-china-sea", "South China Sea"),
            ("tasman-sea", "Tasman Sea"),
            ("tyrrhenian-sea", "Tyrrhenian Sea"),
            ("bay-of-bengal", "Bay of Bengal"),
        ],
    ),
    *_bodies(
        "lake",
        [
            ("crater-lake", "Crater Lake"),
            ("great-salt-lake", "Great Salt Lake"),
            ("lake-baikal", "Lake Baikal"),
            ("lake-champlain", "Lake Champlain"),
            ("lake-como", "Lake Como"),
            ("lake-constance", "Lake Constance"),
            ("lake-erie", "Lake Erie"),
            ("lake-garda", "Lake Garda"),
            ("lake-geneva", "Lake Geneva"),
            ("lake-huron", "Lake Huron"),
            ("lake-lucerne", "Lake Lucerne"),
            ("lake-maggiore", "Lake Maggiore"),
            ("lake-mead", "Lake Mead"),
            ("lake-michigan", "Lake Michigan"),
            ("lake-ontario", "Lake Ontario"),
            ("lake-powell", "Lake Powell"),
            ("lake-superior", "Lake Superior"),
            ("lake-tahoe", "Lake Tahoe"),
            ("lake-titicaca", "Lake Titicaca"),
            ("lake-victoria", "Lake Victoria"),
            ("loch-ness", "Loch Ness"),
            ("sea-of-galilee", "Sea of Galilee"),
        ],
    ),
    *_bodies(
        "river",
        [
            ("amazon-river", "Amazon River"),
            ("colorado-river", "Colorado River"),
            ("columbia-river", "Columbia River"),
            ("congo-river", "Congo River"),
            ("danube-river", "Danube"),
            ("delaware-river", "Delaware River"),
            ("douro-river", "Douro"),
            ("ganges-river", "Ganges"),
            ("hudson-river", "Hudson River"),
            ("loire-river", "Loire"),
            ("mekong-river", "Mekong"),
            ("mississippi-river", "Mississippi River"),
            ("missouri-river", "Missouri River"),
            ("nile-river", "Nile"),
            ("ohio-river", "Ohio River"),
            ("potomac-river", "Potomac River"),
            ("rhine-river", "Rhine"),
            ("rio-grande", "Rio Grande"),
            ("seine-river", "Seine"),
            ("st-lawrence-river", "St. Lawrence River"),
            ("tagus-river", "Tagus"),
            ("thames-river", "River Thames"),
            ("tiber-river", "Tiber"),
            ("yangtze-river", "Yangtze"),
        ],
    ),
]

WATER_BY_SLUG = {body["slug"]: body for body in WATER_BODIES}


def water_groups():
    groups = []
    for kind, label in _KIND_LABELS:
        items = sorted(
            (body for body in WATER_BODIES if body["kind"] == kind),
            key=lambda body: body["name"],
        )
        groups.append({"kind": kind, "label": label, "bodies": items})
    return groups


def water_name(slug):
    if not slug:
        return ""
    body = WATER_BY_SLUG.get(slug)
    return body["name"] if body else slug


def activity_label(code):
    if not code:
        return ""
    return ACTIVITY_LABELS.get(code, code)


def clean_water_slug(raw):
    slug = (raw or "").strip()
    if not slug:
        return None
    if slug not in WATER_BY_SLUG:
        raise VisitInputError("Pick a body of water from the list.")
    return slug


def clean_activity(raw):
    code = (raw or "").strip().lower()
    if not code:
        return None
    if code not in ACTIVITY_LABELS:
        raise VisitInputError("Pick an activity from the list.")
    return code
