import os
import sqlite3
from sqlite3 import Error

from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from flask_login import LoginManager
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import *

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Get absolute path of uploads folder
dirname = os.path.dirname(__file__)
app.config["UPLOADS"] = os.path.join(dirname, "static/uploads")
app.config["USR_UPLOADS"] = os.path.join(dirname, "static/uploads")
app.config["MAP_UPLOADS"] = os.path.join(dirname, "static/uploads/maps")

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Create database connection to the SQLite database
conn = None
try:
    conn = sqlite3.connect("robots.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
except Error as e:
    print(e)

@app.route("/")
def index():
    """Homepage of robot manager"""

    if not session:
        return redirect("/login")

    cur = conn.cursor()
    robots = cur.execute("SELECT * FROM robots WHERE user_id=?", (session["user_id"],))
    # Redirect user to home page
    return render_template("index.html", robots=robots)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=:username", {"username": request.form.get("username")})

        rows = cur.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][3], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0][0]
        session["username"] = rows[0][1]
        session["name"] = rows[0][2]

        # Update uploads folder to include user
        app.config["USR_UPLOADS"] = os.path.join(app.config["UPLOADS"], session["username"])
        app.config["MAP_UPLOADS"] = os.path.join(app.config["USR_UPLOADS"], "maps")
        print(app.config["MAP_UPLOADS"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/maps", methods=["GET", "POST"])
def maps():
    if not session:
        return redirect("/login")

    # Adds a map to the database and to the file server
    if request.method == "POST":
        if "mapImage" in request.files and "yamlFile" in request.files:

            # Request map image and yaml file 
            map_image = request.files["mapImage"]
            yml = request.files["yamlFile"]

            # Ensure that map image and yaml file 
            if map_image.filename == "" or yml.filename == "":
                return apology("No filename", 400)

            if allowed_image(map_image.filename) and allowed_yaml(yml.filename):
                map_filename = secure_filename(map_image.filename)
                map_image.save(os.path.join(app.config["MAP_UPLOADS"], map_filename))
                
                yml_filename = secure_filename(yml.filename)
                yml.save(os.path.join(app.config["MAP_UPLOADS"], yml_filename))
                
                # Get map name
                map_name = map_filename.rsplit(".", 1)[0]
                
                # Connect to database
                cur = conn.cursor()

                # Check if map already exists in database
                cur.execute("SELECT * FROM maps WHERE map_name=? AND user_id=?", (map_name, session["user_id"]))
                rows = cur.fetchall()
                if len(rows) > 0:
                    return apology("Map already exists", 400)
                
                # Update database with map
                cur.execute("INSERT INTO maps (user_id, map_name, mapfile, yamlfile) VALUES (?, ?, ?, ?)", (session["user_id"], map_name,  map_filename, yml_filename))
                conn.commit()
                
                return redirect(request.url)

            else:
                return apology("Invalid filename", 400)
        
        else:
            return apology("Please upload map image and yaml file", 400)

    cur = conn.cursor()
    maps = cur.execute("SELECT * FROM maps WHERE user_id=?", (session["user_id"],))

    return render_template("maps.html", maps=maps)

@app.route("/delete_map", methods=["POST"])
def delete_map():
    """
        Function to delete map from database
    """

    # Check that user has logged in
    if not session:
        return redirect("/login")

    # Get map data from database
    cur = conn.cursor()
    cur.execute("SELECT * FROM maps WHERE id=(?)", (request.form.get("map_id")))
    row = cur.fetchone()

    # Delete map files
    img_path = os.path.join(app.config["MAP_UPLOADS"], row[3])
    yml_path = os.path.join(app.config["MAP_UPLOADS"], row[4])
    
    if os.path.isfile(img_path):
        os.remove(img_path)

    if os.path.isfile(yml_path):
        os.remove(yml_path)
    
    # Delete map from database
    cur.execute("DELETE FROM maps WHERE id=(?)", (request.form.get("map_id")))
    conn.commit()

    return redirect("/maps")

@app.route("/robots", methods=["GET", "POST"])
def robots():
    """
        Display list of robots, allows user to add robot
    """
    # Check that user is logged in
    if not session:
        return redirect("/login")

    # Adds a robot to the database
    if request.method == "POST":

        # Get robot data from form
        robot_name = request.form.get("robot_name")
        robot_type = request.form.get("robot_type")
        ip_address = request.form.get("ip_address")

        # Connect to database
        cur = conn.cursor()
        
        # Check if robot already exists
        cur.execute("SELECT * FROM robots WHERE robot_name=? AND user_id=?", (robot_name, session["user_id"]))
        rows = cur.fetchall()
        if len(rows) > 0:
            return apology("IP Address already in use", 400)

        # Check if ip address is used
        cur.execute("SELECT * FROM robots WHERE ip_address=? AND user_id=?", (ip_address, session["user_id"]))
        rows = cur.fetchall()
        if len(rows) > 0:
            return apology("IP Address already in use", 400)

        # Update database with robot
        cur.execute("INSERT INTO robots (user_id, robot_name, robot_type, ip_address) VALUES (?, ?, ?, ?)", (session["user_id"], robot_name,  robot_type, ip_address))
        conn.commit()

        return redirect(request.url)

    cur = conn.cursor()
    robots = cur.execute("SELECT * FROM robots WHERE user_id=?", (session["user_id"],))
    return render_template("robots.html", robots=robots)

@app.route("/update_robot", methods=["POST"])
def update_robot():
    """
        Function to update robot info
    """

    # Get robot update data from form
    robot_id = request.form.get("robot_id")
    robot_name = request.form.get("robot_name")
    robot_type = request.form.get("robot_type")
    ip_address = request.form.get("ip_address")

    # Get data for robot
    cur = conn.cursor()

    cur.execute("SELECT * FROM robots WHERE id=? AND user_id=?", (robot_id, session["user_id"]))
    rows = cur.fetchall()

    # Check if robot exists in database
    if len(rows) == 0:
        return apology("Robot not in database", 400)

    # Check that IP address has not already been in use
    cur.execute("SELECT ip_address FROM robots WHERE user_id=?", (session["user_id"],))
    rows = cur.fetchall()
    for row in rows:
        if row[0] == ip_address:
            return apology("IP Address already in use", 400)

    cur.execute("UPDATE robots SET robot_name=?, robot_type=?, ip_address=? WHERE id=?", (robot_name, robot_type, ip_address, robot_id))
    conn.commit()

    return redirect("/robots")


@app.route("/delete_robot", methods=["POST"])
def delete_robot():
    """
        Function to delete map from database
    """

    # Check that user has logged in
    if not session:
        return redirect("/login")

    cur = conn.cursor()

    # Delete map from database
    cur.execute("DELETE FROM robots WHERE id=(?)", (request.form.get("robot_id")))
    conn.commit()

    return redirect("/robots")


@app.route("/tasks")
def tasks():
    return render_template("tasks.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("login")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        name = username.capitalize()

        if request.form.get("name"):
            name = request.form.get("name").capitalize()

        pwhash = generate_password_hash(request.form.get("password"))

        # Insert username, name and password hash value into database
        cur = conn.cursor()

        # Check if username already exists in database
        cur.execute("SELECT * FROM users WHERE username=:username", {"username": username})
        rows = cur.fetchall()
        
        if len(rows) > 0:
            return apology("Username Already Exists", 400)

        # Commit new user into database
        cur.execute("INSERT INTO users (username, name, hash) VALUES(?, ?, ?)", (username, name, pwhash))
        cur.execute("SELECT * FROM users WHERE username=:username", {"username": username})
        rows = cur.fetchall()
        conn.commit()

        # Create new user folder in uploads directory
        usr_folder = os.path.join(app.config["UPLOADS"], username)
        if not os.path.exists(usr_folder):
            os.makedirs(os.path.join(usr_folder,"maps"))
            os.makedirs(os.path.join(usr_folder,"tasks"))
            # Update user path
            app.config["USR_UPLOADS"] = usr_folder

        # Remember which user and log in
        session["user_id"] = rows[0][0]
        session["username"] = username
        session["name"] = name

        return redirect("/")
    # User reached route via GET
    else:
        return render_template("register.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """Log user in"""

    # Forget any user_id
    session.clear()
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for 1st user account in database (admin account)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=:id", {"id": "1"})
        rows = cur.fetchall()

        # Ensure admin account exists and password of admin account is correct
        if len(rows) == 1 and check_password_hash(rows[0][3], request.form.get("password")):
            session["username"] = rows[0][1]
            # Redirect user to home page
            return redirect("/change_password")

        else:
            return redirect("/forgot_password")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("forgot_password.html")

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    """Allow users to change password"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Set cursor for database
        cur = conn.cursor()

        # If user is changing password from forgot_password route
        if "username" not in session:
            username = request.form.get("username")

            # Check if username exists in database
            cur.execute("SELECT * FROM users WHERE username=:username", {"username": username})
            rows = cur.fetchall()
            if len(rows) == 0:
                return apology("User Does Not Exist", 400)
        else:
            # Check if username already exists in database
            cur.execute("SELECT * FROM users WHERE username=:username", {"username": session["username"]})
            rows = cur.fetchall()
            if not check_password_hash(rows[0][3], request.form.get("old_password")):
                return apology("Wrong Password", 400)
        username = rows[0][1]

        # Get new password from the user
        new_pwhash = generate_password_hash(request.form.get("password"))

        # Update database with new password
        cur.execute("UPDATE users SET hash = ? WHERE username = ?", (new_pwhash, username))
        cur.execute("SELECT * FROM users WHERE username=:username", {"username": username})
        rows = cur.fetchall()
        conn.commit()

        # Remember and login user
        session["user_id"] = rows[0][0]
        session["username"] = rows[0][1]
        session["name"] = rows[0][2]

        # Redirect user to homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # If user is changing password from forgot_password route
        if "username" not in session:
            # if session["username"] != rows[0][1]:
            return render_template("forgot_password.html")
        else:
            # Query database for 1st user account in database (admin account)
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id=:id", {"id": "1"})
            rows = cur.fetchall()
            # Forget admin user login
            if session["username"] == rows[0][1] and "user_id" not in session:
                session.clear()
            return render_template("change_password.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
