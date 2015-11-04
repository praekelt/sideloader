# -*- coding: utf-8 -*-
# Specter client library

import hashlib
import base64
import hmac
import urllib
import json

from StringIO import StringIO

from zope.interface import implements

from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent
from twisted.internet import reactor, defer, protocol
from twisted.internet.ssl import ClientContextFactory
from twisted.web.http_headers import Headers

try:
    from twisted.web import client
    client._HTTP11ClientFactory.noisy = False
except:
    pass

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

class BodyReceiver(protocol.Protocol):
    """ Simple buffering consumer for body objects """
    def __init__(self, finished):
        self.finished = finished
        self.buffer = StringIO()

    def dataReceived(self, buffer):
        self.buffer.write(buffer)

    def connectionLost(self, reason):
        self.buffer.seek(0)
        self.finished.callback(self.buffer)

class StringProducer(object):
    """
    Body producer for t.w.c.Agent
    """
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

class SpecterClient(object):
    def __init__(self, host, auth, key, port=2400, async=True):
        self.host = host
        self.port = port
        self.auth = auth
        self.key = key
        self.async = async

    def createSignature(self, path, data=None):
        if data:
            method = 'POST'
        else:
            method = 'GET'
        sign = [self.auth, method, '/' + path]
        if data:
            sign.append(
                hashlib.sha1(data).hexdigest()
            )

        mysig = hmac.new(key=self.key, msg='\n'.join(sign),
            digestmod=hashlib.sha1).digest()

        return base64.b64encode(mysig)

    @defer.inlineCallbacks
    def httpsRequest(self, url, headers={}, method='GET', data=None):
        headers['Content-Type'] = ['application/json']
        if url.startswith('https'):
            agent = Agent(reactor, WebClientContextFactory())
        else:
            agent = Agent(reactor)

        if data:
            data = StringProducer(data)

        request = yield agent.request(
            method,
            url,
            Headers(headers),
            data
        )

        if request.length:
            d = defer.Deferred()
            request.deliverBody(BodyReceiver(d))
            body = yield d

            defer.returnValue(json.loads(body.read()))
        else:
            defer.returnValue(None)

    def signHeaders(self, path, data=None):
        sig = self.createSignature(path, data)

        return {
            'authorization': [self.auth],
            'sig': [sig]
        }

    def getRequest(self, path, *a):
        if a:
            path = path + '/' + '/'.join([str(i) for i in a])

        url = 'https://%s:%s/%s' % (self.host, self.port, path)

        return self.httpsRequest(
            url,
            headers=self.signHeaders(path)
        )

    def postRequest(self, path, data, *a):
        url = 'https://%s:%s/%s' % (self.host, self.port, path)
        return self.httpsRequest(
            url,
            headers=self.signHeaders(path, data),
            method='POST',
            data=data
        )

    def __getattr__(self, method):
        if method[:4] == 'get_':
            path = '/'.join(method[4:].split('_'))
            return lambda *a: self.getRequest(path, *a)

        elif method[:5] == 'post_':
            path = '/'.join(method[5:].split('_'))
            return lambda data, *a: self.postRequest(
                path, json.dumps(data), *a)
        else:
            raise AttributeError
