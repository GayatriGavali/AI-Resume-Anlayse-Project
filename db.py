import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Quick override for local testing, e.g. DATABASE_URL=sqlite:///local.db
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    for var in ("TIDB_HOST", "TIDB_USER", "TIDB_PASSWORD", "TIDB_DATABASE"):
        if not os.getenv(var):
            raise ValueError(f"{var} is not set.")

    # URL.create safely handles special characters (@, #, %) in the password
    url = URL.create(
        "mysql+pymysql",
        username=os.getenv("TIDB_USER"),
        password=os.getenv("TIDB_PASSWORD"),
        host=os.getenv("TIDB_HOST"),
        port=int(os.getenv("TIDB_PORT", "4000")),
        database=os.getenv("TIDB_DATABASE"),
    )

    connect_args = {"connect_timeout": 10}

    # TiDB Cloud only accepts TLS connections.
    # Newer pymysql (1.1+) expects ONE "ssl" dict, not separate ssl_ca / ssl_verify_cert kwargs.
    if os.getenv("TIDB_SSL", "true").lower() == "true":
        import certifi

        connect_args["ssl"] = {"ca": certifi.where()}

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()