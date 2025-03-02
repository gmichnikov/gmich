from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email
import pytz

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4)])
    time_zone = SelectField('Time Zone', choices=[(tz, tz) for tz in pytz.all_timezones], default='US/Eastern')
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class AdminPasswordResetForm(FlaskForm):
    email = SelectField('Select User', choices=[])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=4)])
    submit = SubmitField('Reset Password')