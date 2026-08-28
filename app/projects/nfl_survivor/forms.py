from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Optional


class TeamSelectionForm(FlaskForm):
    week = HiddenField("Week")
    team_choice = SelectField("Select an NFL Team", choices=[])
    submit = SubmitField("Submit pick")


class AdminSetPickForm(FlaskForm):
    user_id = SelectField("Participant", coerce=int, choices=[])
    week = SelectField("Week", choices=[])
    team = SelectField("Team", choices=[])
    submit = SubmitField("Set Pick")


class SeasonForm(FlaskForm):
    year = IntegerField("Season year", validators=[DataRequired()])
    name = StringField("Display name", validators=[DataRequired()])
    week_2_start = StringField(
        "Week 2 starts (US/Eastern, YYYY-MM-DD HH:MM)",
        validators=[DataRequired()],
    )
    espn_season_year = IntegerField("ESPN season year", validators=[DataRequired()])
    max_weeks = IntegerField("Max weeks", default=18, validators=[Optional()])
    is_active = BooleanField("Set as active season", default=True)
    submit = SubmitField("Save Season")
