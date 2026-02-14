# Meals Project - Product Requirements Document

## Overview
The Meals project is a family-oriented food tracker designed to help families log what each member eats for the three primary meals of the day (Breakfast, Lunch, Dinner). It focuses on simplicity, collaboration, and easy data entry for recurring meals.

## Project Details
- **Project name:** `meals`
- **Route prefix:** `/meals`
- **CSS prefix:** `meals-` (all classes must use this prefix)
- **Database tables:** Prefixed with `meals_`
- **Authentication:** Required
- **Data ownership:** Shared within a "Family Group"

## Goals
1. Provide a shared space for families to track individual meal consumption.
2. Enable easy discovery and logging of previously eaten meals to reduce manual entry.
3. Facilitate seamless collaboration between family members via simple email-based sharing.
4. Maintain a clean, mobile-friendly UI for quick logging on the go.

## User Stories
1. **As a user**, I want to create a family group so I can start tracking meals with my household.
2. **As a user**, I want to invite family members by email so they can automatically see and edit our shared tracker.
3. **As a user**, I want to log what I ate for Breakfast, Lunch, or Dinner, including the food name and location.
4. **As a user**, I want to quickly log the same meal for multiple family members at once since we often eat together.
5. **As a user**, I want to see a history of what we've eaten to identify patterns or remember good meals.
6. **As a user**, I want to select from previously entered meals using autocomplete or a "recents" list to save time.
7. **As a user**, I want to see a table of our most common meals (for myself or the whole family) to see what we eat most often.
8. **As a user**, I want to view a calendar (weekly or monthly) of our meals to see our eating history in a structured way.

## Functional Requirements

### 1. Family Group Management
- **Creation**: Any authenticated user can create a "Family Group".
- **Family Members**: Within a group, users can add "Members".
  - **Linked Members**: Members who have their own account on the site (linked via email).
  - **Guest Members**: Members who do not have an account (e.g., young children, pets). These only have a `display_name`.
- **Sharing**: Users can invite others to their group by entering the other person's email address.
- **Automatic Access**: If the invited email matches an existing user, that user automatically gains access to the group.
- **Permissions & Lifecycle**:
  - **Flat Permissions**: Every member linked to a `User` account has full permissions to log, edit, or invite others within that group.
  - **No Exit/Deletion**: Once a user is added to a group, they cannot leave it (in V1). Groups cannot be deleted.
  - **Access Control**: Users must be denied access to any page or API endpoint for a group they are not a member of.

### 2. Meal Logging
- **The "Big Three"**: Logging is restricted to Breakfast, Lunch, and Dinner.
- **Bulk Logging (Primary Entry Method)**: Instead of logging per-person and then "copying," the primary UI for adding a meal involves:
  1. Selecting the Date and Meal Type (B, L, or D).
  2. Selecting one or more Family Members from the group.
  3. Entering the Food and Location.
  4. Upon saving, individual `meals_entry` records are created for each selected member.
- **Fields**:
  - `food_name` (String, required)
  - `location` (String, required, e.g., "Home", "Italian Restaurant", "School")
  - `date` (Date)
  - `meal_type` (Enum: Breakfast, Lunch, Dinner)

### 3. Smart Entry & History
- **Dual Autocomplete**: 
  - The `food_name` field provides suggestions based only on the unique food names logged in that family group's history.
  - The `location` field provides suggestions based only on the unique locations logged in that family group's history.
- **Common Meals View**: A table showing the most frequently logged meals.
  - **Filters**: Single family member or the entire family.
  - **Data**: Shows the food name, location, and total count of occurrences.
- **Calendar View**: A visual grid showing logged meals over time.
  - **Timeframes**: Toggle between Weekly and Monthly views.
  - **Filters**: Single family member or "Family View" (merged view of all members).
- **Location Trends**: Basic stats on "Home" vs. "Eating Out" frequency.

### 4. UI/UX Considerations
- **Prefixing**: All CSS classes must use the `meals-` prefix to avoid collisions.
- **Mobile First**: The primary use case is likely logging immediately after eating, so the interface must be highly responsive.
- **Quick-Copy**: A button to "Copy yesterday's breakfast" or "Same as [Family Member]" for the current meal.

## Data Model

### meals_family_group
- `id` (PK)
- `name` (String)
- `created_at` (Timestamp)

### meals_family_member
- `id` (PK)
- `family_group_id` (FK to meals_family_group)
- `user_id` (FK to User, nullable) - Linked account for this member
- `display_name` (String) - Name used for logging (e.g., "Dad", "Kid 1")
- `created_at` (Timestamp)

### meals_entry
- `id` (PK)
- `family_group_id` (FK to meals_family_group)
- `member_id` (FK to meals_family_member) - The person who ate the meal
- `food_name` (String)
- `location` (String)
- `meal_type` (Enum: Breakfast, Lunch, Dinner)
- `date` (Date)
- `created_by_id` (FK to User) - The person who recorded the entry
- `created_at` (Timestamp)

## Implementation Phases

### Phase 1: Foundations & Sharing
- Create database models for Family Groups and Members.
- Implement the "Create Group" and "Invite by Email" functionality.
- Set up the basic project dashboard showing your family group(s).
- *Testing*: Create a group and verify that inviting another user's email makes the group appear in their account.

### Phase 2: Basic Logging
- Implement the meal entry form for individual logging.
- Add the `meals_entry` model and basic list view of recent logs.
- *Testing*: Log a meal for yourself and verify it appears in the family history.

### Phase 3: Bulk Logging & UI Polish
- Add the ability to select multiple family members in the logging form.
- Implement the "Same as..." or "Copy from..." shortcuts.
- *Testing*: Log a single meal for three people at once and verify three separate database records are created.

### Phase 4: Autocomplete & Smart History
- Implement autocomplete for the food and location fields based on family history.
- Build the "Common Meals" table with member/family filtering.
- Implement the "Location Trends" (Home vs. Out) stats.
- *Testing*: Verify common meals are calculated correctly and filters work.

### Phase 5: Calendar Views
- Build the Weekly and Monthly calendar views.
- Implement the "Family Overlay" logic for the calendar.
- *Testing*: Ensure meals appear on the correct dates and the toggle between week/month is seamless.

## Success Metrics
- Average time to log a meal is under 10 seconds.
- High rate of "reused" meal entries vs. unique strings.

## Out of Scope
- Nutritional/Calorie tracking.
- Recipe storage or ingredient lists.
- Grocery list integration.
- Snacks or custom meal types.
