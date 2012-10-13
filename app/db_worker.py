from multiprocessing.queues import Empty
import os
import re
import time
import urlparse

from bs4 import BeautifulSoup

from app import db
from models import QueuedUrl
from models import Url

from workerbase import Worker


def urljoin(url, path):
    url_new = path
    if path:
        if not path.startswith('http'):
            url_new = urlparse.urljoin(url, path)
            url_new = re.sub('#.*$', '', url_new)  # remove fragment
            url_new = re.sub('[.]{2}\/', '', url_new)  # remove excessive ../
    return url_new

class DbWorker(Worker):
    def __init__(self, fetch_queue, fetch_results, seed_urls=None, fetch_queue_preload=1):
        # init multiproc data structures
        self.fetch_queue = fetch_queue
        self.fetch_results = fetch_results
        self.seed_urls = seed_urls
        self.host = self.seed_urls[0]
        self.fetch_queue_preload = fetch_queue_preload

        # call base, dispatches to .mainloop
        super(DbWorker, self).__init__()

    def init_db(self):
        self.logger.info('Preparing datastore')

        os.system('sudo /etc/init.d/postgresql restart')
        os.system('dropdb crawl')
        os.system('createdb crawl')

        self.logger.info('Creating models')
        db.create_all()

    def seed_queue(self, urls):
        for url in urls:
            qurl = QueuedUrl(
                url=url,
                level=0,
            )
            db.session.add(qurl)
        db.session.commit()

    def dequeue_next_qurl(self):
        qurl = QueuedUrl.query.filter(
            QueuedUrl.processing_status == 'new',
        ).first()
        if qurl:
            self.logger.debug('Dequeued: %s' % qurl)
            QueuedUrl.query.filter(QueuedUrl.id == qurl.id).update({
                'processing_status': 'fetchable'
            })
            db.session.expunge_all()
            db.session.commit()
            return qurl

    def store_new_url(self, msg):
        qurl = msg['qurl']
        url = msg['url']
        filepath = msg['filepath']

        self.logger.debug("Storing: %s" % url)
        url.content_length = os.path.getsize(filepath)
        if qurl.parent_url:
            url.parent = Url.query.filter(Url.url == qurl.parent_url).first()

        db.session.add(url)
        QueuedUrl.query.filter(QueuedUrl.id == qurl.id).delete()
        db.session.commit()

        content = open(filepath).read()
        os.unlink(filepath)
        self.spider(qurl, content)

    def spider(self, qurl, content):
        self.logger.info('Spidering: %s' % qurl)
        soup = BeautifulSoup(content)

        level = qurl.level + 1

        def enqueue(url, context):
            self.enqueue_new_qurl(qurl, {
                'parent_url': qurl.url,
                'url': urljoin(qurl.url, url),
                'context': context,
                'level': level,
            })

        for elem in soup.find_all('a'):
            url = elem.get('href')
            enqueue(url, 'anchor')

        for elem in soup.find_all('link'):
            url = elem.get('href')
            enqueue(url, 'link')

        for elem in soup.find_all('script'):
            url = elem.get('src')
            enqueue(url, 'script')

        for elem in soup.find_all('img'):
            url = elem.get('src')
            enqueue(url, 'img')

        for elem in soup.find_all('iframe'):
            url = elem.get('src')
            enqueue(url, 'iframe')

        for elem in soup.find_all('embed'):
            url = elem.get('src')
            enqueue(url, 'embed')

    def enqueue_new_qurl(self, parent, dct):
        url = dct.get('url')
        #self.logger.debug('Enqueuing: %s' % url)

        if not url:
            return
        if url == 'None':
            return
        # improve match to: by top level domain
        if not (url.startswith(self.host) or url.startswith(self.host.replace('www.', ''))):
            return
        if parent and url == parent.url:
            return
        if (QueuedUrl.query.filter(QueuedUrl.url == url).first()
            or Url.query.filter(Url.url == url).first()):
            return

        qurl = QueuedUrl(**dct)
        db.session.add(qurl)
        db.session.commit()
        self.logger.info('Enqueued: %s' % qurl)

    def mainloop(self):
        if self.seed_urls:
            self.init_db()
            self.seed_queue(self.seed_urls)

        while True:
            try:
                msg = self.fetch_results.get_nowait()
                self.store_new_url(msg)
            except Empty:
                pass

            if self.fetch_queue.qsize() < self.fetch_queue_preload:
                for _ in xrange(self.fetch_queue_preload):
                    qurl = self.dequeue_next_qurl()
                    self.fetch_queue.put(qurl)
            else:
                time.sleep(0.01)
