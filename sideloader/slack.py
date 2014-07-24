# -*- coding: utf-8 -*-
# Slack client library

import httplib
import urllib
import json


class SlackClient(object):
    def __init__(self, host, token, channel):
        self.host = host
        self.token = token
        self.channel = channel

    def message(self, text, fields=[]):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        conn = httplib.HTTPSConnection(self.host, 443)

        params = urllib.urlencode({
            'payload': json.dumps({
                'channel': self.channel,
                'username': 'sideloader',
                'icon_emoji': ':greenrocket:',
                'attachments':[{
                    'fallback': text,
                    'pretext': text,
                    'color': '#0000D0',
                    'fields': fields
                }]
            })
        })

        conn.request("POST", 
            "/services/hooks/incoming-webhook?token=%s" % self.token,
            params, headers)

        res = conn.getresponse()
        conn.close()

        return res
