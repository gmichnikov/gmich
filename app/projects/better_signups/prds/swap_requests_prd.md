# Swap Requests Feature PRD

This PRD describes the swap request feature for Better Signups, allowing users to request swaps between their signups and other users' signups within the same list.

## Overview

Allow users to request swaps between their signups and other users' signups within the same list. When a swap request is created, eligible users receive an email with swap links. The first person to click a link completes the swap automatically.

## Implementation Breakdown

**Phase 12a: Database Models and Basic Structure**

- Create models (SwapRequest, SwapRequestTarget, SwapToken), migrations
- Add basic route structure (placeholder routes)
- Test: Verify models can be created, relationships work, migrations run successfully

**Phase 12b: Swap Request Creation (UI and Logic)**

- Create swap interface template (shows all elements, allows multi-select up to 3)
- Add "Swap" button to My Signups page
- Implement swap request creation logic (validation, finding eligible partners)
- Test: Can create swap requests, validation works, eligible partners found correctly

**Phase 12c: Swap Tokens and Email Sending**

- Generate swap tokens for eligible partners
- Create email templates (request notification)
- Send emails with swap links
- Test: Emails sent correctly, tokens generated properly, links work

**Phase 12d: Swap Execution**

- Handle swap link clicks
- Execute swaps atomically (cancel old signups, create new ones)
- Send completion emails
- Test: Swaps execute correctly, signups move properly, emails sent

**Phase 12e: Cleanup, Cancellation, and Edge Cases**

- Handle swap request cancellation
- Automatic cleanup (signup cancelled, list deleted, element deleted)
- Race condition handling
- Edge case handling (expired tokens, already completed, etc.)
- Test: All edge cases handled gracefully, cleanup works correctly

## Requirements

**Models:**

- [ ] Create `SwapRequest` model:
  - `id` (primary key)
  - `requestor_signup_id` (foreign key to Signup - the signup user wants to swap FROM, i.e., the one they want to unload/get rid of)
  - `list_id` (foreign key to SignupList)
  - `requestor_family_member_id` (foreign key to FamilyMember) - for easier querying
  - `status` (string) - 'pending', 'completed', 'cancelled'
  - `created_at` (datetime)
  - `completed_at` (datetime, nullable)
  - `completed_by_user_id` (foreign key to User, nullable)
- [ ] Create `SwapRequestTarget` model (allows one swap request to target multiple elements):
  - `id` (primary key)
  - `swap_request_id` (foreign key to SwapRequest)
  - `target_element_id` (integer) - ID of the element (event or item) user wants to swap TO (i.e., the one they want to get)
  - `target_element_type` (string) - 'event' or 'item'
  - Note: One SwapRequest can have multiple SwapRequestTarget records, meaning the user can express interest in swapping to multiple different elements
- [ ] Create `SwapToken` model:
  - `id` (primary key)
  - `swap_request_id` (foreign key to SwapRequest)
  - `token` (string, unique) - unique token for the swap link
  - `recipient_signup_id` (foreign key to Signup) - the signup that would be swapped FROM recipient's side
  - `recipient_user_id` (foreign key to User) - user who received the email
  - `is_used` (boolean, default False)
  - `used_at` (datetime, nullable)
  - `created_at` (datetime)

**Routes:**

- [ ] Add route for viewing swap request interface (shows all other elements in the list)
- [ ] Add route for creating a swap request
- [ ] Add route for cancelling a swap request
- [ ] Add route for executing a swap (via token link)
- [ ] Add route for handling expired/already-used swap tokens

**Templates:**

- [ ] Add "Swap" button to My Signups page (only show if signup is active and no existing swap request for that family member in that list)
- [ ] Create swap request interface template (shows list of all other elements in the same list to choose from)
- [ ] Add indicator on My Signups page for active swap requests (shows which element they want to swap to, with option to cancel)
- [ ] Create swap execution confirmation page (shown after successful swap)
- [ ] Create swap token expired/already-used page (for when swap already completed or request cancelled)

