#!/usr/bin/env python
import argparse
from logging import getLogger

import uvicorn
import openbook.asgi
from openbook.logging import initialize_logging

logger = getLogger()


def main():
    parser = argparse.ArgumentParser(description="Start okuna server")
    parser.add_argument("--host", type=str, nargs="?", default="127.0.0.1")
    parser.add_argument("--port", type=int, nargs="?", default=8000)

    args = parser.parse_args()

    log_config = initialize_logging()
    logger.info("Logging initialized, starting application")

    uvicorn.run(openbook.asgi.application, host=args.host, port=args.port, lifespan="off", log_config=log_config)


if __name__ == "__main__":
    main()
