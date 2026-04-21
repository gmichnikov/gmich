from datetime import date, datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import db
from app.projects.helper.models import HelperGroup, HelperGroupMember, HelperTask
from app.utils.logging import log_project_visit
from app.utils.user_time import format_user_local_date

helper_bp = Blueprint(
    "helper",
    __name__,
    url_prefix="/helper",
    template_folder="templates",
    static_folder="static",
    static_url_path="/helper/static",
)


def _get_member_group_or_404(group_id):
    """Return group if current_user is a member, else 404."""
    group = HelperGroup.query.get_or_404(group_id)
    membership = HelperGroupMember.query.filter_by(
        group_id=group.id, user_id=current_user.id
    ).first()
    if not membership:
        abort(404)
    return group


def _redirect_after_task_post(task):
    """Redirect to ?next= safe internal path, or group task list."""
    next_path = (request.form.get("next") or "").strip()
    if next_path.startswith("/helper/") and not next_path.startswith("//"):
        return redirect(next_path)
    return redirect(url_for("helper.group_detail", group_id=task.group_id))


def _is_helper_xhr():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


# ---------------------------------------------------------------------------
# Index — list groups + open tasks
# ---------------------------------------------------------------------------

@helper_bp.route("/")
@login_required
def index():
    log_project_visit("helper", "Helper")
    memberships = (
        HelperGroupMember.query
        .filter_by(user_id=current_user.id)
        .join(HelperGroup)
        .order_by(HelperGroup.name)
        .all()
    )
    groups = [m.group for m in memberships]

    # Pre-fetch open + recently completed tasks per group
    open_tasks = {}
    recent_completed = {}
    for group in groups:
        open_tasks[group.id] = (
            HelperTask.query
            .filter_by(group_id=group.id, status="open")
            .order_by(HelperTask.due_date.asc().nullslast(), HelperTask.created_at.asc())
            .all()
        )
        recent_completed[group.id] = (
            HelperTask.query
            .filter_by(group_id=group.id, status="complete")
            .order_by(HelperTask.completed_at.desc())
            .limit(3)
            .all()
        )

    return render_template(
        "helper/index.html",
        groups=groups,
        open_tasks=open_tasks,
        recent_completed=recent_completed,
    )


# ---------------------------------------------------------------------------
# Group detail — all tasks (open + completed)
# ---------------------------------------------------------------------------

@helper_bp.route("/group/<int:group_id>")
@login_required
def group_detail(group_id):
    group = _get_member_group_or_404(group_id)
    open_tasks = (
        HelperTask.query.options(
            joinedload(HelperTask.assignee),
            joinedload(HelperTask.creator),
        )
        .filter_by(group_id=group.id, status="open")
        .order_by(HelperTask.due_date.asc().nullslast(), HelperTask.created_at.asc())
        .all()
    )
    completed_tasks = (
        HelperTask.query.options(
            joinedload(HelperTask.assignee),
            joinedload(HelperTask.creator),
            joinedload(HelperTask.completer),
        )
        .filter_by(group_id=group.id, status="complete")
        .order_by(HelperTask.completed_at.desc())
        .limit(50)
        .all()
    )
    members = [m.user for m in group.members if m.user]
    return render_template(
        "helper/group.html",
        group=group,
        open_tasks=open_tasks,
        completed_tasks=completed_tasks,
        members=members,
    )


# ---------------------------------------------------------------------------
# Task detail
# ---------------------------------------------------------------------------

@helper_bp.route("/task/<int:task_id>")
@login_required
def task_detail(task_id):
    task = (
        HelperTask.query.options(
            joinedload(HelperTask.group),
            joinedload(HelperTask.assignee),
            joinedload(HelperTask.creator),
            joinedload(HelperTask.completer),
            joinedload(HelperTask.source_inbound_email),
            joinedload(HelperTask.completed_via_inbound_email),
        )
        .get_or_404(task_id)
    )
    group = _get_member_group_or_404(task.group_id)
    log_project_visit("helper", f"Helper — {task.title[:40]}")
    detail_url = url_for("helper.task_detail", task_id=task.id)
    members = [m.user for m in group.members if m.user]
    return render_template(
        "helper/task_detail.html",
        task=task,
        group=group,
        members=members,
        detail_url=detail_url,
    )


# ---------------------------------------------------------------------------
# Complete a task
# ---------------------------------------------------------------------------

@helper_bp.route("/task/<int:task_id>/complete", methods=["POST"])
@login_required
def task_complete(task_id):
    task = HelperTask.query.get_or_404(task_id)
    _get_member_group_or_404(task.group_id)
    task.status = "complete"
    task.completed_by_user_id = current_user.id
    task.completed_at = datetime.utcnow()
    task.completed_via_inbound_email_id = None
    db.session.commit()
    return _redirect_after_task_post(task)


