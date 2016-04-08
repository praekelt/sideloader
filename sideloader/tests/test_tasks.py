import sys
import os

from twisted.trial import unittest
from twisted.python import log
from twisted.internet import defer, reactor

from sideloader import tasks
from sideloader.tests import fake_db, repotools
from sideloader.tests.fake_data import (
    RELEASESTREAM_QA, PROJECT_SIDELOADER, BUILD_1)


# NOTE: This is necessary for useful failure output in pytest, but is a problem
#       when running these tests with trial.
log.startLogging(sys.stdout, setStdout=False)


class FakeClient(object):
    pass


class TestTasks(unittest.TestCase):

    def setUp(self):
        self.client = FakeClient()
        localdir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.plug = tasks.Plugin({
            'name': 'sideloader',
            'localdir': localdir,
        }, self.client, task_db=fake_db.FakeDB(reactor))

    def _wait_for_build(self, build_id):

        def _check_build_result(build, d):
            if build['state'] == 0:
                reactor.callLater(0.1, _check_build, d)
            else:
                d.callback(build)

        def _check_build(d):
            self.plug.db.getBuild(build_id).addCallback(_check_build_result, d)

        d = defer.Deferred()
        _check_build(d)
        return d

    def runInsert(self, tbl, data):
        return self.plug.db.runInsert(tbl, data)

    def patch_notifications(self):
        notifications = []

        def catch_notifications(message, project_id):
            notifications.append(message)
            return defer.succeed(None)

        self.plug.sendNotification = catch_notifications
        return notifications

    def mkrepo(self, name, add_scripts=True):
        repo = repotools.LocalRepo('sideloader', self.mktemp())
        if add_scripts:
            repo.mkdir("scripts")
            repo.add_file(
                "scripts/test_build.sh", '#!/bin/bash\n\necho "OK"\n',
                executable=True)
            repo.add_file("scripts/test_post.sh", "echo TEST")
            repo.commit("Add build scripts.")
        return repo

    def assert_notification(self, notification, end_text):
        failmsg = "Expected notification ending with %r, got %r." % (
            end_text, notification,)
        self.assertTrue(notification.endswith(end_text), failmsg)

    @defer.inlineCallbacks
    def test_build(self):
        """
        We can successfully build a simple project.
        """
        repo = self.mkrepo('sideloader')
        prj = PROJECT_SIDELOADER.copy()
        prj['github_url'] = repo.url
        yield self.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.runInsert('sideloader_project', prj)
        yield self.runInsert('sideloader_build', BUILD_1)
        yield self.plug.db.setBuildNumber('sideloader', 1, create=True)
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        print notifications
        self.assertEqual(build['state'], 1)
        self.assertEqual(build['build_file'], 'test-package_0.2_amd64.deb')
        [start_not, success_not] = notifications
        self.assert_notification(
            start_not, "projects/build/view/1|#1> started for branch develop")
        self.assert_notification(
            success_not, "projects/build/view/1|#1> successful")

    @defer.inlineCallbacks
    def test_build_bad_url(self):
        """
        If we have a bad URL, the build fails.
        """
        prj = PROJECT_SIDELOADER.copy()
        prj['github_url'] = 'This is not a valid URL.'
        yield self.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.runInsert('sideloader_project', prj)
        yield self.runInsert('sideloader_build', BUILD_1)
        yield self.plug.db.setBuildNumber('sideloader', 1, create=True)
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 2)
        self.assertEqual(build['build_file'], '')
        [fail_not] = notifications
        self.assert_notification(
            fail_not, '/projects/build/view/1|#1> failed')
