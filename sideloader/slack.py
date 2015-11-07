# -*- coding: utf-8 -*-
# Slack client library

import urllib
import json

from rhumba.plugin import HTTPRequest


class SlackClient(object):
    def __init__(self, host, token, channel):
        self.host = host
        self.token = token
        self.channel = channel

    def message(self, text, fields=[]):
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

        url = 'https://%s/services/hooks/incoming-webhook?token=%s' % (
            self.host, self.token)

        return HTTPRequest().getBody(url, method='POST', data=params, headers={
                'Content-Type': ['application/x-www-form-urlencoded']
            })
