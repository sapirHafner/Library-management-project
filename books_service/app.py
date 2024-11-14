from flask import Flask
from flask_restful import Api
from books import books
from ratings import ratings


app = Flask(__name__)
api = Api(app)

app.register_blueprint(books)  # Import the books function from books.py
app.register_blueprint(ratings)  # Import the books function from ratings.py



if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5001, debug = True)

