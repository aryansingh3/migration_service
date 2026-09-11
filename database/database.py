import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from common.logger import Logger

TIMEOUT_MS = 2 * 60 * 1000


class DatabaseConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            Logger.info("Creating new DatabaseConnection instance")
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        Logger.info("Initializing DatabaseConnection")
        load_dotenv()

        prod_mongodb_uri = os.getenv("MONGODB_URI")
        staging_mongodb_uri = os.getenv("STAGING_MONGODB_URI")

        if not prod_mongodb_uri or not staging_mongodb_uri:
            raise ValueError("MONGODB_URI and STAGING_MONGODB_URI must be set in .env")

        self._prod_client = self._connect("Production", prod_mongodb_uri)
        self._staging_client = self._connect("Staging", staging_mongodb_uri)

    @staticmethod
    def _connect(label: str, uri: str) -> MongoClient:
        Logger.info(f"Attempting to connect to MongoDB {label} database")
        client = MongoClient(
            uri,
            connectTimeoutMS=TIMEOUT_MS,
            socketTimeoutMS=TIMEOUT_MS,
            serverSelectionTimeoutMS=TIMEOUT_MS,
        )
        client.server_info()
        Logger.info(f"Successfully connected to MongoDB {label} database")
        return client

    @property
    def prod_tickets(self) -> Database:
        """Live app DB (events, seatgeek_stats, ...)."""
        return self._prod_client["tickets"]

    @property
    def staging_tickets_backup(self) -> Database:
        """Historical archive DB on the staging cluster. That cluster's `tickets` DB is the staging app's own data."""
        return self._staging_client["tickets_backup"]


db = DatabaseConnection()
