import os

from twisted.trial import unittest
from twisted.internet import defer, reactor

from sideloader import tasks
from sideloader.tests import fake_db, repotools
from sideloader.tests.fake_data import (
    RELEASESTREAM_QA, PROJECT_SIDELOADER, RELEASEFLOW_QA, BUILD_1)
from sideloader.tests.utils import dictmerge


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

    def assert_notifications(self, notifications, end_texts):
        self.assertEqual(
            len(notifications), len(end_texts),
            "Expected %s notifications, got %r" % (
                len(end_texts), notifications))
        for notification, end_text in zip(notifications, end_texts):
            self.assert_notification(notification, end_text)

    @defer.inlineCallbacks
    def setup_db(self, project_def, build_number=1):
        yield self.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.runInsert('sideloader_project', project_def)
        yield self.runInsert('sideloader_releaseflow', dictmerge(
            RELEASEFLOW_QA, project_id=project_def['id']))
        yield self.runInsert('sideloader_build', BUILD_1)
        if build_number is not None:
            yield self.plug.db.setBuildNumber(
                'sideloader', build_number, create=True)

    @defer.inlineCallbacks
    def test_build(self):
        """
        We can successfully build a simple project.
        """
        repo = self.mkrepo('sideloader')
        yield self.setup_db(dictmerge(PROJECT_SIDELOADER, github_url=repo.url))
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 1)
        self.assertEqual(build['build_file'], 'test-package_0.2_amd64.deb')
        self.assert_notifications(notifications, [
            "projects/build/view/1|#1> started for branch develop",
            "projects/build/view/1|#1> successful",
        ])

    @defer.inlineCallbacks
    def test_build_bad_url(self):
        """
        If we have a bad URL, the build fails.
        """
        yield self.setup_db(dictmerge(
            PROJECT_SIDELOADER, github_url='This is not a valid URL.'))
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 2)
        self.assertEqual(build['build_file'], '')
        self.assert_notifications(notifications, [
            "projects/build/view/1|#1> failed",
        ])

    @defer.inlineCallbacks
    def test_build_missing_branch(self):
        """
        If the branch we want to build doesn't exist, the build fails.
        """
        repo = self.mkrepo('sideloader', add_scripts=False)
        yield self.setup_db(dictmerge(
            PROJECT_SIDELOADER, github_url=repo.url, branch='stormdamage'))
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 2)
        self.assertEqual(build['build_file'], '')
        self.assert_notifications(notifications, [
            "projects/build/view/1|#1> started for branch stormdamage",
            "projects/build/view/1|#1> failed",
        ])

    @defer.inlineCallbacks
    def test_build_missing_scripts(self):
        """
        If the build and postinst scripts are missing, the build fails.
        """
        repo = self.mkrepo('sideloader', add_scripts=False)
        yield self.setup_db(dictmerge(PROJECT_SIDELOADER, github_url=repo.url))
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 2)
        self.assertEqual(build['build_file'], '')
        self.assert_notifications(notifications, [
            "projects/build/view/1|#1> started for branch develop",
            "projects/build/view/1|#1> failed",
        ])

    @defer.inlineCallbacks
    def test_build_missing_scripts_branch(self):
        """
        If the build and postinst scripts are not in the branch we want to
        build, the build fails.
        """
        repo = self.mkrepo('sideloader', add_scripts=False)
        yield self.setup_db(dictmerge(
            PROJECT_SIDELOADER, github_url=repo.url, branch='master'))
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 2)
        self.assertEqual(build['build_file'], '')
        self.assert_notifications(notifications, [
            "projects/build/view/1|#1> started for branch master",
            "projects/build/view/1|#1> failed",
        ])

    @defer.inlineCallbacks
    def test_build_bad_script(self):
        """
        If the build script fails, the build fails.
        """
        repo = self.mkrepo('sideloader')
        repo.add_file("scripts/test_build.sh", "exit 1", executable=True)
        repo.commit("Break build.")
        yield self.setup_db(dictmerge(PROJECT_SIDELOADER, github_url=repo.url))
        notifications = self.patch_notifications()
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 2)
        self.assertEqual(build['build_file'], '')
        self.assert_notifications(notifications, [
            "projects/build/view/1|#1> started for branch develop",
            "projects/build/view/1|#1> failed",
        ])
