from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length

class CreateFamilyGroupForm(FlaskForm):
    name = StringField('Family Group Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Create Group')

class InviteMemberForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Invite Member')

class AddGuestMemberForm(FlaskForm):
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Add Member')
