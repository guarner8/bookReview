import os
import requests
import json

from flask import Flask, session, request, render_template, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    try:
        user = session["username"]
        return render_template("index.html", user=user)
    except:
        return redirect(url_for('login'))

@app.route("/book/<string:isbn>")
def book(isbn):
    if session.get("username") == None:
        return redirect(url_for('login'))
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "FftWe8lZeHrsgiwNllJWfg", "isbns": isbn})
    book_api = res.json()
    book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn":isbn}).fetchone()
    reviews = db.execute("SELECT * FROM reviews INNER JOIN users ON users.id =user_id WHERE book_id=:book_id", {"book_id":book.id}).fetchall()
    return render_template("book.html", book=book, book_api=book_api, reviews=reviews, user=session["username"])

@app.route("/api/<string:isbn>")
def api(isbn):
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "FftWe8lZeHrsgiwNllJWfg", "isbns": isbn})
    book_api = res.json()
    book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn":isbn}).fetchone()
    reviews = db.execute("SELECT * FROM reviews, users WHERE book_id=:book_id", {"book_id":book.id}).fetchall()
    return jsonify({
            "title": book.title,
            "author": book.author,
            "year": int(book.year),
            "isbn": isbn,
            "review_count": book_api['books'][0]['work_ratings_count'],
            "average_score":float(book_api['books'][0]['average_rating']) 
        })

@app.route("/search", methods=["POST"])
def search():
    if session.get("username") == None:
        return redirect(url_for('login'))

    isbn = '%' + request.form.get("isbn") + '%'
    title = '%' + request.form.get("title") + '%'
    author = '%' + request.form.get("author") + '%'
    if isbn == None:
        isbn = ""
    if title == None:
        title = ""
    if author == None:
        author = ""
    books = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn AND title LIKE :title AND author LIKE author", {"isbn": isbn, "author": author, "title": title}).fetchall()
    if books == []:
        return render_template('index.html', error="No results found!", user=session["username"])
    return render_template("index.html", books=books, user=session["username"])

@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        check = db.execute("SELECT id FROM users WHERE username = :username", {"username": username}).fetchone() 
        if check == None:
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username":username, "password":password})
            db.commit()
            session["username"] = username;
            return redirect(url_for('index'))
        else: 
            return render_template('register.html', error="Username is taken!")
    return render_template("register.html")

@app.route("/login", methods=["POST", "GET"])
def login():
    session.pop('username', None)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = db.execute("SELECT * FROM Users WHERE username = :username", {"username": username}).fetchone()
        if user is None:
            return render_template("login.html", error="Wrong username, have you tried registering?")
        elif user.password != password:
            return render_template("login.html", error="Wrong Password")
        else:
            session["username"] = username
            return redirect(url_for('index'))
    else:
        return render_template("login.html")

@app.route("/review/<string:isbn>", methods=["POST"])
def review(isbn):
    if session.get("username") == None:
        return redirect(url_for('login'))

    username=session["username"]
    user = db.execute("SELECT * FROM users WHERE username=:username", {"username":username}).fetchone()
    book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn":isbn}).fetchone()
    review = db.execute("SELECT * FROM reviews JOIN users ON user_id=users.id JOIN books ON book_id=books.id WHERE username=:username AND title=:title", {"username":username, "title":book.title}).fetchone()
    rating = request.form.get("rating")
    text = request.form.get("review_text")

    if review != None or rating == None or text == "":
        if text == None or rating == None:
            error="Plese input both rating and review!"
        if review != None:
            error="You cannot add two reviews for the same book!"

        # Plug in your api key here!
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "FftWe8lZeHrsgiwNllJWfg", "isbns": isbn})
        book_api = res.json()
        reviews = db.execute("SELECT * FROM reviews JOIN users ON users.id = user_id WHERE book_id=:book_id", {"book_id":book.id}).fetchall()
        return render_template('/book.html', error=error, book=book, reviews=reviews, book_api=book_api, user=session["username"])

    else:
        db.execute("INSERT INTO reviews (review, rating, user_id, book_id) VALUES (:review, :rating, :user_id, :book_id)", {"review": text, "rating": rating, "user_id":user.id, "book_id":book.id})
        db.commit()
        return redirect(f"book/{isbn}")
    
@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


