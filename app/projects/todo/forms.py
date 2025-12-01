from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

class TodoForm(FlaskForm):
    title = StringField('Task', 
                       validators=[
                           DataRequired(message='Task cannot be empty'),
                           Length(min=1, max=200, message='Task must be between 1 and 200 characters')
                       ],
                       render_kw={"placeholder": "What needs to be done?"})
    submit = SubmitField('Add Task')

