import os
from flask import Flask, render_template, jsonify, request, redirect, session, g, abort, flash
from flask_cors import CORS

import requests
from sqlalchemy.exc import IntegrityError

from forms import UserAddForm, UserSignInForm, UserEditForm,RecipeNoteForm

from models import db, connect_db, User, Recipe, User_Recipe

import requests
from config import APIKEY

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgres:///recipebox'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's no secret")

connect_db(app)

API_BASE_URL=f"https://api.spoonacular.com/"
CURR_USER='curr_user'
allergens=["Dairy","Egg","Gluten","Grain","Peanut","Seafood","Sesame","Shellfish","Soy","Sulfite","Tree Nut","Wheat"]
num_results=6 # change results per page


#############################
### ### Public Routes ### ###
#############################
@app.route('/') 
def show_landing_page():
    """show landing page"""
    if not g.user:
        return render_template("home-anon.html")

    return redirect("/user/profile")

@app.route('/advanced_search')
def show_advanced_search():
    """show advanced search form"""
    diets = ["","glutenfree","ketogenic",'vegetarian','lacto-vegetarian','ovo-vegetarian','vegan','pescetarian','paleo','whole30']

    return render_template("recipe-search.html",intolerances=allergens, diets=diets)

@app.route('/adv_search_results/<int:pg>')
def adv_search_query(pg):
    """perform advanced search from advanced search form, include user's allergies if logged in"""
    intolerances=[]
    if g.user:
        intolerances=g.user.allergies.split(",")

    query=request.args.get('advQuery')
    inc_ing=request.args.get('includeIngredients')
    exc_ing=request.args.get('excludeIngredients')
    cooktime=request.args.get('cooktime')
    diet=request.args.get('diet')
    
    for item in allergens:
        if request.args.get(f"{item}"):
            intolerances.append(item)

    payload={'query': query}    
    
    if inc_ing:
        payload["includeIngredients"]=inc_ing
    if exc_ing:
        payload['excludeIngredients']=exc_ing
    if cooktime:
        payload['maxReadyTime']=cooktime
    if intolerances:
        payload['intolerances']=intolerances
    if diet:
        payload['diet']=diet

    res = requests.get(f"{API_BASE_URL}/recipes/complexSearch?query={query}&number={num_results}&apiKey={APIKEY}",params=payload)
    response = res.json()

    return render_template("recipe-results.html",resp=response)    

@app.route('/search')
def recipe_search():
    """Perform basic search from search bar, include user's allergens if logged in. Store search string in g obj for paged searches"""

    search = request.args.get('search-recipe')
    if not g.user:
        query = f"{API_BASE_URL}/recipes/complexSearch?query={search}&number={num_results}&apiKey={APIKEY}"
        session['query'] = query
        res = requests.get(query) 

    if g.user:
        intolerances=g.user.allergies.split(",")

        query = f"{API_BASE_URL}/recipes/complexSearch?query={search}&excludeIngredients={intolerances}&number={num_results}&apiKey={APIKEY}"
        session['query'] = query
        res = requests.get(query) 
        
    response = res.json()
    
    return render_template("recipe-results.html",resp=response)

@app.route('/search/<int:pg>')
def page_search(pg):
    query = session['query'] 
    offset = (pg-1)*num_results
    res = requests.get(f"{query}&offset={offset}") 
    response = res.json()
    cur_pg=pg+1 
    return render_template("recipe-results.html",resp=response, cur_pg=pg)
    

@app.route('/recipe/<int:id>')
def show_recipe_info(id):
    """display detailed recipe information"""

    res = requests.get(f"{API_BASE_URL}/recipes/{id}/information?apiKey={APIKEY}")
    response = res.json()
    
    sim = requests.get(f"{API_BASE_URL}/recipes/{id}/similar?apiKey={APIKEY}&number=3")
    similar = sim.json()

    return render_template("recipe-info.html",recipe=response, similar=similar)

@app.route('/explore')
def show_random_recipes():
    res = requests.get(f"{API_BASE_URL}/recipes/random?&number={num_results}&apiKey={APIKEY}")

    response=res.json()['recipes']
    
    return render_template("explore-recipes.html",recipes=response)
 
###########################
### ### User Routes ### ###
###########################
@app.before_request
def add_user_to_g():
    """If logged in, add curr user to Flask global."""
    
    if CURR_USER in session:
        g.user = User.query.get(session[CURR_USER])
        g.user_recipes = [item.recipe_id for item in User.query.get(session[CURR_USER]).recipe_notes]

    else:
        g.user = None
        g.user_recipes= None 


def log_in(user):
    """logs in user by adding to session"""
    session[CURR_USER] = user.id

def log_out():
    """log out user"""
    if session[CURR_USER]:
        del session[CURR_USER]

@app.route('/user/signup', methods=['GET','POST'])
def signup():
    """Handle user signup. Create user and add to DB. Redirect to homepage. If form not valid, present form. If user already exists, present form"""
    if CURR_USER in session:
        del session[CURR_USER]

    form=UserAddForm()

    if form.validate_on_submit():
        try:
            user=User.signup(
                name=form.name.data,
                email=form.email.data,
                password=form.password.data,
                allergies=form.allergies.data
            )
            db.session.commit()
            log_in(user)
            flash(f"Welcome {form.name.data}!",'success')
            return redirect('/user/profile')

        except IntegrityError as e:
            flash("Email already registered",'danger')
            return render_template('user/signup.html', form=form)
    
    return render_template('user/signup.html', form=form)

