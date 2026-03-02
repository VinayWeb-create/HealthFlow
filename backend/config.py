import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "healthflow")
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Vinay:vinayavala@cluster0.krhrrdn.mongodb.net/?appName=Cluster0")
    DB_NAME = os.environ.get("DB_NAME", "healthflow")
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    CORS_ORIGINS = os.environ.get(
        "CORS_ORIGINS",
        "https://health-flow-ten.vercel.app,re:https://.*\.vercel\.app,http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080,null"
    ).split(",")

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
