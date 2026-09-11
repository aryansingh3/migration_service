import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from common.logger import Logger
from config.settings import BACKUP_DB, LIVE_DB, MONGO_TIMEOUT_MS


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
            connectTimeoutMS=MONGO_TIMEOUT_MS,
            socketTimeoutMS=MONGO_TIMEOUT_MS,
            serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
        )
        client.server_info()
        Logger.info(f"Successfully connected to MongoDB {label} database")
        return client

    @property
    def live(self) -> Database:
        """Production app DB (events, seatgeek_stats, ...)."""
        return self._prod_client[LIVE_DB]

    @property
    def backup(self) -> Database:
        """Historical archive DB on the staging cluster."""
        return self._staging_client[BACKUP_DB]

    def assert_different_clusters(self) -> None:
        """If both URIs reach the same cluster, "verified in backup" would mean the only copy - refuse."""
        live = self._prod_client.admin.command("hello")
        backup = self._staging_client.admin.command("hello")
        same_set = live.get("setName") and live.get("setName") == backup.get("setName")
        shared_host = set(live.get("hosts", [])) & set(backup.get("hosts", []))
        if same_set or shared_host:
            raise RuntimeError("MONGODB_URI and STAGING_MONGODB_URI point at the same cluster - refusing")


db = DatabaseConnection()
