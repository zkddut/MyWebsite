from cs50 import SQL
from flask import flash, redirect, render_template, request, session, url_for, send_from_directory, abort, Markup, Response
from app import app
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
import datetime
from app.helpers import *
from flask_sqlalchemy import SQLAlchemy
import os
from twilio.twiml.messaging_response import MessagingResponse, Message
from twilio.rest import Client
import urllib
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache
from time import gmtime, strftime

#TODO: 1. Flask + SQLalchmey http://flask-sqlalchemy.pocoo.org/2.3/quickstart/
#TODO: 2. Seperate files for application.py
#TODO: 3. Implement feature for twillo
#      3.1 Upload image

# global variable
user_id = 0

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
account_sid = "AC848322965649be07a6f69b5f86336424"
auth_token = "078646e981762318d5aeb167ce1d0feb"
client = Client(account_sid, auth_token)

@app.route("/")
@login_required
def index():
    if request.method == "POST":
        return render_template("index.html")
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # 1. which stocks the user owns,
        # 2. the numbers of shares owned,
        # 3. the current price of each stock,
        # 4. the total value of each holding (i.e., shares times price).
        # 5. Also display the user’s current cash balance along with
        # 6. a grand total (i.e., stocks' total value plus cash).

        user_id = session["user_id"]
        users_stock_rows = db.execute("SELECT * FROM users_stock WHERE id = :user_id ", user_id=user_id)
        users_rows = db.execute("SELECT * FROM users WHERE id = :user_id ", user_id=user_id)
        username = users_rows[0]["username"]
        cash = users_rows[0]["cash"]
        total = cash
        stocks = []
        for row in users_stock_rows:
            lookup_result = lookup(row["symbol"])
            stock = { "symbol":row["symbol"], "share":row["share"], "price":lookup_result["price"], "value":lookup_result["price"]*row["share"]}
            total += lookup_result["price"]*row["share"]
            stocks.append(stock)
        return render_template("index.html", username=username, cash=cash, total=total, stocks=stocks)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol")

        # ensure share was submitted
        if not request.form.get("share"):
            return apology("must provide share")

        symbol = request.form.get("symbol")
        share = float(request.form.get("share"))
        result = lookup(symbol)

        if (not result):
            return apology("Could not find symbol %s" % (symbol))

        if (share <= 0):
            return apology("Need to specify a positive number")

        rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])

        user_id = session["user_id"]
        tran_status="bought"
        price=result["price"]
        time=str(datetime.datetime.now())
        new_cash = rows[0]["cash"] - share*float(result["price"])

        if (new_cash < 0):
            return apology("You don't have enough cash")
        else:
            db.execute("INSERT INTO 'transactions_tracking' (user_id, symbol, tran_status, price, share, time) VALUES (:user_id, :symbol, :tran_status, :price, :share, :time)", user_id=user_id, symbol=symbol, tran_status=tran_status, price=price, share=share, time=time)
            db.execute("UPDATE 'users' SET cash = :cash where id = :id ", id=user_id, cash=new_cash)
            rows = db.execute("SELECT * FROM users_stock WHERE id = :user_id AND symbol = :symbol", user_id=user_id, symbol=symbol)
            if (len(rows) == 0):
                db.execute("INSERT INTO 'users_stock' (id, symbol, share) VALUES (:id, :symbol, :share)", id=user_id, symbol=symbol, share=share)
            else:
                new_share = rows["share"] + share
                db.execute("UPDATE 'users_stock' SET share = :share where id = :id AND symbol=:symbol ", id=user_id, symbol=symbol, share=new_share)

        return render_template("buy.html", condition=1)
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html", condition=0)

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    if request.method == "POST":
        return render_template("history.html")
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        user_id = session["user_id"]
        form = db.execute("SELECT * FROM 'transactions_tracking' WHERE user_id = :user_id ", user_id=user_id)
        return render_template("history.html", form=form)

