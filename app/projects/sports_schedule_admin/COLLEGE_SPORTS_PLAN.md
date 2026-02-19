# College Sports Expansion Plan

## 1. Goal
Provide comprehensive schedule coverage for major college sports (Basketball, Hockey, Baseball, Soccer, etc.) by shifting from a date-based scoreboard pull to a team-based season sync.

## 2. Why the Existing Approach Fell Short
The existing approach relied on the ESPN Scoreboard API (`.../scoreboard?dates=YYYYMMDD`). 

- **Limited Coverage**: The scoreboard typically only returns games that ESPN has broadcast rights to or chooses to feature. On a typical Saturday in February, the API might return ~17 games, while there are actually 100+ D1 games being played.
- **Missing Data**: Many smaller conferences and teams are entirely absent from the scoreboard endpoint, leading to significant gaps in the `combined-schedule` table.

## 3. The New Approach: Team-Based Sync
Instead of asking "What is playing today?", we will ask "What is the full schedule for Team X?".

### Key Components
1. **Team Registry**: A new database table (`espn_college_teams`) to store team metadata.
   - Fields: `id` (internal), `espn_team_id` (string), `name` (display name), `sport` (e.g., `basketball`), `league_code` (e.g., `NCAAM`).
2. **Team Discovery**: A mechanism to fetch all teams for a given sport from ESPN and populate the registry.
   - Endpoint: `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams?limit=500`
3. **Season Sync**: Fetching the full season schedule for a specific team.
   - Endpoint: `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/schedule`
   - Syncs all games (past and future) for that team in one pass.
4. **Deduplication**: Matchups between two registered teams (e.g., Harvard vs Yale) will appear in both schedules. The existing `primary_key` logic (`{league}_{date}_{home}_vs_{road}`) will allow DoltHub to naturally deduplicate these during upsert.

## 4. Implementation Phases

### Phase 1: Team Discovery & Cleanup
- **Clean Slate Policy**: Before the first team-based sync for a college league (NCAAM, NCB, NCHM, etc.), it is recommended to clear existing data for that league to ensure 100% consistency with the new comprehensive naming and metadata.
- Create the `ESPNCollegeTeam` database model in `app/models.py` to store metadata (`espn_team_id`, `name`, `abbreviation`, `sport`, `league_code`, `last_synced_at`).
- Add a CLI command: `flask sports-admin sync-teams --league <LEAGUE_CODE>` to populate the registry from ESPN.
- Integrate into the **Operations** tab:
    - Add a "Discover Teams" button for supported college leagues.
    - Add a "Sync Mode" toggle: "Date Range" (Scoreboard) or "By Team" (Full Season).
    - When "By Team" is selected, replace date inputs with a searchable "Team" dropdown.

### Phase 2: Team Schedule Sync
- Implement `ESPNClient.fetch_team_schedule(team_id, league_code)`.
- Reuse/adapt the `_parse_events` logic to handle the team-specific schedule payload.
- Update the **Operations** UI:
    - Provide a "Sync Full Season" button for the selected team.
- Add a CLI command: `flask sports-admin sync-team --team-id <ID> --league <LEAGUE>`.

### Phase 3: Bulk/Automatic Sync
- Capability to select multiple teams or an entire conference for bulk syncing in the UI.
- Background tasks to refresh "featured" or "active" teams periodically.
- Add "Last Synced" status to the team selection UI to identify stale data.

## 5. Known Compatible Sports
The following sports have been verified to work with the `.../teams` and `.../schedule` patterns:

| Sport | ESPN Path Slug | League Code | Verified Teams URL |
|-------|----------------|-------------|--------------------|
| Men's College Basketball | `basketball/mens-college-basketball` | `NCAAM` | [Link](https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=500) |
| Men's College Hockey | `hockey/mens-college-hockey` | `NCHM` | [Link](https://site.api.espn.com/apis/site/v2/sports/hockey/mens-college-hockey/teams?limit=100) |
| College Baseball | `baseball/college-baseball` | `NCB` | [Link](https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/teams?limit=500) |
| Men's College Soccer | `soccer/usa.ncaa.m.1` | `NCSM` | [Link](https://site.api.espn.com/apis/site/v2/sports/soccer/usa.ncaa.m.1/teams?limit=500) |

*Note: Women's variants (NCAAW, NCHW, NCSW) likely follow the same pattern (e.g., `womens-college-basketball`, `usa.ncaa.w.1`).*
