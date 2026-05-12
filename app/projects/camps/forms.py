from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, DateField, DecimalField, IntegerField, SubmitField, TimeField
from wtforms.validators import DataRequired, URL, Email, Optional, Length, NumberRange, Regexp

class CampTagCategoryForm(FlaskForm):
    name = StringField("Category Name", validators=[DataRequired(), Length(max=100)])
    submit = SubmitField("Save Category")

class CampTagForm(FlaskForm):
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    name = StringField("Tag Name", validators=[
        DataRequired(), 
        Length(max=100),
        Regexp(r'^[a-z0-9\s&\-/]+$', message="Tags must be lowercase and can only contain letters, numbers, spaces, and symbols like & - /")
    ])
    submit = SubmitField("Save Tag")

class CampForm(FlaskForm):
    name = StringField("Camp Name", validators=[DataRequired(), Length(max=255)])
    website_url = StringField("Website URL", validators=[Optional(), URL(), Length(max=512)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    address = StringField("Address", validators=[Optional(), Length(max=255)])
    city = StringField("City", validators=[DataRequired(), Length(max=100)])
    state = StringField("State", validators=[DataRequired(), Length(min=2, max=2)], default="NJ")
    zip = StringField("Zip Code", validators=[Optional(), Length(max=20)])
    tag_ids = SelectMultipleField("Tags", coerce=int)
    submit = SubmitField("Save Camp")

class CampSessionForm(FlaskForm):
    name = StringField("Session Name", validators=[Optional(), Length(max=255)])
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[DataRequired()])
    start_time = TimeField("Start Time", validators=[Optional()])
    end_time = TimeField("End Time", validators=[Optional()])
    age_min = IntegerField("Min Age", validators=[Optional(), NumberRange(min=0, max=100)])
    age_max = IntegerField("Max Age", validators=[Optional(), NumberRange(min=0, max=100)])
    grade_min = IntegerField("Min Grade (-1 for Pre-K, 0 for K)", validators=[Optional(), NumberRange(min=-1, max=12)])
    grade_max = IntegerField("Max Grade", validators=[Optional(), NumberRange(min=-1, max=12)])
    price = DecimalField("Price", validators=[Optional()], places=2)
    
    # Bulk add helper
    additional_weeks = SelectMultipleField("Also add for these weeks (Summer 2026)", coerce=str)
    
    submit = SubmitField("Save Session")
