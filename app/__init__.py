from flask import Flask

# configure application
app = Flask(__name__)

from app import application
