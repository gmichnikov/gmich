"""Races inside 90/10 at the time this list was written.

This is a fixed list, not a live filter. A race that later moves to 95/5 stays
on the board. The event ticker is pinned because several series also contain a
later cycle or a party-only contract.

Maine is SENATEME-26 only. KXMESENATEPERSON-26 is the same race.
"""

TRACKED_RACES = [
    {
        "event_ticker": "GOVPARTYVT-26",
        "series_ticker": "GOVPARTYVT",
        "office": "governor",
        "state": "VT",
        "label": "Vermont Governor",
    },
    {
        "event_ticker": "GOVPARTYKS-27",
        "series_ticker": "GOVPARTYKS",
        "office": "governor",
        "state": "KS",
        "label": "Kansas Governor",
    },
    {
        "event_ticker": "GOVPARTYTX-26",
        "series_ticker": "GOVPARTYTX",
        "office": "governor",
        "state": "TX",
        "label": "Texas Governor",
    },
    {
        "event_ticker": "KXIASENATE-26",
        "series_ticker": "KXIASENATE",
        "office": "senate",
        "state": "IA",
        "label": "Iowa Senate",
    },
    {
        "event_ticker": "SENATESC-26",
        "series_ticker": "SENATESC",
        "office": "senate",
        "state": "SC",
        "label": "South Carolina Senate",
    },
    {
        "event_ticker": "GOVPARTYSC-26",
        "series_ticker": "GOVPARTYSC",
        "office": "governor",
        "state": "SC",
        "label": "South Carolina Governor",
    },
    {
        "event_ticker": "KXAKSENATE-26NOV03",
        "series_ticker": "KXAKSENATE",
        "office": "senate",
        "state": "AK",
        "label": "Alaska Senate",
    },
    {
        "event_ticker": "SENATEKS-26",
        "series_ticker": "SENATEKS",
        "office": "senate",
        "state": "KS",
        "label": "Kansas Senate",
    },
    {
        "event_ticker": "SENATEME-26",
        "series_ticker": "SENATEME",
        "office": "senate",
        "state": "ME",
        "label": "Maine Senate",
    },
    {
        "event_ticker": "SENATEMS-26",
        "series_ticker": "SENATEMS",
        "office": "senate",
        "state": "MS",
        "label": "Mississippi Senate",
    },
    {
        "event_ticker": "SENATETX-26",
        "series_ticker": "SENATETX",
        "office": "senate",
        "state": "TX",
        "label": "Texas Senate",
    },
    {
        "event_ticker": "GOVPARTYOR-26",
        "series_ticker": "GOVPARTYOR",
        "office": "governor",
        "state": "OR",
        "label": "Oregon Governor",
    },
    {
        "event_ticker": "KXSENATELA-26NOV",
        "series_ticker": "KXSENATELA",
        "office": "senate",
        "state": "LA",
        "label": "Louisiana Senate",
    },
    {
        "event_ticker": "KXMISENATE-26",
        "series_ticker": "KXMISENATE",
        "office": "senate",
        "state": "MI",
        "label": "Michigan Senate",
    },
    {
        "event_ticker": "GOVPARTYNV-26",
        "series_ticker": "GOVPARTYNV",
        "office": "governor",
        "state": "NV",
        "label": "Nevada Governor",
    },
    {
        "event_ticker": "GOVPARTYWI-26",
        "series_ticker": "GOVPARTYWI",
        "office": "governor",
        "state": "WI",
        "label": "Wisconsin Governor",
    },
    {
        "event_ticker": "GOVPARTYGA-26",
        "series_ticker": "GOVPARTYGA",
        "office": "governor",
        "state": "GA",
        "label": "Georgia Governor",
    },
    {
        "event_ticker": "GOVPARTYOH-26",
        "series_ticker": "GOVPARTYOH",
        "office": "governor",
        "state": "OH",
        "label": "Ohio Governor",
    },
    {
        "event_ticker": "GOVPARTYIA-26",
        "series_ticker": "GOVPARTYIA",
        "office": "governor",
        "state": "IA",
        "label": "Iowa Governor",
    },
    {
        "event_ticker": "SENATEOHS-26",
        "series_ticker": "SENATEOHS",
        "office": "senate",
        "state": "OH",
        "label": "Ohio Senate",
    },
]

TRACKED_BY_EVENT = {race["event_ticker"]: race for race in TRACKED_RACES}
