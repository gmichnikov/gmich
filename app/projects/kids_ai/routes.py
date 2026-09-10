from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import LogEntry
from app.projects.kids_ai.access import is_allowlisted_parent
from app.projects.kids_ai.auth import (
    clear_child_session_cookie,
    get_current_child,
    set_child_session_cookie,
)
from app.projects.kids_ai.forms import (
    KidsAiChildLoginForm,
    KidsAiCreateChildForm,
    KidsAiEditChildForm,
)
from app.projects.kids_ai.models import KidsAiChild, KidsAiConsentEvent, KidsAiParent
from app.utils.logging import log_project_visit

kids_ai_bp = Blueprint(
    "kids_ai",
    __name__,
    url_prefix="/kids-ai",
    template_folder="templates",
    static_folder="static",
    static_url_path="/kids-ai/static",
)


def _parent_required():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=url_for("kids_ai.index")))
    if not is_allowlisted_parent(current_user):
        flash("Kids AI is not enabled for your account.", "error")
        return redirect(url_for("kids_ai.child_login"))
    return None


def _child_for_parent_or_404(child_id):
    return KidsAiChild.query.filter_by(
        id=child_id, parent_user_id=current_user.id
    ).first_or_404()


@kids_ai_bp.route("/")
def index():
    child = get_current_child()
    if child:
        return redirect(url_for("kids_ai.child_home"))
    if current_user.is_authenticated and is_allowlisted_parent(current_user):
        return redirect(url_for("kids_ai.dashboard"))
    return redirect(url_for("kids_ai.child_login"))


@kids_ai_bp.route("/login", methods=["GET", "POST"])
def child_login():
    if get_current_child():
        return redirect(url_for("kids_ai.child_home"))

    form = KidsAiChildLoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        child = KidsAiChild.query.filter_by(username=username).first()
        parent_ok = (
            child
            and KidsAiParent.query.filter_by(user_id=child.parent_user_id).first()
        )
        if (
            child
            and child.enabled
            and parent_ok
            and child.check_password(form.password.data)
        ):
            log_project_visit("kids_ai", "Kids AI")
            response = redirect(url_for("kids_ai.child_home"))
            return set_child_session_cookie(response, child.id)
        flash("That username or password didn’t work.", "error")

    parent_signed_in = current_user.is_authenticated and is_allowlisted_parent(
        current_user
    )
    return render_template(
        "kids_ai/login.html",
        form=form,
        parent_signed_in=parent_signed_in,
    )


@kids_ai_bp.route("/logout", methods=["POST"])
def child_logout():
    response = redirect(url_for("kids_ai.child_login"))
    return clear_child_session_cookie(response)


@kids_ai_bp.route("/home")
def child_home():
    child = get_current_child()
    if child is None:
        flash("Please sign in.", "error")
        response = redirect(url_for("kids_ai.child_login"))
        return clear_child_session_cookie(response)
    log_project_visit("kids_ai", "Kids AI")
    return render_template("kids_ai/child_home.html", child=child)


@kids_ai_bp.route("/dashboard")
@login_required
def dashboard():
    denied = _parent_required()
    if denied:
        return denied
    log_project_visit("kids_ai", "Kids AI")
    children = (
        KidsAiChild.query.filter_by(parent_user_id=current_user.id)
        .order_by(KidsAiChild.display_name, KidsAiChild.username)
        .all()
    )
    return render_template(
        "kids_ai/dashboard.html",
        children=children,
        create_form=KidsAiCreateChildForm(),
        credits=current_user.credits or 0,
    )


@kids_ai_bp.route("/children", methods=["POST"])
@login_required
def create_child():
    denied = _parent_required()
    if denied:
        return denied
    form = KidsAiCreateChildForm()
    if not form.validate_on_submit():
        children = (
            KidsAiChild.query.filter_by(parent_user_id=current_user.id)
            .order_by(KidsAiChild.display_name)
            .all()
        )
        return render_template(
            "kids_ai/dashboard.html",
            children=children,
            create_form=form,
            credits=current_user.credits or 0,
        ), 400

    child = KidsAiChild(
        parent_user_id=current_user.id,
        username=form.username.data.strip().lower(),
        display_name=form.display_name.data.strip(),
        age_tier=form.age_tier.data,
        enabled=True,
        lock_count=0,
        paused=False,
    )
    child.set_password(form.password.data)
    db.session.add(child)
    db.session.flush()
    db.session.add(
        KidsAiConsentEvent(
            parent_user_id=current_user.id,
            child_id=child.id,
            username=child.username,
            display_name=child.display_name,
            age_tier=child.age_tier,
        )
    )
    db.session.add(
        LogEntry(
            project="kids_ai",
            category="Create Child",
            actor_id=current_user.id,
            description=(
                f"{current_user.email} created Kids AI child {child.username} "
                f"(tier {child.age_tier})"
            ),
        )
    )
    db.session.commit()
    flash(f"Created {child.display_name} ({child.username}).", "success")
    return redirect(url_for("kids_ai.dashboard"))


@kids_ai_bp.route("/children/<int:child_id>", methods=["GET", "POST"])
@login_required
def edit_child(child_id):
    denied = _parent_required()
    if denied:
        return denied
    child = _child_for_parent_or_404(child_id)
    form = KidsAiEditChildForm(obj=child)
    if form.validate_on_submit():
        child.display_name = form.display_name.data.strip()
        child.age_tier = form.age_tier.data
        if form.new_password.data:
            child.set_password(form.new_password.data)
        db.session.commit()
        flash("Saved.", "success")
        return redirect(url_for("kids_ai.dashboard"))
    return render_template("kids_ai/edit_child.html", child=child, form=form)


@kids_ai_bp.route("/children/<int:child_id>/disable", methods=["POST"])
@login_required
def disable_child(child_id):
    denied = _parent_required()
    if denied:
        return denied
    child = _child_for_parent_or_404(child_id)
    child.enabled = False
    db.session.commit()
    flash(f"{child.display_name} can no longer sign in.", "success")
    return redirect(url_for("kids_ai.dashboard"))


@kids_ai_bp.route("/children/<int:child_id>/enable", methods=["POST"])
@login_required
def enable_child(child_id):
    denied = _parent_required()
    if denied:
        return denied
    child = _child_for_parent_or_404(child_id)
    child.enabled = True
    db.session.commit()
    flash(f"{child.display_name} can sign in again.", "success")
    return redirect(url_for("kids_ai.dashboard"))


@kids_ai_bp.route("/children/<int:child_id>/unpause", methods=["POST"])
@login_required
def unpause_child(child_id):
    denied = _parent_required()
    if denied:
        return denied
    child = _child_for_parent_or_404(child_id)
    child.paused = False
    child.lock_count = 0
    db.session.commit()
    flash(f"{child.display_name} can chat again.", "success")
    return redirect(url_for("kids_ai.dashboard"))
