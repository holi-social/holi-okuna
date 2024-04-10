import threading

class CountDownLatch(object):
    def __init__(self, count=1):
        self.count = count
        self.lock = threading.Condition()

    def count_down(self):
        with self.lock:
            self.count -= 1
            if self.count <= 0:
                self.lock.notify_all()

    def wait_for(self):
        with self.lock:
            while self.count > 0:
                self.lock.wait()
