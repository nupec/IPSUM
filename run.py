import logging
from app.main import app

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    logger = logging.getLogger("run")

    logger.info("Starting Uvicorn with the IPSUM app.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
