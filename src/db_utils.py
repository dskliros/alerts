# src/db_utils.py
import os
from decouple import config
from contextlib import contextmanager
from sshtunnel import SSHTunnelForwarder
from sqlalchemy import create_engine, text
import pandas as pd

# Load .env
SSH_HOST = config('SSH_HOST', default=None)
SSH_PORT = config('SSH_PORT', default=22, cast=int)
SSH_USER = config('SSH_USER', default='prominence')
SSH_KEY_PATH = os.path.expanduser(config('SSH_KEY_PATH', default=''))

DB_HOST = config('DB_HOST')
DB_PORT = config('DB_PORT', cast=int)
DB_NAME = config('DB_NAME')
DB_USER = config('DB_USER')
DB_PASS = config('DB_PASS')

USE_SSH_TUNNEL = config('USE_SSH_TUNNEL', default=False, cast=bool)


def query_to_df(query: str, display_all: bool=True, local: bool=False) -> pd.DataFrame:
    """Execute query and return DataFrame"""
    if display_all:
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
    else:
        pd.reset_option('display.max_rows')
        pd.reset_option('display.max_columns')
        pd.reset_option('display.width')
        pd.reset_option('display.max_colwidth')
    if local:
        import duckdb
        df = duckdb.query(query).to_df()
        return df
    if USE_SSH_TUNNEL and SSH_HOST and SSH_KEY_PATH:
        if not os.path.exists(SSH_KEY_PATH):
            raise FileNotFoundError(f'SSH key not found: {SSH_KEY_PATH}')
        with SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_private_key=SSH_KEY_PATH,
                remote_bind_address=(DB_HOST, DB_PORT)
            ) as tunnel:
            connection_string = (
                    f"postgresql://{DB_USER}:{DB_PASS}@"
                    f"localhost:{tunnel.local_bind_port}/{DB_NAME}"
            )
            engine = create_engine(connection_string)
            return pd.read_sql(query, engine)
    else:
        connection_string = (
                f"postgresql://{DB_USER}:{DB_PASS}@"
                f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        engine = create_engine(connection_string)
        return pd.read_sql(query, engine)

@contextmanager
def get_db_connection():
    """Context manager for database connection with optional SSH tunnel"""
    if USE_SSH_TUNNEL and SSH_HOST:
        if not os.path.exists(SSH_KEY_PATH):
            raise FileNotFoundError(f"SSH key not found: {SSH_KEY_PATH}")
        with SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_private_key=SSH_KEY_PATH,
                remote_bind_address=(DB_HOST, DB_PORT)
        ) as tunnel:
            connection_string = (
                    f"postgresql://{DB_USER}:{DB_PASS}@"
                    f"localhost:{tunnel.local_bind_port}/{DB_NAME}"
            )
            engine = create_engine(connection_string)
            conn = engine.connect()
            try:
                yield conn
            finally:
                conn.close()
    else:
        connection_string = (
                f"postgresql://{DB_USER}:{DB_PASS}@"
                f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        engine = create_engine(connection_string)
        conn = engine.connect()
        try:
            yield conn
        finally:
            conn.close()


def check_db_connection() -> bool:
    """
    Check if the database connection can be established.
    Returns True if successful, False otherwise.
    """
    try:
        if USE_SSH_TUNNEL and SSH_HOST and SSH_KEY_PATH:
            if not os.path.exists(SSH_KEY_PATH):
                raise FileNotFoundError(f"SSH key not found: {SSH_KEY_PATH}")
            with SSHTunnelForwarder(
                    (SSH_HOST, SSH_PORT),
                    ssh_username=SSH_USER,
                    ssh_private_key=SSH_KEY_PATH,
                    remote_bind_address=(DB_HOST, DB_PORT)
            ) as tunnel:
                connection_string = (
                        f"postgresql://{DB_USER}:{DB_PASS}@"
                        f"localhost:{tunnel.local_bind_port}/{DB_NAME}"
                )
                engine = create_engine(connection_string)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
        else:
            connection_string = (
                    f"postgresql://{DB_USER}:{DB_PASS}@"
                    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
            )
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

