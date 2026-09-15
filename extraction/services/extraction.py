from sqlalchemy.ext.asyncio import AsyncSession


class ExtractionService:
    def __init__(
            self,
            session: AsyncSession,
            browser_client: SourceBrowserClient,
    ):
        self._browser_client = browser_client
        self._session = session
