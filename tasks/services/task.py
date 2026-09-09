from sqlalchemy.ext.asyncio import AsyncSession


class TaskService:
    def __init__(
            self,
            session: AsyncSession
    ):
        self._session = session

