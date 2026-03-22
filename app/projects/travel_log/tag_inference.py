"""
Infer Travel Log global tag *names* from Google Places `types` and `primaryType`.

Only tag names that exist as `TlogTag` (scope=global) should be applied at create time.
If you rename or remove a tag in admin, update the sets below or entries will stop
getting that tag until the name matches again.

See docs in repo: sample_20260321*.json for real `types` arrays.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

# Canonical DB tag names (must match TlogTag.name for global tags)
TAG_FOOD = "food"
TAG_LODGING = "lodging"
TAG_OUTDOORS = "outdoors"
TAG_SHOP = "shop"
TAG_SIGHT = "sight"

_FOOD_EXACT = frozenset(
    {
        "food",
        "restaurant",
        "cafe",
        "bar",
        "bakery",
        "meal_takeaway",
        "meal_delivery",
        "coffee_shop",
        "ice_cream_shop",
        "pub",
        "winery",
        "brunch_restaurant",
        "fast_food_restaurant",
        "fine_dining_restaurant",
        "food_court",
        "grocery_store",
        "liquor_store",
    }
)

_LODGING_EXACT = frozenset(
    {
        "lodging",
        "hotel",
        "motel",
        "hostel",
        "resort_hotel",
        "bed_and_breakfast",
        "extended_stay_hotel",
    }
)

_OUTDOORS_EXACT = frozenset(
    {
        "park",
        "national_park",
        "state_park",
        "playground",
        "campground",
        "beach",
        "hiking_area",
        "rv_park",
        "marina",
        "athletic_field",
        "sports_complex",
        "stadium",
        "golf_course",
        "ski_resort",
        "dog_park",
        "natural_feature",
        "mountain_peak",
        "fishing_pier",
    }
)

_SHOP_EXACT = frozenset(
    {
        "store",
        "shopping_mall",
        "supermarket",
        "convenience_store",
        "market",
        "home_goods_store",
        "hardware_store",
        "clothing_store",
        "book_store",
        "shoe_store",
        "electronics_store",
        "furniture_store",
        "jewelry_store",
        "department_store",
        "gift_shop",
        "shopping_center",
    }
)

_SIGHT_EXACT = frozenset(
    {
        "tourist_attraction",
        "museum",
        "art_gallery",
        "historical_landmark",
        "monument",
        "church",
        "place_of_worship",
        "hindu_temple",
        "mosque",
        "synagogue",
        "library",
        "city_hall",
        "bridge",
        "observation_deck",
        "castle",
        "amusement_park",
        "zoo",
        "aquarium",
        "tourist_information_center",
        "cultural_center",
        "performing_arts_theater",
        "opera_house",
    }
)

def parse_google_types_from_request(data: Mapping[str, Any]) -> list[str]:
    """Read `google_types` from form (JSON string) or JSON body (list)."""
    raw = data.get("google_types")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(x).strip() for x in parsed if x is not None and str(x).strip()]
    return []


def _collect_type_strings(google_types: list[str], primary_type: str | None) -> set[str]:
    types_set = {t for t in google_types if t}
    if primary_type:
        pt = str(primary_type).strip()
        if pt:
            types_set.add(pt)
    return types_set


def infer_tag_names_from_google_place(
    google_types: list[str],
    primary_type: str | None,
) -> frozenset[str]:
    """
    Return canonical tag names (food, lodging, outdoors, shop, sight) to try on the entry.
    Multiple tags are allowed. Unknown / unmapped types yield an empty contribution.
    """
    types_set = _collect_type_strings(google_types, primary_type)
    if not types_set:
        return frozenset()

    out: set[str] = set()

    def has_food() -> bool:
        for t in types_set:
            if t in _FOOD_EXACT:
                return True
            if t.endswith("_restaurant"):
                return True
            if t.endswith("_cafe") and t != "cafe":
                return True
        return False

    def has_lodging() -> bool:
        return bool(types_set & _LODGING_EXACT)

    def has_outdoors() -> bool:
        return bool(types_set & _OUTDOORS_EXACT)

    def has_shop() -> bool:
        for t in types_set:
            if t in _SHOP_EXACT:
                return True
            if t.endswith("_store") and t not in _FOOD_EXACT:
                # e.g. book_store, clothing_store; not grocery_store (food)
                return True
        return False

    def has_sight() -> bool:
        for t in types_set:
            if t in _SIGHT_EXACT:
                return True
        return False

    if has_food():
        out.add(TAG_FOOD)
    if has_lodging():
        out.add(TAG_LODGING)
    if has_outdoors():
        out.add(TAG_OUTDOORS)
    if has_shop():
        out.add(TAG_SHOP)
    if has_sight():
        out.add(TAG_SIGHT)

    return frozenset(out)
