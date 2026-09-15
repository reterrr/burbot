import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

load_dotenv()

database_url = os.environ["DCKR_DATABASE_URL"]

engine = create_async_engine(database_url)


def get_session() -> AsyncSession:
    return AsyncSession(bind=engine)
