from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, SelectMultipleField, BooleanField
from wtforms.validators import DataRequired, Length, Email, ValidationError
import pytz
from app.models import User

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4)])
    time_zone = SelectField('Time Zone', choices=[(tz, tz) for tz in pytz.common_timezones], default='US/Eastern')
    submit = SubmitField('Register')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class AdminPasswordResetForm(FlaskForm):
    email = SelectField('Select User', choices=[])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=4)])
    submit = SubmitField('Reset Password')

class AskManyLLMsForm(FlaskForm):
    """Form for asking a question to multiple LLMs"""
    content = TextAreaField('Your Question', validators=[
        DataRequired(),
        Length(min=10, max=1000, message='Question must be between 10 and 1000 characters')
    ])
    
    def get_model_choices():
        """Generate model choices with pricing info"""
        from app.projects.ask_many_llms.services.llm_service import MODEL_MAPPINGS, PRICING
        choices = []
        for display_name, model_name in MODEL_MAPPINGS.items():
            pricing = PRICING[model_name]
            label = f"{display_name} (${pricing['input']}/1M input, ${pricing['output']}/1M output)"
            choices.append((display_name, label))
        return choices
    
    models = SelectMultipleField('Select Models (up to 5)', 
                               choices=get_model_choices,
                               validators=[DataRequired()])
    
    concise = BooleanField('Concise Mode', default=False)
    
    submit = SubmitField('Ask Question')
    
    def validate_models(self, field):
        if len(field.data) > 5:
            raise ValidationError('You can select at most 5 models.')
        if len(field.data) == 0:
            raise ValidationError('Please select at least one model.')

class AdminCreditForm(FlaskForm):
    """Admin form to add credits to a user"""
    email = SelectField('Select User', choices=[])
    credits = StringField('Credits to Add', validators=[DataRequired()])
    submit = SubmitField('Add Credits')