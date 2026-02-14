from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, SelectMultipleField, DateField, widgets
from wtforms.validators import DataRequired, Email, Length, InputRequired
from datetime import datetime

class CreateFamilyGroupForm(FlaskForm):
    name = StringField('Family Group Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Create Group')

class InviteMemberForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Invite Member')

class AddGuestMemberForm(FlaskForm):
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Add Member')

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class LogMealForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    meal_type = SelectField('Meal', choices=[
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Dinner', 'Dinner')
    ], validators=[DataRequired()])
    food_name = StringField('Food Name', validators=[DataRequired(), Length(max=200)])
    location = StringField('Location', validators=[DataRequired(), Length(max=200)])
    member_ids = MultiCheckboxField('Members', coerce=int, validators=[InputRequired(message="Please select at least one member.")])
    submit = SubmitField('Log Meal')
