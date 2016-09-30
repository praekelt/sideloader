from datetime import datetime
import os

import pytest
from twisted.trial import unittest
from twisted.internet import defer, reactor, task
from twisted.web import resource, server

from sideloader import tasks
from sideloader.tests import fake_db, repotools
from sideloader.tests.fake_data import (
    RELEASESTREAM_QA, RELEASESTREAM_PROD, PROJECT_SIDELOADER,
    RELEASEFLOW_QA, RELEASEFLOW_PROD, BUILD_1, WEBHOOK_QA_1, WEBHOOK_QA_2)
from sideloader.tests.utils import dictmerge


@pytest.fixture
def env_tz(monkeypatch):
    monkeypatch.setenv('TZ', 'test-5')


def id_sorted(rows):
    return sorted(rows, key=lambda r: r['id'])


class WebhookCatcher(object):
    """
    A webserver to catch webhook calls.
    """

    def __init__(self, testcase):
        self._testcase = testcase
        self.queue = defer.DeferredQueue()
        self._webserver = None
        self.addr = None
        self._url = None

    @defer.inlineCallbacks
    def start(self):
        root = resource.Resource()
        root.isLeaf = True
        root.render = self._render
        site_factory = server.Site(root)
        self._webserver = yield reactor.listenTCP(
            0, site_factory, interface='127.0.0.1')
        self._testcase.addCleanup(self._webserver.loseConnection)
        self._testcase.addCleanup(self._webserver.stopListening)
        self.addr = self._webserver.getHost()
        self._url = "http://%s:%s/" % (self.addr.host, self.addr.port)

    def url(self, path):
        return "/".join([self._url.rstrip("/"), path.lstrip("/")])

    def _render(self, request):
        self.queue.put(request)
        return server.NOT_DONE_YET

    def get_request(self):
        return self.queue.get()

    def reply(self, request, body="", code=200):
        request.setResponseCode(code)
        request.write(body)
        request.finish()


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

    def wait(self, seconds):
        return task.deferLater(reactor, seconds, lambda: None)

    def _wait_for_build(self, build_id):

        def _check_build_result(build, d):
            if build['state'] == 0:
                reactor.callLater(0.1, _check_build, d)
            else:
                # Wait an extra 100ms for things that happen after the build
                # status is set.
                reactor.callLater(0.1, d.callback, build)

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

    def assert_time_between(self, start, end, timestamp, name='timestamp'):
        self.assertTrue(
            start <= timestamp <= end,
            "Expected %s between %r and %r, got %r" % (
                name, start, end, timestamp))

    @defer.inlineCallbacks
    def setup_db(self, project_def, build_number=1, flow_defs=()):
        yield self.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.runInsert('sideloader_releasestream', RELEASESTREAM_PROD)
        yield self.runInsert('sideloader_project', project_def)
        for flow_def in flow_defs:
            yield self.runInsert('sideloader_releaseflow', dictmerge(
                flow_def, project_id=project_def['id']))
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

    @defer.inlineCallbacks
    def test_build_and_release(self):
        """
        We can successfully build a simple project and then release it.

        Note that this only creates the release object in the database. It
        doesn't actually run the release.
        """
        repo = self.mkrepo('sideloader')
        yield self.setup_db(
            dictmerge(PROJECT_SIDELOADER, github_url=repo.url),
            flow_defs=[RELEASEFLOW_PROD])
        yield self.plug.call_build({'build_id': 1})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 1)

        # FIXME: We dig directly into our fake db here, because we haven't
        #        implemented FakeDB.getReleases() yet.
        self.assertEqual(self.plug.db._release, {})
        yield self.plug.call_release(
            {'build_id': 1, 'flow_id': RELEASEFLOW_PROD['id']})
        [release] = yield self.plug.db._release.values()
        self.assertEqual(release['build_id'], 1)
        self.assertEqual(release['flow_id'], RELEASEFLOW_PROD['id'])
        self.assertEqual(release['scheduled'], None)
        self.assertEqual(release['waiting'], True)

    @pytest.mark.usefixtures('env_tz')
    @defer.inlineCallbacks
    def test_build_and_release_timezone(self):
        """
        When we build a release, we send the timestamp in UTC.

        The twisted database stuff assumes timezones are in UTC and sends them
        to postgres with an explicit zero offset.
        """
        repo = self.mkrepo('sideloader')
        yield self.setup_db(
            dictmerge(PROJECT_SIDELOADER, github_url=repo.url),
            flow_defs=[RELEASEFLOW_PROD])

        start = datetime.utcnow()

        yield self.plug.call_build({'build_id': 1})
        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 1)
        # FIXME: We dig directly into our fake db here, because we haven't
        #        implemented FakeDB.getReleases() yet.
        self.assertEqual(self.plug.db._release, {})
        yield self.plug.call_release(
            {'build_id': 1, 'flow_id': RELEASEFLOW_PROD['id']})
        [release] = yield self.plug.db._release.values()

        end = datetime.utcnow()

        self.assert_time_between(
            start, end, release['release_date'], 'release_date')

    @defer.inlineCallbacks
    def test_build_and_autorelease(self):
        """
        We can successfully build a simple project and have it automatically
        released.

        Note that this only creates the release object in the database. It
        doesn't actually run the release.
        """
        repo = self.mkrepo('sideloader')
        yield self.setup_db(
            dictmerge(PROJECT_SIDELOADER, github_url=repo.url),
            flow_defs=[RELEASEFLOW_QA])
        yield self.plug.call_build({'build_id': 1})

        # FIXME: We dig directly into our fake db here, because we haven't
        #        implemented FakeDB.getReleases() yet.
        self.assertEqual(self.plug.db._release, {})

        build = yield self._wait_for_build(1)
        self.assertEqual(build['state'], 1)

        [release] = yield self.plug.db._release.values()
        self.assertEqual(release['build_id'], 1)
        self.assertEqual(release['flow_id'], RELEASEFLOW_QA['id'])
        self.assertEqual(release['scheduled'], None)
        self.assertEqual(release['waiting'], True)

    @defer.inlineCallbacks
    def test_runrelease(self):
        """
        We can successfully run a release.

        This first creates a build and a release in the database, then runs the
        release.
        """
        repo = self.mkrepo('sideloader')
        yield self.setup_db(
            dictmerge(PROJECT_SIDELOADER, github_url=repo.url),
            flow_defs=[RELEASEFLOW_QA])
        yield self.plug.call_build({'build_id': 1})

        # FIXME: We dig directly into our fake db here, because we haven't
        #        implemented FakeDB.getReleases() yet.
        self.assertEqual(self.plug.db._release, {})
        yield self._wait_for_build(1)
        [release] = yield self.plug.db._release.values()
        self.assertEqual(release['build_id'], 1)
        self.assertEqual(release['waiting'], True)
        self.assertEqual(release['lock'], False)

        yield self.plug.call_runrelease({'release_id': release['id']})
        [release] = yield self.plug.db._release.values()
        self.assertEqual(release['build_id'], 1)
        self.assertEqual(release['waiting'], False)
        self.assertEqual(release['lock'], False)

        # Wait for webhook processing, even though we don't have any.
        yield self.wait(0.002)

    @defer.inlineCallbacks
    def test_runrelease_single_webhook(self):
        """
        After a release, we call a configured webhook.
        """
        wc = WebhookCatcher(self)
        yield wc.start()

        repo = self.mkrepo('sideloader')
        yield self.setup_db(
            dictmerge(PROJECT_SIDELOADER, github_url=repo.url),
            flow_defs=[RELEASEFLOW_QA])
        yield self.runInsert(
            'sideloader_webhook', dictmerge(WEBHOOK_QA_1, url=wc.url("h1")))

        yield self.plug.call_build({'build_id': 1})

        # FIXME: We dig directly into our fake db here, because we haven't
        #        implemented FakeDB.getReleases() yet.
        self.assertEqual(self.plug.db._release, {})
        yield self._wait_for_build(1)
        [release] = yield self.plug.db._release.values()
        yield self.plug.call_runrelease({'release_id': release['id']})
        [release] = yield self.plug.db._release.values()
        self.assertEqual(release['build_id'], 1)
        self.assertEqual(release['waiting'], False)
        self.assertEqual(release['lock'], False)

        hook_req = yield wc.get_request()
        assert hook_req.method == WEBHOOK_QA_1['method']
        assert hook_req.path == "/h1"
        [webhook] = yield self.plug.db.getWebhooks(RELEASEFLOW_QA['id'])
        assert webhook['last_response'] == ''
        wc.reply(hook_req, "Happy.")
        # Wait a bit for things to happen.
        yield self.wait(0.01)
        [webhook] = yield self.plug.db.getWebhooks(RELEASEFLOW_QA['id'])
        assert webhook['last_response'] == "Happy."

    @defer.inlineCallbacks
    def test_runrelease_two_webhooks(self):
        """
        After a release, we call all configured webhooks.
        """
        wc = WebhookCatcher(self)
        yield wc.start()

        repo = self.mkrepo('sideloader')
        yield self.setup_db(
            dictmerge(PROJECT_SIDELOADER, github_url=repo.url),
            flow_defs=[RELEASEFLOW_QA])
        yield self.runInsert(
            'sideloader_webhook', dictmerge(WEBHOOK_QA_1, url=wc.url("h1")))
        yield self.runInsert(
            'sideloader_webhook', dictmerge(WEBHOOK_QA_2, url=wc.url("h2")))

        yield self.plug.call_build({'build_id': 1})

        # FIXME: We dig directly into our fake db here, because we haven't
        #        implemented FakeDB.getReleases() yet.
        self.assertEqual(self.plug.db._release, {})
        yield self._wait_for_build(1)
        [release] = yield self.plug.db._release.values()
        yield self.plug.call_runrelease({'release_id': release['id']})
        [release] = yield self.plug.db._release.values()
        self.assertEqual(release['build_id'], 1)
        self.assertEqual(release['waiting'], False)
        self.assertEqual(release['lock'], False)

        r1 = yield wc.get_request()
        r2 = yield wc.get_request()
        [hook_req1, hook_req2] = sorted([r1, r2], key=lambda r: r.path)
        assert hook_req1.method == WEBHOOK_QA_1['method']
        assert hook_req1.path == "/h1"
        assert hook_req2.method == WEBHOOK_QA_2['method']
        assert hook_req2.path == "/h2"

        webhooks = yield self.plug.db.getWebhooks(RELEASEFLOW_QA['id'])
        [wh1, wh2] = id_sorted(webhooks)
        assert wh1['last_response'] == ''
        assert wh2['last_response'] == ''
        wc.reply(hook_req1, "Content.")
        wc.reply(hook_req2, "Joyous.")
        # Wait a bit for things to happen.
        yield self.wait(0.01)
        webhooks = yield self.plug.db.getWebhooks(RELEASEFLOW_QA['id'])
        [wh1, wh2] = id_sorted(webhooks)
        assert wh1['last_response'] == "Content."
        assert wh2['last_response'] == "Joyous."
