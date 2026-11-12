from elasticsearch import Elasticsearch
from flask import current_app
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from redis import Redis

jwt = JWTManager()


def init_extensions(app, mongo_client=None, redis_client=None, es_client=None):
    app.extensions["mongo_client"] = mongo_client or MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=app.config["MONGO_TIMEOUT_MS"],
        connect=False,
    )
    app.extensions["mongo_db"] = app.extensions["mongo_client"][app.config["MONGO_DB"]]
    app.extensions["redis"] = redis_client or Redis.from_url(
        app.config["REDIS_URL"],
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    app.extensions["es"] = es_client or Elasticsearch(
        app.config["ELASTIC_URL"],
        request_timeout=app.config["ELASTIC_TIMEOUT"],
    )


def get_db():
    return current_app.extensions["mongo_db"]


def get_redis():
    return current_app.extensions["redis"]


def get_es():
    return current_app.extensions["es"]
