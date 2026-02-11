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
- [x] Run `flask db migrate -m "Add meals_entry model"`
- [x] Run `flask db upgrade`

### 2.2 Multi-Member Logging UI
- [x] Create `LogMealForm` in `forms.py`
- [x] Implement `POST /meals/groups/<int:group_id>/log`
- [x] Update `templates/meals/group_detail.html` (Mobile-First)
- [x] Add `static/meals/style.css` (with `meals-` prefixes)
- [x] Add "Recent History" list.

**Manual Testing 2.2:**
- [x] Log a meal for two people at once and verify two separate records are created.
- [x] Verify the UI looks and feels good on a mobile viewport.

---

## Phase 3: Smart Entry & Dashboard Views

### 3.1 Dual Autocomplete API
- [x] Implement `GET /meals/groups/<int:group_id>/api/suggestions/food`
- [x] Implement `GET /meals/groups/<int:group_id>/api/suggestions/location`
- [x] Integrate both autocompletes into the logging form.

### 3.2 Common Meals & Trends
- [x] Implement the "Common Meals" table (Individual vs Family toggle).
- [x] Implement "Location Trends" stats (Home vs Out).

**Manual Testing 3.1 & 3.2:**
- [x] Type a food name and verify suggestions match food history, not location history.
- [x] Verify "Common Meals" table calculates correctly.

---

## Phase 4: Calendar Views (Mobile-First)

### 4.1 Weekly & Monthly Grids
- [x] Implement `GET /meals/groups/<int:group_id>/calendar`
- [x] Weekly view: Optimized for mobile (scrollable or stacked).
- [x] Monthly view: Optimized for mobile.
- [x] Implement the "Family Overlay" (showing all members in the same cell).

**Manual Testing 4.1:**
- [ ] Verify calendar navigation works well on mobile.
- [ ] Verify family overlay doesn't break the layout.

---

## Phase 5: Final Review & Polish
- [x] **Mobile Audit**: Final pass on all pages at 375px width.
- [x] **CSS Audit**: Verify `meals-` prefix everywhere.
- [x] **Permission Audit**: Verify every single route has an `is_user_in_group` check.

**Manual Testing 5:**
- [x] Check Dashboard, Group Detail, and Calendar on a mobile device or simulator.
- [x] Verify that navigating to another user's group ID returns a 404 or redirect.
