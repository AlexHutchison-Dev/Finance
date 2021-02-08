import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.request import Request, urlopen

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    holdings= db.execute("SELECT * FROM stocks WHERE user = ?", session["user_id"])
    app.logger.info(user)
    #declare and intitialize total to user["cash"]
    total = user[0]["cash"]

    #update holdings price's with current value
    for holding in holdings:

        data =lookup(holding[("symbol")])
        holding["price"] = usd(data["price"])
        holding["value"] = holding["qty"] * data["price"]

        total = total + holding["value"]
        holding["value"] = usd(holding["value"])

    #add total to user
    user[0]["total"] = usd(total)
    user[0]["cash"] = usd(user[0]["cash"])



    return render_template("index.html", user = user, holdings = holdings)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":
        #check that a symbol was enetered
        if not request.form.get("symbol"):
            return apology("enter a symbol")
        #check that a quantity was entered
        if not request.form.get("shares"):
            return apology("enter a quantity of Shares to buy")

        else:

            #get user data from database
            user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
            #getstock data from database
            data =lookup(request.form.get("symbol"))
            #check validity of symbol by checking for returned data
            if not data:
                return apology("enter valid symbol")


            #declare and initialise variables for insertion into database
            userId = session["user_id"]
            symbol = request.form.get("symbol")
            price = float(data["price"])
            qty = int(request.form.get("shares"))
            name = data["name"]

            #calculate cost of transaction
            cost = qty * price
            app.logger.info(userId)
            app.logger.info(user)



            #check that the user has sufficient funds
            if cost > user[0]["cash"]:
                return apology("Insufficient Funds")

            #update transactions db
            db.execute("INSERT into transactions (user,symbol,price,qty,buy) VALUES (?,?,?,?,?)",userId,symbol,price,qty,1)

            #get id for row in transactions
            trans_id = []
            trans_id = db.execute("Select last_insert_rowid() from transactions")
            app.logger.info(trans_id)

            #remove cost from users cash ballance
            db.execute("UPDATE users SET cash=? WHERE id=?", user[0]["cash"] - cost, userId)

            #check for previous owner ship of this stock
            stocks = db.execute("SELECT * FROM stocks WHERE user=?", userId)
            app.logger.info(stocks)

            #itterater over stocks to check for current ownership

            for stock in stocks:
                #if this stock matches purchased stock increase qty
                if stock["symbol"] == symbol:
                    qty += stocks[0]["qty"]
                    #update stocks db
                    db.execute("UPDATE stocks SET qty=? WHERE user=? AND symbol=?", qty, userId, symbol)
                    return redirect("/")
            #if no current ownership add new row for purchased stock to stocks table

            #insert into stocks.db
            db.execute("INSERT into stocks (user, transId, symbol, qty, name) VALUES (?,?,?,?,?)", userId, trans_id[0]['last_insert_rowid()'], symbol, qty, name)
            return redirect("/")


    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    #get tranaction history for the logged in user
    transactions = db.execute("SELECT * FROM transactions WHERE user=? ORDER BY date DESC", session["user_id"])
    app.logger.info(transactions)
    return render_template("/history.html", transactions = transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    app.logger.info("request /quote")

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("enter a symbol")

        else:
            app.logger.info(request.form.get("symbol"))
            data =lookup(request.form.get("symbol"))
            return render_template("price.html", name = data["name"], symbol = data["symbol"], price = usd(data["price"]))
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():



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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Check if username exists and report if so
        if len(rows) != 0 :
            return apology("a with that username is already registered", 403)

        # Add new user with form credentials
        else:


            db.execute("INSERT INTO users (username,hash) VALUES (?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

            # Return the index page
            return redirect("/login")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        #check symbol was selected
        if not request.form.get("symbol"):
            return apology("enter a symbol")
        #check that a quantity was entered
        if not request.form.get("shares"):
            return apology("enter a quantity of Shares to buy")

        else:
            shares = int(request.form.get("shares"))
            #get qty of this stock
            holding = db.execute("SELECT qty FROM (SELECT * FROM stocks WHERE user=?) WHERE symbol=?", session["user_id"], request.form.get("symbol"))

            #check that user own more than they are trying to sell
            if holding[0]["qty"] < shares:
                return apology("You dont own that many shares of {0}".format(request.form.get("symbol")))
            else:
                #get current value of requested stock
                data = lookup(request.form.get("symbol"))
                returns = shares * data["price"]

                #check if new qty will be == 0
                if holding[0]["qty"] - shares == 0:
                    db.execute("DELETE FROM (SELECT * FROM stocks WHERE user=?) WHERE symbol=?", session["user_id"], request.form.get("symbol"))
                else:
                    #update stocks db to show qty remaining
                    stock_id = db.execute("SELECT id FROM (SELECT * FROM stocks WHERE user=?) WHERE symbol=?", str(session["user_id"]), request.form.get("symbol"))
                    app.logger.info(stock_id[0]["id"])
                    qty = (holding[0]["qty"] - shares)
                    db.execute("UPDATE stocks SET qty=? WHERE id=?",qty, stock_id[0]["id"])

                    #get users cash value
                    cash = db.execute("SELECT cash from users WHERE id=?", session["user_id"])
                    new_cash = cash[0]["cash"] + returns

                    #update users cash to new value
                    db.execute("UPDATE users SET cash=? WHERE id=?",new_cash, session["user_id"])
                    #add transaction to transaction db
                    db.execute("INSERT INTO transactions (user, symbol, price, qty, buy) VALUES (?,?,?,?,?)", session["user_id"],data["symbol"], data["price"], shares, 0)


            return redirect("/")
    else:

        #get list of symbolss for owned stocks
        holdings = db.execute("SELECT DISTINCT symbol FROM (SELECT * FROM stocks WHERE user=?)",session["user_id"])
        return render_template("sell.html", holdings = holdings)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
