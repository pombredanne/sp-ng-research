#!/usr/bin/env python

from datetime import datetime
import json
import os
import random
import sys

from twisted.web import server
from twisted.web import static
from twisted.web import resource
from twisted.internet import reactor
from twisted.python import log

from jinja2 import Environment
from jinja2 import FileSystemLoader


def get_package_path():
    return os.path.dirname(os.path.abspath(__file__))

def render_to_response(request, template, context):
    path = os.path.join(get_package_path(), 'templates')
    loader = FileSystemLoader(path)
    env = Environment(loader=loader)
    temp = env.get_template(template)
    html = temp.render(context)

    charset = 'utf-8'
    request.setHeader('content-type', 'text/html; charset=%s' % charset)
    return html.encode(charset)


_files = {
    'a': 0,
    'b': 0,
    'c': 0,
}

class Root(resource.Resource):
    hits = 0

    def __init__(self):
        resource.Resource.__init__(self)

        self.putChild('', Home(self))
        self.putChild('_json', JsonView(self))

        fp = os.path.join(get_package_path(), 'static')
        self.putChild('static', static.File(fp))

    def getChild(self, name, request):
        self.hits += 1
        return resource.ErrorPage(404, '404', 'Not found')

class Home(resource.Resource):
    pageviews = 0

    def __init__(self, root):
        self.root = root

    def render_GET(self, request):
        self.pageviews += 1
        self.root.hits += 1
        msg = "Page views: %s, Hits: %s\n" % (self.pageviews, self.root.hits)

        return render_to_response(request, 'index.html', dict(
            title='Webber',
            msg=msg,
            files=_files,
        ))

class JsonView(resource.Resource):
    def __init__(self, root):
        self.root = root

    def render_GET(self, request):
        self.root.hits += 1

        payload = {}

        for f in _files:
            progress = _files[f]
            if progress < 100:
                delta = random.randint(0, 1)
                if delta:
                    _files[f] += delta
                    payload[f] = _files[f]

        dct = {
            'files': payload,
        }
        return json.dumps(dct)


if __name__ == '__main__':
    reactor.listenTCP(8000, server.Site(Root()))
    log.startLogging(sys.stdout)
    reactor.run()