**Business Logic:**

- [ ] When creating swap request:
  - Verify requestor's signup is still active
  - User can select MULTIPLE target elements they're interested in swapping to (maximum 3 target elements per swap request)
  - Only show target elements that are FULL (no available spots) and have at least one signup
    - If an element has available spots, user can just sign up directly - no need to swap
    - If an element has zero signups, there's no one to swap with
  - For each selected target element:
    - Verify target element exists and is in same list
    - Verify target element is full (spots_remaining == 0) and has signups (spots_taken > 0)
    - Verify requestor's family member (the one in the signup) is NOT already signed up for that target element (prevent self-swap - cannot swap to element you're already signed up for)
  - Check if this family member already has a pending swap request in this list - if yes, prevent creating new one (only one swap request per family member per list)
  - Find all eligible swap partners across ALL selected target elements:
    - For each target element, find users who have at least one family member signed up for that target element
    - That family member is NOT already signed up for requestor's element
    - Create SwapToken for each eligible family member + target element combo
  - If no eligible partners found across any target elements, show message and don't create request
  - Create one SwapRequest record
  - Create SwapRequestTarget records (one per selected target element)
  - Create SwapToken records (one per eligible family member + target element combo)
  - Group tokens by recipient_user_id
  - Send one email per recipient_user_id with ALL their family's swap options across ALL target elements
- [ ] When swap link is clicked:
  - Verify token exists and is not used
  - Verify swap request is still pending
  - Verify both signups are still active (if either is cancelled, show message and do nothing)
  - Verify the target element (from the token) still exists and is still in the swap request's target elements
  - Execute swap atomically:
    - Cancel requestor's signup (mark as cancelled)
    - Cancel recipient's signup (mark as cancelled)
    - Create new signup: requestor's family member → target element (from token)
    - Create new signup: recipient's family member → requestor's original element
    - Mark swap token as used
    - Mark swap request as completed
    - Invalidate all other tokens for this swap request (mark as used or add cancelled status)
  - Send confirmation email to requestor (notifying them swap completed, which target element was used)
  - Send confirmation email to recipient (notifying them swap completed, which target element was used)
  - Show success message
- [ ] When swap request is cancelled (by user):
  - Mark swap request as cancelled
  - Invalidate all associated swap tokens
  - (Tokens remain in DB but marked as invalid)
- [ ] When signup is cancelled (automatic cleanup):
  - Find all pending swap requests for that signup (as requestor_signup_id)
  - Mark all those swap requests as cancelled
  - Invalidate all associated swap tokens
- [ ] When list is deleted (automatic cleanup):
  - Find all pending swap requests for that list
  - Mark all those swap requests as cancelled
  - Invalidate all associated swap tokens
- [ ] When target element is deleted (graceful handling):
  - Note: Each swap request can have MULTIPLE target elements (the elements the user wants to swap TO).
  - When a user creates a swap request, they can select MULTIPLE target elements from the list.
  - If a target element is deleted:
    - Remove that target element from any pending swap requests (delete SwapRequestTarget record)
    - Invalidate all swap tokens associated with that deleted target element
    - If a swap request has NO remaining target elements after deletion, mark the swap request as cancelled
    - If a swap request still has other target elements, keep it active (only remove the deleted one)
  - If someone clicks a swap link for a deleted target element, show appropriate message
- [ ] Race condition handling:
  - When executing swap, verify both signups are still active atomically (within transaction)
  - If requestor's signup was cancelled between link click and execution, show message and abort gracefully
  - If recipient's signup was cancelled between link click and execution, show message and abort gracefully
  - Use database transactions to ensure atomicity of swap execution
