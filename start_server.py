#!/usr/bin/env python
from logging import getLogger

import uvicorn
import openbook.asgi
from openbook.logging import initialize_logging

logger = getLogger()

if __name__ == "__main__":
    log_config = initialize_logging()
    logger.info("Logging initialized, starting application")

    uvicorn.run(openbook.asgi.application, host="0.0.0.0", port=80, log_config=log_config)  # hardcoded for docker atm
