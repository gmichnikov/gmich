# Meals Project - Implementation Plan

This plan follows the PRD but breaks it into smaller, testable chunks, mirroring the successful structure used in other projects in this repo.

---

## Phase 1: Foundations & Sharing

### 1.1 Database Model Setup
- [x] Create `MealsFamilyGroup` model in `models.py`
- [x] Create `MealsFamilyMember` model in `models.py`
- [x] Update `app/__init__.py` to import these models for discovery by Flask-Migrate

**Manual Testing 1.1:**
- [x] Run `flask db migrate -m "Add meals core models"`
- [x] Run `flask db upgrade`
- [x] Verify tables `meals_family_group` and `meals_family_member` exist in the database with correct schema.

### 1.2 Blueprints & Basic Routes
- [x] Ensure `routes.py` is properly set up with the `meals_bp` blueprint.
- [x] Create `forms.py` for Meals project forms.
- [x] Create `utils.py` for helper functions.
- [x] Implement `GET /meals/` (Dashboard placeholder)
- [x] Implement `POST /meals/groups/create`
- [x] Implement `POST /meals/groups/<int:group_id>/invite` (Link existing User)
- [x] Implement `POST /meals/groups/<int:group_id>/members/add` (Add Guest Member)

**Manual Testing 1.2:**
- [x] Create a group and verify it appears on your dashboard.
- [x] Add a guest member (e.g., "Kid 1") and verify they show up in the member list.
- [x] Invite another user by email and verify they can see the group when they log in.
- [x] **Security Test**: Try to access or invite to a group ID you are not a member of; verify it returns 404/Denied.

---

## Phase 2: Core Logging (Mobile-First)

### 2.1 Meals Entry Model
- [x] Create `MealsEntry` model in `models.py`
  - [x] Fields: `id`, `family_group_id` (FK), `member_id` (FK), `food_name`, `location`, `meal_type` (Enum: Breakfast, Lunch, Dinner), `date` (Date), `created_by_id` (FK to User), `created_at`
  - [x] Add relationships to group and member.

**Manual Testing 2.1:**
- [ ] Run `flask db migrate -m "Add meals_entry model"`
- [ ] Run `flask db upgrade`

### 2.2 Multi-Member Logging UI
- [ ] Create `LogMealForm` in `forms.py`
  - [ ] `date`, `meal_type`, `food_name`, `location`.
  - [ ] `member_ids`: Multiple selection of family members.
- [ ] Implement `POST /meals/groups/<int:group_id>/log`
  - [ ] **Access Check**: Verify requester is in the group.
  - [ ] Iterate over selected members and create individual `MealsEntry` records.
- [ ] Update `templates/meals/index.html` (Mobile-First)
  - [ ] Add "Log a Meal" form optimized for touch (large targets).
  - [ ] Add "Recent History" list.
- [ ] Add `static/meals/style.css` (with `meals-` prefixes).

**Manual Testing 2.2:**
- [ ] Log a meal for two people at once and verify two separate records are created.
- [ ] Verify the UI looks and feels good on a mobile viewport.

---

## Phase 3: Smart Entry & Dashboard Views

### 3.1 Dual Autocomplete API
- [ ] Implement `GET /meals/groups/<int:group_id>/api/suggestions/food`
  - [ ] Return unique `food_name` strings from family history.
- [ ] Implement `GET /meals/groups/<int:group_id>/api/suggestions/location`
  - [ ] Return unique `location` strings from family history.
- [ ] Integrate both autocompletes into the logging form.

### 3.2 Common Meals & Trends
- [ ] Implement the "Common Meals" table (Individual vs Family toggle).
- [ ] Implement "Location Trends" stats (Home vs Out).

**Manual Testing 3.1 & 3.2:**
- [ ] Type a food name and verify suggestions match food history, not location history.
- [ ] Verify "Common Meals" table calculates correctly.

---

## Phase 4: Calendar Views (Mobile-First)

### 4.1 Weekly & Monthly Grids
- [ ] Implement `GET /meals/groups/<int:group_id>/calendar`
- [ ] Weekly view: Optimized for mobile (scrollable or stacked).
- [ ] Monthly view: Optimized for mobile.
- [ ] Implement the "Family Overlay" (showing all members in the same cell).

**Manual Testing 4.1:**
- [ ] Verify calendar navigation works well on mobile.
- [ ] Verify family overlay doesn't break the layout.

---

## Phase 5: Final Review & Polish
- [ ] **Mobile Audit**: Final pass on all pages at 375px width.
- [ ] **CSS Audit**: Verify `meals-` prefix everywhere.
- [ ] **Permission Audit**: Verify every single route has an `is_user_in_group` check.
