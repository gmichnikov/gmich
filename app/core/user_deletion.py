"""Safe deletion of unused, unverified user accounts.

An account is eligible only when it never got past email verification and has
no project data beyond signup residue (unused Better Signups "self" family
member and auth log rows). Those residue rows are removed with the user.
"""
from collections import defaultdict

from app import db
from app.models import LogEntry, User
from app.projects.ask_many_llms.models import LLMQuestion
from app.projects.baseball_lineup.models import BluTeam
from app.projects.basketball_tracker.models import BasketballGame, BasketballTeam
from app.projects.betfake.models import BetfakeAccount, BetfakeBet, BetfakeTransaction
from app.projects.better_signups.models import (
    FamilyMember,
    ListAccess,
    ListEditor,
    LotteryEntry,
    Signup,
    SignupList,
    SwapRequest,
    SwapToken,
    WaitlistEntry,
)
from app.projects.chatbot.models import ChatMessage
from app.projects.codenames_online.models import CodenamesConfusingWord
from app.projects.daily_email.models import (
    DailyEmailJobWatch,
    DailyEmailProfile,
    DailyEmailSendLog,
    DailyEmailSportsWatch,
    DailyEmailStockTicker,
    DailyEmailWeatherLocation,
)
from app.projects.football_squares.models import FootballSquaresGrid
from app.projects.helper.models import (
    HelperGroup,
    HelperGroupMember,
    HelperInboundEmail,
    HelperTask,
)
from app.projects.meals.models import MealsEntry, MealsFamilyMember
from app.projects.nfl_survivor.models import NflSurvivorParticipant
from app.projects.notes.models import Note
from app.projects.reminders.models import Reminder
from app.projects.sports_schedules.models import (
    SportsScheduleSavedQuery,
    SportsScheduleScheduledDigest,
)
from app.projects.travel_log.models import (
    TlogCollection,
    TlogCollectionMember,
    TlogEntry,
    TlogTag,
)


# (human-readable reason, column pointing at user.id)
_PROJECT_USER_COLUMNS = (
    ("Better Signups list", SignupList.creator_id),
    ("Better Signups editor", ListEditor.user_id),
    ("Better Signups access", ListAccess.user_id),
    ("Better Signups signup", Signup.user_id),
    ("Better Signups swap completed", SwapRequest.completed_by_user_id),
    ("Better Signups swap token", SwapToken.recipient_user_id),
    ("Better Signups lottery", LotteryEntry.user_id),
    ("Helper group created", HelperGroup.created_by_user_id),
    ("Helper group member", HelperGroupMember.user_id),
    ("Helper inbound email", HelperInboundEmail.sender_user_id),
    ("Helper task assignee", HelperTask.assignee_user_id),
    ("Helper task created", HelperTask.created_by_user_id),
    ("Helper task completed", HelperTask.completed_by_user_id),
    ("Daily Email profile", DailyEmailProfile.user_id),
    ("Daily Email weather", DailyEmailWeatherLocation.user_id),
    ("Daily Email stocks", DailyEmailStockTicker.user_id),
    ("Daily Email sports", DailyEmailSportsWatch.user_id),
    ("Daily Email jobs", DailyEmailJobWatch.user_id),
    ("Daily Email send log", DailyEmailSendLog.user_id),
    ("Travel log collection", TlogCollection.user_id),
    ("Travel log member", TlogCollectionMember.user_id),
    ("Travel log entry", TlogEntry.user_id),
    ("Travel log tag", TlogTag.user_id),
    ("Meals member", MealsFamilyMember.user_id),
    ("Meals entry", MealsEntry.created_by_id),
    ("Reminders", Reminder.user_id),
    ("Notes", Note.user_id),
    ("Chatbot", ChatMessage.user_id),
    ("BetFake account", BetfakeAccount.user_id),
    ("BetFake bet", BetfakeBet.user_id),
    ("BetFake transaction", BetfakeTransaction.user_id),
    ("Basketball team", BasketballTeam.user_id),
    ("Basketball game", BasketballGame.user_id),
    ("Baseball lineup team", BluTeam.user_id),
    ("Football squares", FootballSquaresGrid.user_id),
    ("NFL Survivor", NflSurvivorParticipant.user_id),
    ("Sports saved query", SportsScheduleSavedQuery.user_id),
    ("Sports digest", SportsScheduleScheduledDigest.user_id),
    ("Ask Many LLMs", LLMQuestion.user_id),
    ("Codenames word", CodenamesConfusingWord.created_by_user_id),
)


def _ids_with_column(column, user_ids):
    if not user_ids:
        return set()
    rows = (
        db.session.query(column)
        .filter(column.in_(user_ids))
        .distinct()
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _family_member_blockers_by_user(user_ids):
    """Map user_id -> reasons if family members are more than unused self residue."""
    blockers = defaultdict(list)
    if not user_ids:
        return blockers

    members = FamilyMember.query.filter(FamilyMember.user_id.in_(user_ids)).all()
    if not members:
        return blockers

    member_ids = [m.id for m in members]
    used_ids = set()
    used_ids.update(_ids_with_column(Signup.family_member_id, member_ids))
    used_ids.update(_ids_with_column(WaitlistEntry.family_member_id, member_ids))
    used_ids.update(_ids_with_column(LotteryEntry.family_member_id, member_ids))
    used_ids.update(_ids_with_column(SwapRequest.requestor_family_member_id, member_ids))

    for member in members:
        if not member.is_self:
            blockers[member.user_id].append("other family members")
        if member.id in used_ids:
            blockers[member.user_id].append("family member has signups")

    return blockers


def annotate_users_for_safe_delete(users):
    """Set safe_to_delete and safe_delete_blockers on each user."""
    user_ids = [user.id for user in users]
    blockers = defaultdict(list)

    for user in users:
        if user.is_admin:
            blockers[user.id].append("admin account")
        if user.email_verified:
            blockers[user.id].append("email is verified")
        if user.google_id:
            blockers[user.id].append("Google login linked")

    for label, column in _PROJECT_USER_COLUMNS:
        for user_id in _ids_with_column(column, user_ids):
            blockers[user_id].append(label)

    for user_id, reasons in _family_member_blockers_by_user(user_ids).items():
        blockers[user_id].extend(reasons)

    for user in users:
        reasons = list(dict.fromkeys(blockers[user.id]))
        user.safe_delete_blockers = reasons
        user.safe_to_delete = not reasons


def delete_safe_user(user, actor):
    """Delete an eligible user and leftover auth / unused-self rows.

    Returns the deleted email. Raises ValueError if the user is not eligible.
    """
    annotate_users_for_safe_delete([user])
    if not user.safe_to_delete:
        reasons = ", ".join(user.safe_delete_blockers)
        raise ValueError(f"{user.email} is not safe to delete ({reasons})")

    if actor.id == user.id:
        raise ValueError("You cannot delete your own account")

    email = user.email
    user_id = user.id

    LogEntry.query.filter_by(actor_id=user_id).delete(synchronize_session=False)
    FamilyMember.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.delete(user)

    db.session.add(
        LogEntry(
            project="admin",
            category="Delete User",
            actor_id=actor.id,
            description=f"{actor.email} deleted unused unverified account {email}",
        )
    )
    db.session.commit()
    return email
