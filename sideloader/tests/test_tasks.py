import time

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
                'build_file': 'test'
            }
        },
        'projects': {
            1: {
                'name': 'Test project',
                'github_url': 'git@github.com:fakeorg/someproject.git',
                'branch': 'develop',
                'package_manager': 'deb',
                'deploy_type': 'virtualenv',
                'deploy_file': '.deploy.yaml',
                'package_name': 'test_package',
                'build_script': 'build_test.sh',
                'postinstall_script': 'post_test.sh',
                'created_by_user': 1,
                'release_stream': 1,
                'idhash': '6d8adfebec3011e59599b88d121fe884',
                'allowed_users': [1],
                'notifications': False,
                'slack_channel': '#mychan'
            }
        }
    }

    def getBuild(self, id):
        return self.data['builds'][id]

    def updateBuildLog(self, id, data):
        self.data['builds'][id]['log'] = data

    def getProject(self, id):
        return self.data['projects'][id]

class TestDB(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.plug = tasks.Plugin({'name': 'sideloader'}, self.client)

        self.plug.db = FakeDB()

    @defer.inlineCallbacks
    def test_build(self):
        yield self.plug.call_build({'build_id': 1})
        

