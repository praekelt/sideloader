# -*- coding: utf-8 -*-
# Specter client library

import hashlib
import base64
import hmac
import json

from rhumba.client import HTTPRequest

class SpecterClient(object):
    def __init__(self, host, auth, key, port=2400):
        self.host = host
        self.port = port
        self.auth = auth
        self.key = key

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

    def signHeaders(self, path, data=None):
        sig = self.createSignature(path, data)

        return {
            'authorization': self.auth,
            'sig': sig
        }

    def getRequest(self, path, *a):
        if a:
            path = path + '/' + '/'.join([str(i) for i in a])

        return HTTPRequest().getJson(
            'https://%s:%s/' % (self.host, self.port),
            headers=self.signHeaders(path, data)
        )

    def postRequest(self, path, data, *a):
        return HTTPRequest().getJson(
            'https://%s:%s/' % (self.host, self.port), 
            method='POST', data=data, headers=self.signHeaders(path, data)
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