@app.route('/user/logout')
def log_out_user():
    """log out user"""
    log_out()
    flash("You have successfully logged out.", 'success')
    return redirect("/")

@app.route('/user/login', methods=['GET','POST'])
def log_in_user():
    """log in user"""
    form=UserSignInForm()

    if form.validate_on_submit():
        user = User.authenticate(email=form.email.data, password=form.password.data)
        if user:
            log_in(user)
            flash(f"Welcome back {user.name}", 'success')
            return redirect("/explore")

        else:
            flash("Invalid credentials",'danger')
    
    return render_template("user/login.html", form=form)

@app.route('/user/profile')
def show_user():
    if not g.user:
        flash("Unauthorized access",'danger')
        return redirect('/')
    
    user=g.user

    return render_template("user/profile.html", user=user)


@app.route('/user/edit', methods=['GET','POST'])
def edit_user_profile():
    if not g.user:
        flash("Unauthorized access",'danger')
        return redirect('/')
    
    user=g.user
    form=UserEditForm(obj=user)

    if form.validate_on_submit():
        user.name=form.name.data
        user.allergies = form.allergies.data
        
        db.session.commit()
        flash("Profile updated successfully!",'success')
    return render_template('user/edit-user.html',form=form)

@app.route('/user/delete', methods=['GET','POST'])
def delete_user_profile():
    if not g.user:
        flash("Unauthorized access",'danger')
        return redirect('/')
    
    user=g.user
    form=UserSignInForm()

    if form.validate_on_submit():
        user = User.authenticate(email=form.email.data, password=form.password.data)
        if user:
            db.session.delete(user)
            db.session.commit()
            log_out()
            flash(f"Account deleted", 'success')
            return redirect("/")
        else:
            flash("Invalid credentials",'danger')

    return render_template('user/delete-user.html',form=form)


############################
### ### User Recipes ### ###
############################
@app.route('/user/recipes')
def show_saved_recipes():
    """show user's saved recipes"""
    if not g.user:
        flash("Unauthorized access",'danger')
        return redirect('/')
    u_id = g.user.id

    rec_notes=db.session.query(Recipe.name,Recipe.image_url, Recipe.id, User_Recipe.notes).join(User_Recipe).filter(User_Recipe.user_id==u_id)    

    return render_template('user/saved-recipes.html', recipes=rec_notes)

@app.route('/save_to_recipebox/<int:rec_id>')
def save_user_recipe(rec_id):
    """Save recipe to user's recipebox"""
    if not g.user:
        flash("Unauthorized access",'danger')
        return redirect('/')

    user_id = g.user.id
    recipe=add_recipe_to_database(rec_id)
    
    if User_Recipe.query.filter(User_Recipe.recipe_id == rec_id, User_Recipe.user_id==user_id).first() is None:
        u_r = User_Recipe(user_id=user_id, recipe_id=rec_id)
        db.session.add(u_r)
        db.session.commit()

    return redirect('/user/recipes')

@app.route('/unsave_recipe/<int:rec_id>', methods=['GET'])
def unsave_recipe(rec_id):
    """remove recipe from user's saved recipes"""
    if not g.user:
        flash("Unauthorized access", 'danger')
        return redirect('/')
    
    user_id=g.user.id
    
    u_r = User_Recipe.query.filter(User_Recipe.user_id==user_id, User_Recipe.recipe_id==rec_id).first()
    
    db.session.delete(u_r)
    db.session.commit()

    return redirect('/user/recipes')

@app.route('/recipe/edit/<int:rec_id>',methods=['GET','POST'])
def edit_recipe_notes(rec_id):
    """edit users' recipe notes"""
    if not g.user:
        flash("Unauthorized access", 'danger')
        return redirect('/')
    
    user_id=g.user.id
    user_note = User_Recipe.query.filter(User_Recipe.user_id==user_id, User_Recipe.recipe_id==rec_id).first()
    recipe=Recipe.query.get_or_404(rec_id)
    form = RecipeNoteForm(obj=user_note)

    if form.validate_on_submit():
        user_note.notes=form.notes.data
        db.session.commit()
        flash("Note updated!","success")
        return redirect('/user/recipes')

    return render_template("edit-note.html",form=form, recipe=recipe)


def add_recipe_to_database(rec_id):
    """Check to see if recipe exists in database. If recipe is missing, make 
    api call to add recipe to database. Return Recipe instance."""

    if Recipe.query.filter(Recipe.id == rec_id).first() is None:
        res = requests.get(f"{API_BASE_URL}/recipes/{rec_id}/information?apiKey={APIKEY}")
        rec = res.json()
        recipe = Recipe(id=rec_id, name=rec["title"], image_url= rec["image"], source_url= rec["sourceUrl"], servings=rec["servings"] , ready_in_minutes= rec["readyInMinutes"])
        db.session.add(recipe)
        db.session.commit()

    else:
        recipe = Recipe.query.get(rec_id)

    return recipe 

@app.errorhandler(404)
def page_not_found(e):
    """Set the 404 status explicitly"""
    return render_template('404.html'), 404