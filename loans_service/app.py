from flask import Flask
from flask_restful import Api
from loans import loans


app = Flask(__name__)
api = Api(app)

app.register_blueprint(loans) 


if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5002, debug = True)

