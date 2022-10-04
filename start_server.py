#!/usr/bin/env python
import uvicorn

if __name__ == '__main__':
    uvicorn.run("openbook.asgi:application", reload=True)
