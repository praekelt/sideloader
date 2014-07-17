# -*- coding: utf-8 -*-
# Specter client library

import hashlib
import base64
import hmac
import httplib
import json


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

    def httpsRequest(self, path, headers={}, method='GET', data=None):
        headers['Content-Type'] = ['application/json']
        conn = httplib.HTTPSConnection(self.host, self.port)

        if data:
            conn.request(method, '/'+path, data, headers)
        else:
            conn.request(method, '/'+path, None, headers)
                
        response = conn.getresponse()

        if response.status == 200:
            return json.loads(response.read())
        else:
            return None

    def signHeaders(self, path, data=None):
        sig = self.createSignature(path, data)

        return {
            'authorization': self.auth,
            'sig': sig
        }

    def getRequest(self, path, *a):
        if a:
            path = path + '/' + '/'.join([str(i) for i in a])

        return self.httpsRequest(
            path,
            headers=self.signHeaders(path)
        )

    def postRequest(self, path, data, *a):
        return self.httpsRequest(
            path,
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

