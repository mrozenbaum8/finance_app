import os
import datetime
#api_token='pk_19d7a0519ad14a1ab9ed7113b9c87fa4'

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
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
    portfolios = db.execute("SELECT company_symbol, company_name, company_shares, price FROM purchases WHERE buyer_id = ?", session["user_id"])

    if not portfolios:
        return render_template("index_empty.html")

    """Show portfolio's total balance"""
    portfolio_total = 0
    for folio in portfolios:
        tmp = folio["company_shares"] * folio["price"]
        portfolio_total += tmp

    """Show user's cash balance"""
    usr_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    grand_total = portfolio_total + usr_cash[0]['cash']

    return render_template("index.html", portfolio=portfolios, cash=usr_cash[0]['cash'], portfolio_total=portfolio_total, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':
        stock = request.form.get("symbol")
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Provide valid number!", 400)
        if not stock:
            return apology("Provide valid company!", 400)
        elif shares < 1:
            return apology("Provide valid number!", 400)

        company = lookup(request.form.get("symbol"))

        if company == None:
            return apology("Provide valid company!", 400)

        if company["name"]:
            stock_price = float(company["price"])
            transaction = stock_price * shares
            available = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            available_cash = float(available[0]["cash"])

            if transaction <= available_cash:
                #Complete purchase
                timestamp = datetime.datetime.now()

                in_portfolio = db.execute("SELECT * FROM purchases WHERE buyer_id = ?", session["user_id"])

                for item in in_portfolio:
                    if company["symbol"] == item["company_symbol"]:
                        previous_shares = item["company_shares"]

                        update_shares = previous_shares + shares

                        db.execute("UPDATE purchases SET company_shares = ?, price = ?, timestamp = ? WHERE buyer_id = ? AND company_symbol = ?", update_shares, stock_price, timestamp, session["user_id"], company["symbol"])

                        db.execute("INSERT INTO journal (symbol, shares, price, transacted, buyer_id, type) VALUES (?, ?, ?, ?, ?, ?)", company["symbol"], shares, stock_price, timestamp, session["user_id"], "bought")

                        new_cash = available_cash - transaction

                        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

                        return redirect("/")


                db.execute("INSERT INTO purchases (company_symbol, company_name, company_shares, price, timestamp, buyer_id) VALUES (?, ?, ?, ?, ?, ?)", company["symbol"], company["name"], shares, stock_price, timestamp, session["user_id"])

                db.execute("INSERT INTO journal (symbol, shares, price, transacted, buyer_id, type) VALUES (?, ?, ?, ?, ?, ?)", company["symbol"], shares, stock_price, timestamp, session["user_id"], "bought")

                new_cash = available_cash - transaction

                db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

                return redirect("/")

            else:
                return apology("Not enough money!", 400)
        else:
            return apology("Company does not exist!", 400)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    """Show portfolio of stocks"""
    j_portfolios = db.execute("SELECT type, transacted, symbol, shares, price FROM journal WHERE buyer_id = ?", session["user_id"])

    if not j_portfolios:
        return apology("You don't have any transactions!", 403)

    return render_template("history.html", portfolio=j_portfolios)


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
        company = lookup(request.form.get("symbol"))

        if company == None:
            return apology("Provide valid company!", 400)

        price = company["price"]

        return render_template("quoted.html", company=company['name'], price=price)

    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        # Ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords must match", 400)

        usr_list = db.execute("SELECT username FROM users")
        usr = request.form.get("username")
        pss = request.form.get("password")

        users = []

        for user in usr_list:
            users.append(user["username"])

        if usr in users:
            return apology("Username already exists!", 400)

        if usr and pss:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", usr, generate_password_hash(pss))
            flash('Registration successful!')
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stock_selection = db.execute("SELECT company_symbol FROM purchases WHERE buyer_id = ?", session["user_id"])

    if request.method == "POST":
        to_sell = request.form.get("symbol")

        selections = []

        for stock in stock_selection:
            selections.append(stock['company_symbol'])

        if to_sell not in selections:
            return apology("Select stock to sell!", 403)

        to_sell_ammount = int(request.form.get("shares"))

        available_tosell = db.execute("SELECT company_shares FROM purchases WHERE buyer_id = ? AND company_symbol = ?",session["user_id"], to_sell)

        if available_tosell[0]["company_shares"] < to_sell_ammount:
            return apology("You don't own that many stocks!", 400)

        remaining_stocks = available_tosell[0]["company_shares"] - to_sell_ammount

        company_v = lookup(to_sell)
        company_value = company_v["price"]
        transaction_value = company_value * to_sell_ammount

        timestamp = datetime.datetime.now()

        if remaining_stocks == 0:
            db.execute("DELETE FROM purchases WHERE company_symbol = ? AND buyer_id = ?", to_sell, session["user_id"])
        else:
            db.execute("UPDATE purchases SET company_shares = ?, price = ?, timestamp = ? WHERE buyer_id = ? AND company_symbol = ?", remaining_stocks, company_value, timestamp, session["user_id"], to_sell)

        av_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        up_cash = av_cash[0]["cash"] + transaction_value

        db.execute("UPDATE users SET cash = ? WHERE id = ?", up_cash, session["user_id"])

        db.execute("INSERT INTO journal (symbol, shares, price, transacted, buyer_id, type) VALUES (?, ?, ?, ?, ?, ?)", to_sell, to_sell_ammount, company_value, timestamp, session["user_id"], "sold")

        return redirect("/")

    else:
        return render_template("sell.html", stock_selection=stock_selection)

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password"""
    if request.method == "POST":
        #Change password
        current_password = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])

        old_password = request.form.get("old_password")

        new_password = request.form.get("new_password")

        confirmation = request.form.get("confirm_new_password")

        if not check_password_hash(current_password[0]["hash"], old_password):
            return apology("Wrong password!", 403)

        elif new_password != confirmation:
            return apology("New password does not match confirmation!", 403)

        elif check_password_hash(current_password[0]["hash"], new_password):
            return apology("New password is the same as old password!", 403)

        else:
            db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new_password), session["user_id"])

        session.clear()

        return redirect("/login")
    else:
        return render_template("change_password.html")