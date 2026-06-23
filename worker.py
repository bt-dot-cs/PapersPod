"""
Worker process — runs Procrastinate job queue.

Usage:
    cd /Users/Benjamin/Documents/Entrepreneurship/Agentic_Software/PapersPod
    set -a && source .env && set +a
    PYTHONPATH=. .venv/bin/python worker.py
"""
import asyncio
import logging

from dotenv import load_dotenv

# Load env before importing core.queue so DATABASE_URL is available
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    from core.queue import app
    logger.info("Worker starting")
    async with app.open_async():
        logger.info("Worker ready — waiting for jobs")
        await app.run_worker_async()


if __name__ == "__main__":
    asyncio.run(main())
