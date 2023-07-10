import os
import re
import time


from django.db import connection

import structlog
from django.utils.decorators import async_only_middleware

log = structlog.getLogger()

SLOW_LOG_THRESHOLD = int(os.environ.get("SLOW_LOG_THRESHOLD", "500"))  # milliseconds


def to_bytes(string):
    """Converts a string with a human-readable byte size to a number of
    bytes.  Takes strings like '7536 kB', in the format of proc."""
    num, units = string.split()
    num = int(num)
    powers = {"kb": 10, "mb": 20, "gb": 30}
    if units and units.lower() in powers:
        num <<= powers[units.lower()]
    return num


class LoadAverage(object):
    """Fetch the current load average.  Uses /proc/loadavg in linux"""

    disabled = False

    def __init__(self):
        self.disabled = not os.path.exists("/proc/loadavg")

    def current(self):
        """Returns 3 floats, (1 min, 5 min, 15 min) load averages like
        the datetime command."""
        if not self.disabled:
            return self.proc_load()
        else:
            return [0.0, 0.0, 0.0]

    def proc_load(self):
        try:
            with open("/proc/loadavg") as f:
                content = f.read()
            return [float(x) for x in content.split()[:3]]
        except:
            return [0.0, 0.0, 0.0]


class MemoryStatus(object):
    """Fetch the memory for a given PID.  Note that this is designed mostly to
    read the current processes memory size;"""

    matcher = re.compile("VmSize:\s*(\d+\s*\w+)")
    disabled = False

    def __init__(self, pid):
        self.pid = int(pid)
        self.procpath = "/proc/%s/status" % pid
        if not os.path.exists(self.procpath):
            self.disabled = True

    def usage(self):
        if not self.disabled:
            return self.proc_usage()
        else:
            return 0

    def proc_usage(self):
        try:
            with open(self.procpath) as f:
                content = f.read()
            size = self.matcher.search(content).groups()[0]
            return to_bytes(size)
        except:
            return 0


@async_only_middleware
def slow_log_middleware(get_response):
    loadavg = LoadAverage()
    pid = os.getpid()
    memory = MemoryStatus(pid)

    def _get_stats(time_delta):
        return {
            "time": time_delta,  # millis
            "memory": memory.usage(),
            "load": loadavg.current()[0],
        }

    def _current_millis():
        return round(time.time() * 1000)

    async def middleware(request):
        start_time = _current_millis()
        try:
            initial_http_body = request.body
        except Exception:
            initial_http_body = "Could not parse request body"

        response = await get_response(request)  # handle request

        time_delta = _current_millis() - start_time

        if time_delta > SLOW_LOG_THRESHOLD:
            path = request.get_host() + request.get_full_path()
            status_code = response.status_code if response else "500"
            stats = _get_stats(time_delta)

            if hasattr(connection, "query_count"):
                query_count = connection.query_count
            else:
                query_count = len(connection.queries)

            log.warn(
                f"Slow Request: Took {time_delta}ms to process {path}",
                status_code=status_code,
                request_method=request.META["REQUEST_METHOD"],
                path=path,
                stats=stats,
                queries=query_count,
                request_body=initial_http_body,
            )
        return response

    return middleware
