#!/usr/bin/env python3
import os
import uvicorn

from api.app import app


if __name__ == "__main__":
    host = os.getenv("BSC_DLP_HOST", "127.0.0.1")
    port = int(os.getenv("BSC_DLP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")
