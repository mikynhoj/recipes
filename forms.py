from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length

class UserAddForm(FlaskForm):
    """Add new user form"""
    name=StringField('Name', validators=[DataRequired()])
    email=StringField('E-mail', validators=[DataRequired()])
    
    password=PasswordField('Password',validators=[DataRequired(), Length(min=6)])
    
    allergies=StringField("Allergens/Intolerances")

class UserSignInForm(FlaskForm):
    """Sign in user form"""
    
    email=StringField('E-mail', validators=[DataRequired()])
    password=PasswordField('Password',validators=[DataRequired(), Length(min=6)])

class UserEditForm(FlaskForm):
    """Edit user form"""
    name=StringField('Name', validators=[DataRequired()])
    
    
    allergies=StringField("Allergens/Intolerances")

class RecipeNoteForm(FlaskForm):
    """Save user's notes for a recipe"""
    notes=TextAreaField('Notes')
    