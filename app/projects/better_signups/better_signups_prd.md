# Better Signups PRD

This is a PRD for a better version of signup genius. The goal is to describe the requirements, very succinctly. We want to get an MVP version working, and then we can consider additional features.

# Basics

1. The unit that a user creates will be called a List.
2. A list contains either events or items (just one)
3. Lists have a name and an optional description
4. Events are either dates or datetimes/timestamps (just one, and the creator chooses if they want to offer specific time ranges, or just dates). Either way, they have an optional field called location and an optional descriptions. (The date or datetime is the "name" but we won't store this. We'll format the name for display.) For times, let's store the datetime and the time zone. The time zone should be the creator's time zone. Let's also store the duration in minutes, not the end time. For dates, store as a Date field (no time component). For date-only events, set duration_minutes = None and timezone = None.
5. Items are strings. They have names and optional description.
6. If we need an internal term that includes both events and items, we can call them elements, but that will never be exposed to users.
7. There can be 1 or more signup spots available for each item event/item
8. Auth will be handled by my web app's existing auth. Users must be signed in to use this.
9. Each list can be either open to anyone with an account, or it can require an additional list password. Let's hash the password like with user passwords.
10. It should be possible for the end user to cancel their signup for a spot
11. A list creator is considered to be an editor and can add additional users to be list editors
12. A list can be in the state or accepting signups, or not accepting signups
13. Editors can both remove signups and edit the lists/elements at any time. For now, they cannot reduce the number of spots in an element below the number already signed up.
14. When signing up, users can see (before the sign up) how many spots are available and who has taken spots so far (though per below, we may eventually offer to hide that)
15. Each user account needs to have the option to add other family members. For now, these other members only have a single full name for display.
16. When a user signs up, if they have other family members in their account, they have the option to indicate who they are signing up. The default is themselves. We should have some sort of self Family Member record so we don't have to special case it. The name should not be editable here, we will take it from the user's account.
17. A user can sign up more than one person for the same element if there are multiple spots. The same person cannot be signed up more than once for a splot though.
18. There is no public list of lists. It must be reached via direct link. This will be a standard UUID based URL that cannot be changed.

# One level beyond basics

1. Ability to limit how many spots one account signs up for within a list of elements (max 1 signup per element). Limits are at the level of the person being signed up (e.g. child), not the user doing the signups.
2. Have an option to do a lottery after a certain of time goes by (same lottery time for all elements in a list), rather than first come first served (it can only use one approach). No special action needed, this will be the only option for these elements (Enter lottery). Before the lottery, it will show the user that they have entered (and if they have other family members, there will be an option to enter another person). It will be done automatically at the chosen time, and users will be notified of results in emails. Users must click to accept (the creator can choose how long they have to accept). If they don't, it goes to the next person in the waitlist, or to no one if empty. Users can be in a lottery for more than one element (and for more than the limit for the given list). Limits will be applied as needed when the lottery is conducted (loterries will be done in random order, users cannot rank preferences between elements, once they hit the max they won't be in lotteries for future elements).
3. Within lists that user lotteries, have an option to always give everyone 1 spot before giving anyone a second spot, etc.
4. A list level option to allow swaps. If this is on, a user can request to switch out of their current spot, and a link is sent by email to any other users who are signed up on that list but for a different element. Whoever clicks that link first, the swap is completed automatically. Until the swap is completed, the requestor remains in their chosen spot.
5. Allow (ordered) waitlists on elements. For signups with lotteries, there will be an option up front to be added to a waitlist if not picked. For signups that are first come first served, there will just be an option to join the waitlist. The names can be visible or hidden. If someone cancels, the first name on the waitlist fills in. They must accept within some time (set by creator), or the next person is added. If the spot is not filled, it's then re-opened. A user can remove themselves from a waitlist at any time after it is created.
6. Added to Google Calendar button

# Ideas that are not part of MVP, tracking them here for later

1. Allow someone to indicate they are flexible across several items
2. Allow hiding who else signed up
3. List editors can add questions that must be answered as part of taking a spot
4. Confirmation emails and reminder emails
