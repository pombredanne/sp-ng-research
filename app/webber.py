#!/usr/bin/env python

from multiprocessing import Queue
from multiprocessing import Process
import os
import signal
import time
import sys

from db_worker import DbWorker
from fetch_worker import FetchWorker
from web_worker import WebWorker


class WebberDaemon(object):
    def __init__(self, seed_url=None, num_fetchers=None):
        self.fetch_results = Queue()
        self.fetch_queue = Queue()

        self.seed_url = seed_url
        self.num_fetchers = num_fetchers or 1

        self.child_procs = []

    def spawn_fetchers(self, count):
        for num in xrange(count):
            p = Process(target=FetchWorker, args=[
                self.fetch_queue,
                self.fetch_results,
            ])
            self.child_procs.append(p)
            p.start()

    def spawn_db_workers(self, count):
        for num in xrange(count):
            p = Process(target=DbWorker, args=[
                self.fetch_queue,
                self.fetch_results,
                self.seed_url,
            ])
            self.child_procs.append(p)
            p.start()

    def spawn_web_workers(self, count):
        for num in xrange(count):
            p = Process(target=WebWorker, args=[
            ])
            self.child_procs.append(p)
            p.start()

    def mainloop(self):
        #self.spawn_db_workers(1)
        #self.spawn_fetchers(self.num_fetchers)
        self.spawn_web_workers(1)

        try:
            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            for p in self.child_procs:
                try:
                    os.kill(p.pid, signal.SIGTERM)
                except OSError:
                    import traceback
                    traceback.print_exc()


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("", "--fetchers", action="store", type="int",
                      help="Run with [x] workers")
    #parser.add_option("", "--keep", action="store_true",
    #                  help="Store the download in a file")
    (options, args) = parser.parse_args()

    if not args:
        print("No urls given")
        sys.exit(os.EX_USAGE)

    wd = WebberDaemon(
        seed_url=args[0],
        num_fetchers=options.fetchers,
    )
    wd.mainloop()
