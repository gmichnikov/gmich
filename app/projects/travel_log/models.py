"""Travel Log models: Collection, Entry, EntryPhoto."""

from datetime import datetime, date

from app import db


class TlogCollection(db.Model):
    """A collection of travel entries (e.g. 'Tokyo 2026', 'Portugal Summer')."""

    __tablename__ = "tlog_collection"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Denormalized: updated when entry added/edited or collection renamed (for ordering)
    last_modified = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("tlog_collections", lazy="dynamic"))
    entries = db.relationship(
        "TlogEntry",
        backref="collection",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="TlogEntry.updated_at.desc()",
    )

    __table_args__ = (db.Index("ix_tlog_collection_user_last_modified", "user_id", "last_modified"),)

    def __repr__(self):
        return f"<TlogCollection {self.id}: {self.name}>"


class TlogEntry(db.Model):
    """A place visit within a collection."""

    __tablename__ = "tlog_entry"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey("tlog_collection.id", ondelete="CASCADE"), nullable=False)
    place_id = db.Column(db.String(255), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    user_name = db.Column(db.String(255), nullable=False)
    user_address = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    visited_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("tlog_entries", lazy="dynamic"))
    photos = db.relationship(
        "TlogEntryPhoto",
        backref="entry",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="TlogEntryPhoto.sort_order, TlogEntryPhoto.created_at",
    )

    __table_args__ = (
        db.Index("ix_tlog_entry_collection_id", "collection_id"),
        db.Index("ix_tlog_entry_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<TlogEntry {self.id}: {self.user_name}>"


class TlogEntryPhoto(db.Model):
    """A photo attached to an entry, stored in R2."""

    __tablename__ = "tlog_entry_photo"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("tlog_entry.id", ondelete="CASCADE"), nullable=False)
    r2_key = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<TlogEntryPhoto {self.id}: {self.r2_key}>"
