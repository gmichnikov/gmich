from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    TextAreaField,
    SelectMultipleField,
    BooleanField,
    IntegerField,
    DateField,
)
from wtforms.validators import DataRequired, Length, Email, ValidationError, EqualTo, NumberRange, Optional
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


class FamilyMemberForm(FlaskForm):
    """Form for adding a family member"""

    display_name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=1, max=200)],
        description="Enter the full name of the family member"
    )
    submit = SubmitField("Add Family Member")

    def validate_display_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("Name cannot be blank or only whitespace.")


class CreateSignupListForm(FlaskForm):
    """Form for creating a new signup list"""

    name = StringField(
        "List Name",
        validators=[DataRequired(), Length(min=1, max=200)],
        description="Name of the signup list"
    )
    description = TextAreaField(
        "Description",
        validators=[Length(max=2000)],
        description="Optional description for the list"
    )
    list_type = SelectField(
        "List Type",
        choices=[("events", "Events (dates/times)"), ("items", "Items")],
        validators=[DataRequired()],
        description="Choose whether this list contains events or items"
    )
    list_password = PasswordField(
        "List Password (Optional)",
        validators=[Length(max=100)],
        description="Optional password to restrict access to this list. Leave blank for open access."
    )
    submit = SubmitField("Create List")

    def validate_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("List name cannot be blank or only whitespace.")


class EditSignupListForm(FlaskForm):
    """Form for editing a signup list"""

    name = StringField(
        "List Name",
        validators=[DataRequired(), Length(min=1, max=200)]
    )
    description = TextAreaField(
        "Description",
        validators=[Length(max=2000)]
    )
    list_password = PasswordField(
        "List Password (Optional)",
        validators=[Length(max=100)],
        description="Leave blank to keep current password, or enter new password to change it"
    )
    accepting_signups = BooleanField(
        "Accepting Signups",
        default=True,
        description="Allow users to sign up for this list"
    )
    submit = SubmitField("Update List")

    def validate_name(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("List name cannot be blank or only whitespace.")


class AddListEditorForm(FlaskForm):
    """Form for adding a list editor by email"""

    email = StringField(
        "Email Address",
        validators=[DataRequired(), Email(), Length(max=60)],
        description="Enter the email address of the user to add as an editor"
    )
    submit = SubmitField("Add Editor")

    def validate_email(self, field):
        if not field.data or not field.data.strip():
            raise ValidationError("Email cannot be blank or only whitespace.")


class EventForm(FlaskForm):
    """Form for creating/editing events"""

    event_type = SelectField(
        "Event Type",
        choices=[("date", "Date Only"), ("datetime", "Date and Time")],
        validators=[DataRequired()],
        description="Choose whether this is a date-only event or includes specific time"
    )
    event_date = DateField(
        "Event Date",
        validators=[Optional()],
        description="Date for date-only events"
    )
    event_datetime = StringField(
        "Event Date and Time",
        validators=[],
        description="Date and time for datetime events (format: YYYY-MM-DD HH:MM)"
    )
    timezone = SelectField(
        "Time Zone",
        choices=[(tz, tz) for tz in pytz.common_timezones],
        validators=[Optional()],
        description="Timezone for datetime events"
    )
    duration_minutes = IntegerField(
        "Duration (minutes)",
        validators=[Optional()],  # Max 7 days - validation done in custom validator
        description="Duration in minutes (for datetime events only)"
    )
    location = StringField(
        "Location",
        validators=[Length(max=200)],
        description="Optional location for the event"
    )
    location_is_link = BooleanField(
        "Make the location a clickable link to Google Maps",
        default=True
    )
    description = TextAreaField(
        "Description",
        validators=[Length(max=2000)],
        description="Optional description for the event"
    )
    spots_available = IntegerField(
        "Spots Available",
        validators=[DataRequired(), NumberRange(min=1)],
        default=1,
        description="Number of signup spots available"
    )
    submit = SubmitField("Save Event")

    def validate_event_date(self, field):
        """Validate event_date is provided for date-only events"""
        if self.event_type.data == 'date' and not field.data:
            raise ValidationError("Event date is required for date-only events.")

    def validate_event_datetime(self, field):
        """Validate event_datetime is provided for datetime events"""
        if self.event_type.data == 'datetime' and not field.data:
            raise ValidationError("Event date and time is required for datetime events.")

    def validate_duration_minutes(self, field):
        """Validate duration_minutes if provided"""
        # Only validate if a value is provided (field is optional)
        if field.data is not None:
            # IntegerField should already convert to int, but handle both cases
            value = field.data if isinstance(field.data, int) else (int(field.data) if field.data else None)
            if value is not None:
                if value < 1 or value > 10080:
                    raise ValidationError("Duration must be between 1 and 10080 minutes.")
