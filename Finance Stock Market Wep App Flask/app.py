import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
load_dotenv()
from helpers import apology, login_required, lookup, usd


app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #home page containg table with all infromtion of user of his stocks and cash balance
    #and number of shares that the user have
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    stocks = db.execute(
        "SELECT symbol, SUM(shares) as shares, operation FROM stocks WHERE userID = ? GROUP BY symbol HAVING (SUM(shares)) > 0;",
        session["user_id"],
    )
    #getting name and price and symbol of stock at the current time and passing it to index.html(home page)
    total_cash_stocks = 0
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["total"] = stock["price"] * stock["shares"]
        total_cash_stocks = total_cash_stocks + stock["total"]

    total_cash = total_cash_stocks + user_cash[0]["cash"]
    return render_template(
        "index.html", stocks=stocks, user_cash=user_cash[0], total_cash=total_cash
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    #geting varrabile of user submits
    if request.method == "POST":
        symbol = request.form.get("symbol")
        price = lookup(symbol)
        shares = request.form.get("shares")
        #cash that user have before buy stocks
        user_cash = db.execute(
            "SELECT cash FROM users WHERE id = ? ", session["user_id"]
        )[0]["cash"]
        #check error conditions like invalid symbol or user sumbit invalid symbol of stock
        if not symbol:
            return apology("a valid symbol must be provide", 400)
        elif price is None:
            return apology("must provide valid symbol", 400)
        #check error condtion if the user sumit negative number of shares of stock
        try:
            shares = int(shares)
            if shares < 1:
                return apology("share must be a positive integer", 400)
        except ValueError:
            return apology("share must be a positive integer", 400)
        #calculate the total price of share (price * number of shares)
        shares_price = shares * price["price"]
        #check if usercash suitable for this transaction
        if user_cash < (shares_price):
            return apology("cash is not sufficient", 400)
        #update user cash and number of share from stocks and users table in database
        else:
            db.execute(
                "UPDATE users SET cash = cash - ? WHERE id = ?",
                shares_price,
                session["user_id"],
            )

            db.execute(
                "INSERT INTO stocks (userID, symbol, shares, price, operation) VALUES (?, ?, ?, ?, ?)",
                session["user_id"],
                symbol.upper(),
                shares,
                price["price"],
                shares_price,
            )

            flash("Transaction successful")
            return redirect("/")
    #if request via get
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    #showing total Transacted shares and stock by data and time
    stocks = db.execute("SELECT * FROM stocks WHERE userID = ?", session["user_id"])
    return render_template("history.html", stocks=stocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    """Get stock quote."""
    #querys (search) about stocks name and price and symbol 
    if request.method == "POST":
        symbol = request.form.get("symbol")
        #check error conditon like user submit invalid symbol of stock or blank
        if not request.form.get("symbol"):
            return apology("Missing quote", 400)
        look = lookup(request.form.get("symbol"))
        if look == None:
            return apology("Invalid quote", 400)

        else:
            #passing name and price and symbol of stock

            name = look["name"]
            price = look["price"]
            symbol1 = look["symbol"]
            return render_template("quoted.html",name=name,price=price,symbol1=symbol1)
    #return this html if request via get
    else:
        return render_template("quote.html")






@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #check errors like blank or  name already in database
    if request.method == "POST":
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        password = request.form.get("password")
        confirm = request.form.get("confirmation")
        if len(rows) != 0:
            return apology("name already exists",400)
        if not request.form.get("username"):
            return apology("missing name",400)
        #check the password and confimation password are equal
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("missing password or confirmation",400)
        elif not password == confirm:
            return apology("passwords must match",400)
        else:
            #hasing the password(saltpassword)
            hash = generate_password_hash(password,method="pbkdf2:sha256", salt_length=8)
            #insert new user to database
            db.execute("INSERT INTO users(username,hash) VALUES(?,?)",username,hash)
            return redirect("/")

    #if sending via get request
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    #check if user can efford number of shares that he submits
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        try:
            shares = int(shares)
            if shares < 1:
                return apology("shares must be a positive integer")
        except ValueError:
            return apology("shares must be a positive integer")
        #error checking
        if not symbol:
            return apology("missing symbol")
        #check if user has number of shares that he want to sell it
        stocks = db.execute(
            "SELECT SUM(shares) as shares FROM stocks WHERE userID = ? AND symbol = ?;",
            session["user_id"],
            symbol,
        )[0]

        if shares > stocks["shares"]:
            return apology("You don't have this number of shares")
        price = lookup(symbol)["price"]
        #total value of share price
        shares_value = price * shares
        #insert to database the new updates of selled shares
        db.execute(
            "INSERT INTO stocks (userID, symbol, shares, price, operation) VALUES (?, ?, ?, ?, ?)",
            session["user_id"],
            symbol.upper(),
            -shares,
            price,
            "sell",
        )
        #update the new cash balance of user after selling his stocks
        db.execute(
            "UPDATE users SET cash = cash + ? WHERE id = ?",
            shares_value,
            session["user_id"],
        )

        flash("Sold!")
        return redirect("/")
    else:
        stocks = db.execute(
            "SELECT symbol FROM stocks WHERE userID = ? GROUP BY symbol",
            session["user_id"],
        )
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