- [ ] Edge cases to handle gracefully:
  - User clicks swap link after swap already completed → show "swap already completed" message
  - User clicks swap link after swap request was cancelled → show "swap request cancelled" message
  - Recipient cancels their signup then clicks swap link → verify signup is inactive, show message and do nothing (don't break)
  - Requestor cancels signup while swap is in progress → handled by automatic cleanup and race condition checks above
  - Target element gets deleted → handled by automatic cleanup above
  - List gets deleted → handled by automatic cleanup above

**Email:**

- [ ] Create email template for swap request notification (sent to potential swap partners)
  - Email includes:
    - List name
    - Requestor's name and which family member they want to swap
    - Description of requestor's current element (event date/time or item name)
    - List of ALL swappable options within recipient's family across ALL target elements
    - For each option, show: which target element it's for, which family member, and unique swap link with token
    - Clear explanation of what will happen if they click (which swap will execute)
- [ ] Create email template for swap completion notification (sent to both parties)
  - Email to requestor includes:
    - Confirmation that swap completed
    - Details of what was swapped (from which element to which element)
    - Which family member was swapped
  - Email to recipient (the one who clicked the link) includes:
    - Confirmation that swap completed
    - Details of what was swapped (from which element to which element)
    - Which family member was swapped

**UI/UX:**

- [ ] Swap button only visible when:
  - Signup is active (not cancelled)
  - User is viewing their own signup
  - No existing pending swap request for this family member in this list
- [ ] Swap request interface shows:
  - Current element details (what they're swapping FROM)
  - List of all other elements in the same list (what they can swap TO)
  - User can select MULTIPLE target elements (checkboxes or multi-select, maximum 3 selections)
  - Show message/indicator when 3 elements are selected (disable further selections)
  - For each element, show: name/date, spots available, who's signed up
  - Disable elements that the requestor's family member is already signed up for (self-swap prevention)
  - Note: Full elements are fine for swaps (swaps don't change total signup count)
- [ ] My Signups page shows indicator (e.g., badge or icon) next to signups with active swap requests
  - Indicator shows which elements they want to swap to (can be multiple)
  - Clicking indicator shows swap request details (all target elements) and option to cancel
- [ ] No in-app visibility of swap requests for other users (email-only notification)

**Testing:**

- [ ] Create swap request from My Signups page
- [ ] Verify only one swap request allowed per family member per list
- [ ] Verify email is sent to eligible users (one per user)
- [ ] Verify email contains all family member swap options for that user
- [ ] Click swap link and verify swap executes correctly
- [ ] Verify both signups are moved to opposite elements
- [ ] Verify other swap tokens become invalid after swap
- [ ] Try clicking expired token - verify appropriate message
- [ ] Cancel swap request and verify tokens are invalidated
- [ ] Cancel signup and verify swap requests are automatically cancelled
- [ ] Test edge cases:
  - Swap request when no eligible partners exist
  - Swap to/from full elements (should work fine)
  - Swap when signup is cancelled before swap completes
  - Recipient cancels signup then clicks swap link (should gracefully do nothing)
  - Try to create second swap request for same family member in same list (should be prevented)
  - Click swap link after swap already completed (should show message)
  - Click swap link after swap request cancelled (should show message)
  - Delete list and verify all swap requests are automatically cancelled
  - Delete target element and verify swap requests are automatically cancelled
  - Race condition: Cancel signup while someone is clicking swap link (should handle gracefully)
  - Try to create swap request to element you're already signed up for (self-swap prevention)

## Implementation Notes:

- **Self-swap prevention**: Check that requestor's family member is NOT already signed up for target element before creating swap request.
- **Race condition handling**: Use database transactions and atomic checks when executing swaps to handle cases where signups are cancelled concurrently.
- **Automatic cleanup**: Swap requests are automatically cancelled when:
  - The requestor's signup is cancelled
  - The list is deleted
  - The target element is deleted
- **Graceful degradation**: All swap link clicks should verify conditions and show appropriate messages rather than throwing errors.
