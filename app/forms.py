from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    TextAreaField,
    SelectMultipleField,
    BooleanField,
)
from wtforms.validators import DataRequired, Length, Email, ValidationError, EqualTo
import pytz
from app.models import User


class RegistrationForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=4)])
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=100)])
    short_name = StringField(
        "How should we address you?", validators=[DataRequired(), Length(max=50)]
    )
    time_zone = SelectField(
        "Time Zone",
        choices=[(tz, tz) for tz in pytz.common_timezones],
        default="US/Eastern",
    )
    submit = SubmitField("Register")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("Email already registered.")

    def validate_full_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("Full name cannot be blank or only whitespace.")

    def validate_short_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("Short name cannot be blank or only whitespace.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class ResendVerificationForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Resend Verification Email")


class RequestPasswordResetForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=4)])
    password_confirm = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
    )
    submit = SubmitField("Reset Password")


class AdminPasswordResetForm(FlaskForm):
    email = SelectField("Select User", choices=[])
    new_password = PasswordField(
        "New Password", validators=[DataRequired(), Length(min=4)]
    )
    submit = SubmitField("Reset Password")


class AskManyLLMsForm(FlaskForm):
    """Form for asking a question to multiple LLMs"""

    content = TextAreaField(
        "Your Question",
        validators=[
            DataRequired(),
            Length(
                min=10,
                max=1000,
                message="Question must be between 10 and 1000 characters",
            ),
        ],
    )

    def get_model_choices():
        """Generate model choices with pricing info"""
        from app.projects.ask_many_llms.services.llm_service import (
            MODEL_MAPPINGS,
            PRICING,
        )

        choices = []
        for display_name, model_name in MODEL_MAPPINGS.items():
            pricing = PRICING[model_name]
            label = f"{display_name} (${pricing['input']}/1M input, ${pricing['output']}/1M output)"
            choices.append((display_name, label))
        return choices

    models = SelectMultipleField(
        "Select Models (up to 5)",
        choices=get_model_choices,
        validators=[DataRequired()],
    )

    concise = BooleanField("Concise Mode", default=False)

    submit = SubmitField("Ask Question")

    def validate_models(self, field):
        if len(field.data) > 5:
            raise ValidationError("You can select at most 5 models.")
        if len(field.data) == 0:
            raise ValidationError("Please select at least one model.")


class AdminCreditForm(FlaskForm):
    """Admin form to add credits to a user"""

    email = SelectField("Select User", choices=[])
    credits = StringField("Credits to Add", validators=[DataRequired()])
    submit = SubmitField("Add Credits")


class FeedbackForm(FlaskForm):
    """Form for submitting feedback"""

    subject = StringField("Subject", validators=[DataRequired(), Length(max=200)])
    message = TextAreaField(
        "Message", validators=[DataRequired(), Length(min=10, max=2000)]
    )
    submit = SubmitField("Send Feedback")


class ProfileForm(FlaskForm):
    """Form for editing user profile"""

    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=100)])
    short_name = StringField(
        "How should we address you?", validators=[DataRequired(), Length(max=50)]
    )
    time_zone = SelectField(
        "Time Zone", choices=[(tz, tz) for tz in pytz.common_timezones], default="UTC"
    )
    submit = SubmitField("Update Profile")

    def validate_full_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("Full name cannot be blank or only whitespace.")

    def validate_short_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("Short name cannot be blank or only whitespace.")
