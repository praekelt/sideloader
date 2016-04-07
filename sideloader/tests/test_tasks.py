import time
import os

from twisted.trial import unittest

from twisted.internet import defer, reactor, error

from sideloader import task_db, tasks


class FakeClient(object):
    pass

class FakeDB(object):
    data = {
        'builds': {
            1: {
                'id': 1, 
                'build_time': None,
                'task_id': 1, 
                'log': '',
                'project_id':1,
                'state':0, 
                'build_file': ''
            }
        },
        'projects': {
            1: {
                'id': 1,
                'name': 'Test project',
                'github_url': 'https://github.com/praekelt/sideloader.git',
                'branch': 'develop',
                'package_manager': 'deb',
                'deploy_type': 'virtualenv',
                'deploy_file': '.deploy.yaml',
                'package_name': 'test_package',
                'build_script': 'scripts/test_build.sh',
                'postinstall_script': 'scripts/test_post.sh',
                'created_by_user': 1,
                'release_stream': 1,
                'idhash': '6d8adfebec3011e59599b88d121fe884',
                'allowed_users': [1],
                'notifications': False,
                'slack_channel': '#mychan'
            }
        },
        'buildnums': {
            'sideloader': 1
        }
    }

    def getBuildNumber(self, repo):
        return self.data['buildnums'][repo]

    def getAutoFlows(self, id):
        return []

    def setBuildNumber(self, repo, num):
        assert type(num) is int
        self.data['buildnums'][repo] = num

    def setBuildFile(self, id, file):
        self.data['builds'][id]['build_file'] = file

    def getBuild(self, id):
        return self.data['builds'][id]

    def setBuildState(self, id, state):
        assert type(state) is int
        self.data['builds'][id]['state'] = state

    def getProjectNotificationSettings(self, id):
        prj = self.getProject(id)
        return [prj['name'], prj['notifications'], prj['slack_channel']]

    def updateBuildLog(self, id, data):
        self.data['builds'][id]['log'] = data

    def getProject(self, id):
        return self.data['projects'][id]

class TestDB(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        localdir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.plug = tasks.Plugin({
                        'name': 'sideloader', 
                        'localdir': localdir,
                    }, self.client)
        self.plug.db.p.close()
        self.plug.db = FakeDB()

    def _wait_for_build(self):
        d = defer.Deferred()
        def check_build(d):
            build = self.plug.db.getBuild(1)
            if build['state'] == 0:
                reactor.callLater(1, check_build, d)
            else:
                d.callback(build)
        reactor.callLater(1, check_build, d)
        return d

    def _no_notification(self, *a):
        return None

    @defer.inlineCallbacks
    def test_build(self):
        self.plug.sendNotification = self._no_notification
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build()
        self.assertEquals(build['state'], 1)
        self.assertEquals(build['build_file'], 'test-package_0.2_amd64.deb')