# ---------------------------------------------------------------------------
# Reopen a completed task
# ---------------------------------------------------------------------------

@helper_bp.route("/task/<int:task_id>/reopen", methods=["POST"])
@login_required
def task_reopen(task_id):
    task = HelperTask.query.get_or_404(task_id)
    _get_member_group_or_404(task.group_id)
    task.status = "open"
    task.completed_by_user_id = None
    task.completed_at = None
    task.completed_via_inbound_email_id = None
    db.session.commit()
    return _redirect_after_task_post(task)


# ---------------------------------------------------------------------------
# Delete a task
# ---------------------------------------------------------------------------

@helper_bp.route("/task/<int:task_id>/delete", methods=["POST"])
@login_required
def task_delete(task_id):
    task = HelperTask.query.get_or_404(task_id)
    group_id = task.group_id
    _get_member_group_or_404(group_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("helper.group_detail", group_id=group_id))


# ---------------------------------------------------------------------------
# Edit notes on a task
# ---------------------------------------------------------------------------

@helper_bp.route("/task/<int:task_id>/notes", methods=["POST"])
@login_required
def task_notes(task_id):
    task = HelperTask.query.get_or_404(task_id)
    _get_member_group_or_404(task.group_id)
    task.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "notes": task.notes or ""})
    return _redirect_after_task_post(task)


# ---------------------------------------------------------------------------
# Edit title / due date / assignee (task detail)
# ---------------------------------------------------------------------------

@helper_bp.route("/task/<int:task_id>/title", methods=["POST"])
@login_required
def task_title(task_id):
    task = HelperTask.query.get_or_404(task_id)
    _get_member_group_or_404(task.group_id)
    title = (request.form.get("title") or "").strip()
    if not title:
        if _is_helper_xhr():
            return jsonify({"ok": False, "error": "Title is required"}), 400
        return redirect(url_for("helper.task_detail", task_id=task.id))
    if len(title) > 255:
        if _is_helper_xhr():
            return jsonify({"ok": False, "error": "Title is too long"}), 400
        return redirect(url_for("helper.task_detail", task_id=task.id))
    task.title = title
    db.session.commit()
    if _is_helper_xhr():
        return jsonify({"ok": True, "title": task.title})
    return _redirect_after_task_post(task)


@helper_bp.route("/task/<int:task_id>/due", methods=["POST"])
@login_required
def task_due(task_id):
    task = HelperTask.query.get_or_404(task_id)
    _get_member_group_or_404(task.group_id)
    raw = (request.form.get("due_date") or "").strip()
    if not raw:
        task.due_date = None
    else:
        try:
            task.due_date = date.fromisoformat(raw)
        except ValueError:
            if _is_helper_xhr():
                return jsonify({"ok": False, "error": "Invalid date"}), 400
            return redirect(url_for("helper.task_detail", task_id=task.id))
    db.session.commit()
    due_label = (
        format_user_local_date(task.due_date, current_user, "%b %-d, %Y")
        if task.due_date
        else ""
    )
    if _is_helper_xhr():
        return jsonify(
            {
                "ok": True,
                "due_date": task.due_date.isoformat() if task.due_date else "",
                "due_label": due_label or None,
            }
        )
    return _redirect_after_task_post(task)


@helper_bp.route("/task/<int:task_id>/assignee", methods=["POST"])
@login_required
def task_assignee(task_id):
    task = HelperTask.query.get_or_404(task_id)
    _get_member_group_or_404(task.group_id)
    raw = (request.form.get("assignee_user_id") or "").strip()
    if raw == "":
        task.assignee_user_id = None
    else:
        try:
            uid = int(raw)
        except ValueError:
            if _is_helper_xhr():
                return jsonify({"ok": False, "error": "Invalid assignee"}), 400
            return redirect(url_for("helper.task_detail", task_id=task.id))
        if not HelperGroupMember.query.filter_by(
            group_id=task.group_id, user_id=uid
        ).first():
            if _is_helper_xhr():
                return jsonify(
                    {"ok": False, "error": "That user is not in this group"}
                ), 400
            return redirect(url_for("helper.task_detail", task_id=task.id))
        task.assignee_user_id = uid
    db.session.commit()
    task = HelperTask.query.options(joinedload(HelperTask.assignee)).get(task.id)
    if _is_helper_xhr():
        return jsonify(
            {
                "ok": True,
                "assignee_user_id": task.assignee_user_id,
                "assignee_name": task.assignee.full_name if task.assignee else "",
                "assignee_short": task.assignee.short_name if task.assignee else "",
            }
        )
    return _redirect_after_task_post(task)
