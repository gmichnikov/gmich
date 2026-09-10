import re

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

from app.projects.kids_ai.models import KidsAiChild

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


class KidsAiAllowlistForm(FlaskForm):
    email = SelectField("Hub user", choices=[], validators=[DataRequired()])
    submit = SubmitField("Allow as parent")


class KidsAiChildLoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class KidsAiCreateChildForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=20),
            Regexp(USERNAME_RE, message="Letters, numbers, and underscore only (3–20)."),
        ],
    )
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=4, max=128)]
    )
    display_name = StringField(
        "Display name", validators=[DataRequired(), Length(min=1, max=50)]
    )
    age_tier = SelectField(
        "Age tier",
        choices=[
            (KidsAiChild.AGE_YOUNG_CHILD, "Young child (5–8)"),
            (KidsAiChild.AGE_TWEEN, "Tween (9–12)"),
            (KidsAiChild.AGE_TEEN, "Teen (13–17)"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Create child")

    def validate_username(self, field):
        username = field.data.strip().lower()
        if KidsAiChild.query.filter_by(username=username).first():
            raise ValidationError("That username is already taken.")


class KidsAiEditChildForm(FlaskForm):
    display_name = StringField(
        "Display name", validators=[DataRequired(), Length(min=1, max=50)]
    )
    age_tier = SelectField(
        "Age tier",
        choices=[
            (KidsAiChild.AGE_YOUNG_CHILD, "Young child (5–8)"),
            (KidsAiChild.AGE_TWEEN, "Tween (9–12)"),
            (KidsAiChild.AGE_TEEN, "Teen (13–17)"),
        ],
        validators=[DataRequired()],
    )
    new_password = PasswordField(
        "New password (leave blank to keep)",
        validators=[Optional(), Length(min=4, max=128)],
    )
    submit = SubmitField("Save")
