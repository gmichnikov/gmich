"""Travel Log — who can view/edit collections and entries (owner vs editor)."""

from __future__ import annotations

from flask import abort
from flask_login import UserMixin

from app.projects.travel_log.models import TlogCollection, TlogCollectionMember, TlogEntry

ROLE_EDITOR = "editor"


def normalize_invite_email(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def is_collection_owner(user: UserMixin | None, collection: TlogCollection | None) -> bool:
    return bool(user and collection and collection.user_id == user.id)


def editor_membership(user: UserMixin | None, collection: TlogCollection | None) -> TlogCollectionMember | None:
    if not user or not collection:
        return None
    return TlogCollectionMember.query.filter_by(
        collection_id=collection.id,
        user_id=user.id,
        role=ROLE_EDITOR,
    ).first()


def can_edit_collection(user: UserMixin | None, collection: TlogCollection | None) -> bool:
    """Owner or invited editor: journal work (entries, photos, tags)."""
    if is_collection_owner(user, collection):
        return True
    return editor_membership(user, collection) is not None


def can_manage_sharing(user: UserMixin | None, collection: TlogCollection | None) -> bool:
    """Invite/remove editors — owner only."""
    return is_collection_owner(user, collection)


def can_manage_collection_settings(user: UserMixin | None, collection: TlogCollection | None) -> bool:
    """Rename or delete collection — owner only."""
    return is_collection_owner(user, collection)


def can_edit_entry(user: UserMixin | None, entry: TlogEntry | None) -> bool:
    if not entry:
        return False
    return can_edit_collection(user, entry.collection)


def get_collection_for_access(user: UserMixin | None, collection_id: int) -> TlogCollection:
    """Collection the user may view/edit as owner or editor, else 404."""
    collection = TlogCollection.query.get(collection_id)
    if not collection or not can_edit_collection(user, collection):
        abort(404)
    return collection


def get_entry_for_access(user: UserMixin | None, entry_id: int) -> TlogEntry:
    """Entry in a collection the user may edit, else 404."""
    entry = TlogEntry.query.get(entry_id)
    if not entry or not can_edit_entry(user, entry):
        abort(404)
    return entry
