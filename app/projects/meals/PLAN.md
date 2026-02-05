# Meals Project - Implementation Plan

This plan follows the PRD but breaks it into smaller, testable chunks, mirroring the successful structure used in other projects in this repo.

---

## Phase 1: Foundations & Sharing

### 1.1 Database Model Setup
- [ ] Create `MealsFamilyGroup` model in `models.py`
  - [ ] Fields: `id`, `name`, `created_at`
- [ ] Create `MealsFamilyMember` model in `models.py`
  - [ ] Fields: `id`, `family_group_id` (FK), `user_id` (FK, nullable), `display_name` (String), `created_at`
  - [ ] Add relationship to `MealsFamilyGroup`
  - [ ] Add relationship to `User` (backref `meals_memberships`)
- [ ] Update `app/__init__.py` to import these models for discovery by Flask-Migrate

**Manual Testing 1.1:**
- [ ] Run `flask db migrate -m "Add meals core models"`
- [ ] Run `flask db upgrade`
- [ ] Verify tables `meals_family_group` and `meals_family_member` exist in the database with correct schema.

### 1.2 Blueprints & Basic Routes
- [ ] Ensure `routes.py` is properly set up with the `meals_bp` blueprint.
- [ ] Create `forms.py` for Meals project forms.
  - [ ] `CreateFamilyGroupForm` (name)
  - [ ] `InviteMemberForm` (email)
  - [ ] `AddGuestMemberForm` (display_name)
- [ ] Create `utils.py` for helper functions.
  - [ ] `get_user_family_groups(user)`
  - [ ] `is_user_in_group(user, group_id)`
- [ ] Implement `GET /meals/` (Dashboard placeholder)
- [ ] Implement `POST /meals/groups/create`
  - [ ] Create group and add current user as the first linked member.
- [ ] Implement `POST /meals/groups/<int:group_id>/invite` (Link existing User)
  - [ ] Accept email, find user, create `MealsFamilyMember` linked to `user_id`.
- [ ] Implement `POST /meals/groups/<int:group_id>/members/add` (Add Guest Member)
  - [ ] Create `MealsFamilyMember` with only `display_name`.

**Manual Testing 1.2:**
- [ ] Create a group and verify it appears on your dashboard.
- [ ] Add a guest member (e.g., "Kid 1") and verify they show up in the member list.
- [ ] Invite another user by email and verify they can see the group when they log in.

---

## Phase 2: Basic Logging

### 2.1 Meals Entry Model
- [ ] Create `MealsEntry` model in `models.py`
  - [ ] Fields: `id`, `family_group_id` (FK), `member_id` (FK), `food_name`, `location`, `meal_type` (Enum: Breakfast, Lunch, Dinner), `date` (Date), `created_by_id` (FK to User), `created_at`
  - [ ] Add relationships to group and member.

**Manual Testing 2.1:**
- [ ] Run `flask db migrate -m "Add meals_entry model"`
- [ ] Run `flask db upgrade`
- [ ] Verify table `meals_entry` exists.

### 2.2 Individual Logging UI
- [ ] Create `LogMealForm` in `forms.py`
  - [ ] `date`, `meal_type`, `food_name`, `location`.
- [ ] Implement `POST /meals/log`
  - [ ] Save entry to DB.
- [ ] Update `templates/meals/index.html`
  - [ ] Add "Log a Meal" form.
  - [ ] Add "Recent History" list (last 10 entries for the family).
- [ ] Add `static/meals/style.css` (with `meals-` prefixes).

**Manual Testing 2.2:**
- [ ] Log a meal for yourself and verify it appears in the recent history.
- [ ] Verify the data is correctly saved in the DB.

---

## Phase 3: Bulk Logging & UI Polish

### 3.1 Bulk Member Selection
- [ ] Update `LogMealForm` to handle multiple member selections (using `SelectMultipleField` or custom checkboxes).
- [ ] Update `POST /meals/log` to iterate and create multiple `MealsEntry` records.
- [ ] UI: Add "Select All" / "Deselect All" buttons.

### 3.2 "Same as..." Shortcuts
- [ ] Implement a "Quick Copy" JS helper in `static/meals/script.js`.
- [ ] Add buttons to the UI to populate the form from another family member's last entry.

**Manual Testing 3.1 & 3.2:**
- [ ] Log a meal for three people at once and verify three separate records are created.
- [ ] Use the "Quick Copy" to fill the form and verify it works.

---

## Phase 4: Autocomplete & Smart History

### 4.1 Autocomplete API
- [ ] Implement `GET /meals/api/suggestions?query=...`
  - [ ] Return unique `food_name` and `location` pairs from the group's history.
- [ ] Integrate autocomplete on the `food_name` and `location` inputs.

### 4.2 Common Meals & Stats
- [ ] Implement the "Common Meals" table logic.
  - [ ] Query and group by food/location, count occurrences.
- [ ] Implement "Location Trends" (Home vs Out) calculations.
- [ ] Update dashboard with these new components.

**Manual Testing 4.1 & 4.2:**
- [ ] Type a meal name you've used before and verify it suggests the full name and location.
- [ ] Check that the "Common Meals" table correctly ranks your most frequent foods.

---

## Phase 5: Calendar Views

### 5.1 Weekly & Monthly Grids
- [ ] Implement `GET /meals/calendar` with `view=week` or `view=month`.
- [ ] Create `templates/meals/calendar.html`
- [ ] Weekly view: 7 columns, 3 rows (B, L, D).
- [ ] Monthly view: 5-week grid.
- [ ] Implement the "Family Overlay" (showing all members in the same cell).

**Manual Testing 5.1:**
- [ ] Verify that meals show up on the correct day and meal slot in both views.
- [ ] Toggle between views and verify navigation (Previous/Next week/month) works.

---

## Phase 6: Final Polishing
- [ ] Mobile Responsiveness: Ensure logging and calendar work on small screens.
- [ ] CSS Audit: Ensure all classes use the `meals-` prefix.
- [ ] Accessibility: Add proper labels and ARIA roles for the complex calendar grid.
