from twisted.trial import unittest

from twisted.internet import defer, reactor, error

from sideloader import task_db


class TestDB(unittest.TestCase):
    def setUp(self):
        self.db = task_db.SideloaderDB()
        self.addCleanup(self.db.p.close)

    @defer.inlineCallbacks
    def test_select(self):
        r = yield self.db.select('sideloader_project', 
            ['id', 'name', 'github_url', 'branch', 'deploy_file', 'idhash',
            'notifications', 'slack_channel', 'created_by_user_id',
            'release_stream_id', 'build_script', 'package_name',
            'postinstall_script', 'package_manager', 'deploy_type'])
