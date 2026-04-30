from flask import Flask, render_template, request, redirect, session
from flask_mail import Mail, Message
import random
import os

app = Flask(__name__)
app.secret_key = "otpsecretkey"


app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "shubhashishdas22@gnu.ac.in"
app.config["MAIL_PASSWORD"] = "lscg cdjp qajv cdzh"

mail = Mail(app)


USER_EMAIL = "test@gmail.com"
USER_PASSWORD = "12345"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if password == "12345":
            otp = str(random.randint(100000, 999999))
            session["otp"] = otp
            session["email"] = email

            msg = Message("Your OTP",
                          sender=app.config["MAIL_USERNAME"],
                          recipients=[email])
            msg.body = f"Your OTP is {otp}"
            mail.send(msg)

            return redirect("/verify")

        return "Wrong Email or Password"

    return render_template("login.html")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":
        entered_otp = request.form.get("otp")
        stored_otp = session.get("otp")

        print("DEBUG OTP:", entered_otp, stored_otp)

        if entered_otp == stored_otp:
            session["logged_in"] = True

            
            redirect_url = f"http://13.204.232.136:5000?email={session.get('email')}"
            print("REDIRECTING TO:", redirect_url)

            return redirect(redirect_url)

        return "Wrong OTP ❌"

    return render_template("otp.html")



if __name__ == "__main__":
    app.run(debug=True)
