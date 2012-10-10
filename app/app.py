from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy


app = Flask(__name__)

#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.sqlite'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/crawl'
db = SQLAlchemy(app)