@app.route("/game")
#@login_required
def game():
    """Show history of transactions."""
    if request.method == "POST":
        return render_template("game.html")
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("game.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
#@login_required
def quote():
    """Get stock quote."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol")

        symbol = request.form.get("symbol")

        result = lookup(symbol)

        if (result):
            # render quoted html
            return render_template("quoted.html", name=result['name'], symbol=result['symbol'], price=usd(result['price']))
        else:
            return apology("Could not find symbol %s" % (symbol))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # ensure password was submitted
        elif not request.form.get("repeat_password"):
            return apology("must provide repeat password")

        username = request.form.get("username")
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        # ensure username already exists
        if (len(rows) >= 1):
            return apology("username: %s already exist" % (username))

        # check password and repeat password is the same
        password = request.form.get("password")
        repeat_password = request.form.get("repeat_password")
        if (password != repeat_password):
            return apology("passwords do not match")

        # INSERT the new user into users with hashed password
        hash_password = pwd_context.hash(password)
        rows = db.execute("INSERT INTO 'users' (username, hash) VALUES (:username, :hash)", username=username, hash=hash_password)

        # redirect user to home page
        return redirect(url_for("login"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol")

        # ensure share was submitted
        if not request.form.get("share"):
            return apology("must provide share")

        symbol = request.form.get("symbol")
        share = float(request.form.get("share"))
        result = lookup(symbol)
        user_id = session["user_id"]

        if (not result):
            return apology("Could not find symbol %s in the market" % (symbol))

        if (share <= 0):
            return apology("Need to specify a positive number")

        stock_rows = db.execute("SELECT * FROM users_stock WHERE id = :user_id AND symbol = :symbol", user_id=user_id, symbol=symbol)

        find_stock = None
        for stock in stock_rows:
            if(stock["symbol"] == symbol):
                find_stock = stock;
                break;

        if(find_stock == None):
            return apology("You don't have stock %s" % (symbol))

        if(share > find_stock["share"]):
            return apology("You don't have enough stock %s share" % (symbol))
        else:
            new_share = find_stock["share"] - share
        rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
        tran_status="sell"
        price=result["price"]
        time=str(datetime.datetime.now())
        new_cash = rows[0]["cash"] + share*float(result["price"])

        db.execute("INSERT INTO 'transactions_tracking' (user_id, symbol, tran_status, price, share, time) VALUES (:user_id, :symbol, :tran_status, :price, :share, :time)", user_id=user_id, symbol=symbol, tran_status=tran_status, price=price, share=share, time=time)
        db.execute("UPDATE 'users' SET cash = :cash where id = :id ", id=user_id, cash=new_cash)

        if (new_share == 0):
            db.execute("DELETE from 'users_stock' where id = :id AND symbol=:symbol ", id=user_id, symbol=symbol)
        else:
            db.execute("UPDATE 'users_stock' SET share = :share where id = :id AND symbol=:symbol ", id=user_id, symbol=symbol, share=new_share)

        return render_template("sell.html")
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")


@app.route("/funtext", methods=["GET", "POST"])
#@login_required
def funtext():
    if request.method == "POST":
        message = request.form.get('Message')
        to_number = request.form.get('phone')

        # Grab the relevant phone numbers.
        from_number = "+14243610437"
        to_number = "+1{}".format(to_number)

        client.messages.create(
            to= to_number,
            from_= from_number,
            body=message
        )

        return render_template("funtext.html", sent = True)
    else:
        return render_template("funtext.html", sent = False)

@app.route('/images/<filename>')
def send_image(filename):
    return send_from_directory("images", filename)

@app.route('/myblogIndex')
#@login_required
def myblogIndex():
    #db.execute("DROP TABLE blog")
    #db.execute("CREATE TABLE blog (id int, title varchar(255), content varchar(65535), image_name varchar(255), timestamp varchar(255))")
    query = db.execute("SELECT * FROM blog ORDER BY timestamp DESC")
    #print (query)
    return render_template("blogIndex.html", entries=query)

@app.route('/createMyBlog', methods=["GET", "POST"])
#@login_required
def createMyBlog():
    if request.method == "POST":
        target = os.path.join(APP_ROOT, 'images/')
        print(target)

        if not os.path.isdir(target):
            os.mkdir(target)

        for file in request.files.getlist("file"):
            print(file)
            filename = file.filename
            destination = "/".join([target, filename])
            print(destination)
            file.save(destination)

        title = request.form.get('title')
        content = request.form.get('content')
        image_name = filename
        timestamp = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        db.execute(
            "INSERT INTO 'blog' (id, title, content, image_name, timestamp) VALUES (:id, :title, :content, :image_name, :timestamp)",
            id=0, title=title, content=content, image_name=image_name, timestamp=timestamp)
        return redirect(url_for('myblogIndex'))
    else:
        return render_template("blogCreate.html")

if __name__ == "__main__":
	app.run()
