import threading


class YThread(threading.Thread):
    def __init__(self, session, offset, process_apts):
        super().__init__()
        self.session = session
        self.offset = offset
        self.process_apts = process_apts

    def run(self):
        self.process_apts(
            self.offset
        )
