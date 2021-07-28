import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

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
    """Show portfolio of stocks"""

    stocksdict = {}

    shares = db.execute("SELECT SUM(shares) FROM stocks WHERE id = ? GROUP BY stock ", session["user_id"])
    shareslength = len(shares)

    stocks = db.execute("SELECT * FROM stocks WHERE id = ? GROUP BY stock", session["user_id"])

    cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    cash = cash[0]["cash"]

    totalcash = cash

    for i in range(shareslength):
        stocksdict[i] = {
            "symbol" : stocks[i]["symbol"],
            "name"   : stocks[i]["stock"],
            "shares" : shares[i]["SUM(shares)"],
            "price"  : lookup(stocks[i]["symbol"])["price"]
        }

        totalamount = stocksdict[i]["shares"] * stocksdict[i]["price"]
        totalcash += totalamount

    return render_template("index.html", stocksdict=stocksdict, cash=cash, totalcash=totalcash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if(symbol == "" or shares == ""):
            return apology("All fields are required", 400)

        elif(shares.isnumeric() != True):
            return apology("Number of shares are invalid", 400)

        elif(int(shares) <= 0):
            return apology("Number of shares are invalid", 400)


        shares = int(shares)
        if lookup(symbol) == None:
             return apology("Invalid Symbol", 400)
        else:
            stock = lookup(symbol)
            name = stock["name"]
            price = stock["price"]
            symbol = stock["symbol"]

            cashrow = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash = cashrow[0]["cash"]

            purchased = (price*shares)

            if(purchased > cash):
                return render_template("buy.html", message = "You don't have enough cash to complete this transcation")

            db.execute("INSERT INTO stocks (id, symbol, stock, shares, price, date) values(?,?,?,?,?,CURRENT_TIMESTAMP)"
            , session["user_id"], symbol, name, shares, price)

            #Updating the cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash-purchased, session["user_id"])

            return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT symbol, shares, price, date FROM stocks WHERE id = ? ORDER BY date DESC", session["user_id"])

    return render_template("history.html", rows=rows)

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
    if request.method == "POST":

        symbol = request.form.get("symbol")

        if(symbol == ""):
            return apology("Symbol is required", 400)

        if lookup(symbol) == None:
             return apology("Invalid Symbol", 400)
        else:
            stock = lookup(symbol)
            name = stock["name"]
            price = stock["price"]
            symbol = stock["symbol"]

            return render_template("quoted.html", name=name, price=price, symbol=symbol, stock = stock)

        return redirect("quoted")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username");
        password = request.form.get("password");
        confirmation = request.form.get("confirmation");

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if(username == "" or password == "" or confirmation == ""):
            return apology("All fields are required", 400)

        elif(password != confirmation):
            return apology("Passwords don't match", 400)


        # # Ensure username exists and password is correct
        if len(rows) == 1:
            # return render_template("register.html", message="Username already taken")
            return apology("Username already taken", 400)

        p = generate_password_hash(request.form.get("password"));

        db.execute("INSERT INTO users (username, hash) VALUES(?,?)", username, p);

        # Redirect user to home page
        return redirect("login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        #validate the # of shares
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if(symbol == "" or shares == ""):
            return apology("All fields are required", 400)

        elif(shares.isnumeric() != True):
            return apology("Number of shares are invalid", 400)

        elif(int(shares) <= 0):
            return apology("Number of shares are invalid", 400)

        shares = int(shares)

        rows = db.execute("SELECT SUM(shares) FROM stocks WHERE id = ? AND symbol = ? ", session["user_id"], symbol)
        currentshares = rows[0]["SUM(shares)"]
        print(currentshares)

        if( currentshares < shares):

            return apology("You don't have enough shares", 400)
        else:

            #Update the database
            stock = lookup(symbol)
            name = stock["name"]
            price = stock["price"]
            symbol = stock["symbol"]

            cashrow = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash = cashrow[0]["cash"]

            sold = (price*shares)
            print(sold)
            print(cash+sold)

            db.execute("INSERT INTO stocks (id, symbol, stock, shares, price, date) values(?,?,?,?,?,CURRENT_TIMESTAMP)"
            , session["user_id"], symbol, name, -shares, price)

            #Updating the cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash+sold, session["user_id"])

            return redirect("/")

    else:

        shares = db.execute("SELECT SUM(shares) FROM stocks WHERE id = ? GROUP BY stock ", session["user_id"])
        shareslength = len(shares)

        stocks = db.execute("SELECT * FROM stocks WHERE id = ? GROUP BY stock", session["user_id"])

        return render_template("sell.html", shareslength=shareslength, stocks=stocks)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
