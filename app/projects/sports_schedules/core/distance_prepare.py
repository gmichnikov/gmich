"""
Shared distance filter setup for /api/query and weekly digest execution.

Distance uses zip + radius from request params or from saved config ``filters.near``.
"""
from dataclasses import dataclass

from app.projects.sports_schedules.core.geocode import (
    filter_rows_by_distance,
    nearby_states,
    zip_to_coords,
)


@dataclass(frozen=True)
class DistancePrepareResult:
    distance_filter_active: bool
    user_coords: tuple[float, float] | None
    radius_miles: float | None
    extra_dims: list[str]
    error: str | None
    """Set when zip is missing from DB; caller should surface as query error."""
    early_empty: bool
    """True when no candidate states / empty intersection — skip SQL, return no rows."""


def prepare_distance_filter(params: dict) -> DistancePrepareResult:
    """
    Resolve zip + radius from top-level keys or ``filters.near``, mutate ``params``
    for build_sql (home_state prefilter, dimensions, include_international), and
    remove ``filters.near`` when consumed.

    Caller must run build_sql only when ``error`` is None and ``early_empty`` is False.
    """
    filters = params.setdefault("filters", {})

    zip_code = str(params.pop("zip_code", "") or "").strip()
    radius_raw = params.pop("radius_miles", None)

    if not zip_code or radius_raw is None or radius_raw == "":
        near = filters.get("near")
        if isinstance(near, dict):
            zip_code = str(near.get("zip") or "").strip()
            radius_raw = near.get("radius")
        if "near" in filters:
            del filters["near"]

    try:
        radius_miles = (
            float(radius_raw)
            if radius_raw is not None and str(radius_raw).strip() != ""
            else None
        )
    except (TypeError, ValueError):
        radius_miles = None

    if not zip_code or radius_miles is None or radius_miles <= 0:
        return DistancePrepareResult(
            False, None, None, [], None, False
        )

    user_coords = zip_to_coords(zip_code)
    if user_coords is None:
        return DistancePrepareResult(
            False, None, None, [], f"Zip code '{zip_code}' not found.", False
        )

    states = nearby_states(user_coords[0], user_coords[1], radius_miles)
    if not states:
        return DistancePrepareResult(
            True, user_coords, radius_miles, [], None, True
        )

    user_states = filters.get("home_state", [])
    if user_states:
        state_set = set(user_states)
        states = [s for s in states if s in state_set]
        if not states:
            return DistancePrepareResult(
                True, user_coords, radius_miles, [], None, True
            )

    filters["home_state"] = states
    params["include_international"] = True

    extra_dims: list[str] = []
    if not params.get("count"):
        raw_dims = params.get("dimensions", "")
        if isinstance(raw_dims, str):
            dims_list = [d.strip() for d in raw_dims.split(",") if d.strip()]
        else:
            dims_list = list(raw_dims or [])
        for col in ("home_city", "home_state"):
            if col not in dims_list:
                dims_list.append(col)
                extra_dims.append(col)
        params["dimensions"] = ",".join(dims_list)

    return DistancePrepareResult(
        True, user_coords, radius_miles, extra_dims, None, False
    )


def apply_post_sql_distance(
    rows: list,
    params: dict,
    dpr: DistancePrepareResult,
) -> list:
    """Python-side distance filter and strip helper dimensions (matches /api/query)."""
    if dpr.early_empty or dpr.error or not dpr.distance_filter_active:
        return rows
    if (
        dpr.user_coords
        and dpr.radius_miles is not None
        and not params.get("count")
    ):
        rows = filter_rows_by_distance(
            rows,
            dpr.user_coords[0],
            dpr.user_coords[1],
            dpr.radius_miles,
        )
    if dpr.extra_dims:
        rows = [
            {k: v for k, v in row.items() if k not in dpr.extra_dims} for row in rows
        ]
    return rows
