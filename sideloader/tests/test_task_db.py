"""
Tests for sideloader.task_db.
"""

from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from twisted.trial import unittest

from sideloader import task_db
from sideloader.tests import fake_db
from sideloader.tests.fake_data import (
    RELEASESTREAM_QA, RELEASESTREAM_PROD, PROJECT_SIDELOADER, BUILD_1,
    RELEASEFLOW_QA, RELEASEFLOW_PROD, RELEASE_1, WEBHOOK_QA_1, WEBHOOK_QA_2)
from sideloader.tests.utils import dictmerge, now_utc


def maybe_fail(f, *args, **kw):
    try:
        return True, f(*args, **kw)
    except NotImplementedError:
        raise
    except:
        return False, Failure()


def id_sorted(rows):
    return sorted(rows, key=lambda r: r['id'])


class BothDBsProxy(object):
    """
    A database object wrapper that makes proxies any call to both a real
    database and a fake database. It asserts that both return the same result,
    or that both raise an exception.
    """

    def __init__(self, real_db, fake_db):
        self._real_db = real_db
        self._fake_db = fake_db

    def compare_for(self, name, rr, fr):
        # Some methods need order-agnostic result comparisons.
        if name in ['getWebhooks']:
            return id_sorted(rr) == id_sorted(fr)
        return rr == fr

    def __getattr__(self, name):
        realattr = getattr(self._real_db, name)
        fakeattr = getattr(self._fake_db, name)

        def result(rs, rr, fs, fr):
            if not rs:
                assert not fs, (
                    "Real operation failed, fake succeeded: %r" % (rr,))
                raise rr.value
            assert fs, (
                "Real operation succeeded, fake failed: %r" % (fr,))

            assert self.compare_for(name, rr, fr), (
                "Real operation returned %r, fake returned %r" % (rr, fr))
            return rr

        @defer.inlineCallbacks
        def result_async(df, dr):
            [(rs, rr), (fs, fr)] = yield defer.DeferredList([dr, df])
            defer.returnValue(result(rs, rr, fs, fr))

        def callboth(self, *args, **kw):
            fs, fr = maybe_fail(fakeattr, self, *args, **kw)
            rs, rr = maybe_fail(realattr, self, *args, **kw)
            if isinstance(rr, defer.Deferred):
                return result_async(fr, rr)
            return result(rs, rr, fs, fr)

        return callboth


class TestDB(unittest.TestCase):
    """
    Tests for both task_db and fake_db.
    """

    def setUp(self):
        self.real_db = task_db.SideloaderDB()
        self.addCleanup(self.real_db.p.close)
        self.addCleanup(self.clear_db)
        self.fake_db = fake_db.FakeDB(reactor)
        self.db = BothDBsProxy(self.real_db, self.fake_db)
        return self.clear_db()

    @defer.inlineCallbacks
    def clear_db(self):
        for tbl in ['sideloader_webhook',
                    'sideloader_release',
                    'sideloader_build',
                    'sideloader_buildnumbers',
                    'sideloader_releaseflow',
                    'sideloader_project',
                    'sideloader_releasestream']:
            yield self.real_db.p.runOperation('DELETE FROM %s' % (tbl,))
            yield self.real_db.p.runOperation(
                'ALTER SEQUENCE %s_id_seq RESTART' % (tbl,))

    @defer.inlineCallbacks
    def test_real_select(self):
        yield self.real_db.select('sideloader_project', [
            'id', 'name', 'github_url', 'branch', 'deploy_file', 'idhash',
            'notifications', 'slack_channel', 'created_by_user_id',
            'release_stream_id', 'build_script', 'package_name',
            'postinstall_script', 'package_manager', 'deploy_type'])

    @defer.inlineCallbacks
    def test_getProject(self):
        """
        We can get information about a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        proj = yield self.db.getProject(1)
        assert proj == PROJECT_SIDELOADER

    @defer.inlineCallbacks
    def test_getProject_missing(self):
        """
        We can't get information about a project that doesn't exist.
        """
        yield self.assertFailure(self.db.getProject(42), Exception)

    @defer.inlineCallbacks
    def test_updateBuildLog(self):
        """
        We can update a build's log.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.updateBuildLog(1, "Stardate 19564.3: Building a thing.")
        build = yield self.db.getBuild(1)
        assert build['log'] == "Stardate 19564.3: Building a thing."

    @defer.inlineCallbacks
    def test_updateBuildLog_missing(self):
        """
        Updates to missing builds go to /dev/null.
        """
        yield self.db.updateBuildLog(42, "Stardate 19564.3: Building a thing.")

    @defer.inlineCallbacks
    def test_getProjectNotificationSettings(self):
        """
        We can get notification settings for a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        pns = yield self.db.getProjectNotificationSettings(1)
        assert pns == (
            PROJECT_SIDELOADER['name'],
            PROJECT_SIDELOADER['notifications'],
            PROJECT_SIDELOADER['slack_channel'],
        )

    @defer.inlineCallbacks
    def test_getProjectNotificationSettings_missing(self):
        """
        We can't get notification settings for a project  that doesn't exist.
        """
        yield self.assertFailure(
            self.db.getProjectNotificationSettings(1), Exception)

    @defer.inlineCallbacks
    def test_getBuild(self):
        """
        We can get information about a build.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        build = yield self.db.getBuild(1)
        assert build == BUILD_1

    @defer.inlineCallbacks
    def test_getBuild_missing(self):
        """
        We can't get information about a build that doesn't exist.
        """
        yield self.assertFailure(self.db.getBuild(42), Exception)

    @defer.inlineCallbacks
    def test_getBuildNumber_missing(self):
        """
        If we ask for a missing build number, we get zero.
        """
        r = yield self.db.getBuildNumber('myproj')
        assert r == 0

    @defer.inlineCallbacks
    def test_setBuildNumber_create(self):
        """
        If we set a new build number and then get it, we get the one we set.
        """
        yield self.db.setBuildNumber('myproj', 7, create=True)
        r = yield self.db.getBuildNumber('myproj')
        assert r == 7

    @defer.inlineCallbacks
    def test_setBuildNumber_create_exists(self):
        """
        We can't set a new build number if the project already has one.
        """
        yield self.db.setBuildNumber('myproj', 7, create=True)
        d = self.db.setBuildNumber('myproj', 12, create=True)
        yield self.assertFailure(d, Exception)
        r = yield self.db.getBuildNumber('myproj')
        assert r == 7

    @defer.inlineCallbacks
    def test_setBuildNumber_getBuildNumber(self):
        """
        If we set a build number and then get it, we get the one we set.
        """
        yield self.db.setBuildNumber('myproj', 7, create=True)
        yield self.db.setBuildNumber('myproj', 12)
        r = yield self.db.getBuildNumber('myproj')
        assert r == 12

    @defer.inlineCallbacks
    def test_setBuildState(self):
        """
        We can update a build's state.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.setBuildState(1, 2)
        build = yield self.db.getBuild(1)
        assert build['state'] == 2

    @defer.inlineCallbacks
    def test_setBuildState_missing(self):
        """
        Updates to missing builds go to /dev/null.
        """
        yield self.db.setBuildState(42, 2)

    @defer.inlineCallbacks
    def test_setBuildFile(self):
        """
        We can update a build's file.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.setBuildFile(1, 'foo.deb')
        build = yield self.db.getBuild(1)
        assert build['build_file'] == 'foo.deb'

    @defer.inlineCallbacks
    def test_setBuildFile_missing(self):
        """
        Updates to missing builds go to /dev/null.
        """
        yield self.db.setBuildFile(42, 'foo.deb')

    @defer.inlineCallbacks
    def test_createRelease_getRelease(self):
        """
        We can create a release and then get it.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        release_data = {
            'flow_id': 1,
            'build_id': 1,
            'waiting': True,
            'scheduled': None,
            'release_date': now_utc(),
            'lock': False,
        }
        [release_id] = yield self.db.createRelease(release_data)
        release = yield self.db.getRelease(release_id)
        self.assertEqual(release, dictmerge(release_data, id=release_id))

    @defer.inlineCallbacks
    def test_getReleaseStream(self):
        """
        We can get a release stream.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        stream = yield self.db.getReleaseStream(RELEASESTREAM_QA['id'])
        assert stream == RELEASESTREAM_QA

    @defer.inlineCallbacks
    def test_getReleaseStream_missing(self):
        """
        We can't get a release stream that doesn't exist.
        """
        yield self.assertFailure(self.db.getReleaseStream(12), Exception)

    @defer.inlineCallbacks
    def test_checkReleaseSchedule_unscheduled(self):
        """
        We can check the schedule status of a release which isn't scheduled.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.runInsert('sideloader_release', RELEASE_1)

        assert RELEASE_1['scheduled'] is None
        scheduled_now = self.db.checkReleaseSchedule(RELEASE_1)
        assert scheduled_now is True

    @defer.inlineCallbacks
    def test_checkReleaseSignoff_none_required(self):
        """
        We can check the signoff status of a release which doesn't require
        signoff.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.runInsert('sideloader_release', RELEASE_1)

        assert RELEASEFLOW_QA['require_signoff'] is False
        signed_off = yield self.db.checkReleaseSignoff(1, RELEASEFLOW_QA)
        assert signed_off is True

    @defer.inlineCallbacks
    def test_updateReleaseLocks(self):
        """
        We can update the release lock.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.runInsert('sideloader_release', RELEASE_1)

        assert RELEASE_1['lock'] is False
        yield self.db.updateReleaseLocks(1, True)
        release = yield self.db.getRelease(1)
        assert release['lock'] is True
        yield self.db.updateReleaseLocks(1, False)
        release = yield self.db.getRelease(1)
        assert release['lock'] is False

    @defer.inlineCallbacks
    def test_updateReleaseState_no_args(self):
        """
        We can update the release state with default values.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_build', BUILD_1)
        yield self.db.runInsert('sideloader_release', RELEASE_1)

        yield self.db.updateReleaseLocks(1, True)
        release = yield self.db.getRelease(1)
        assert release['lock'] is True
        assert release['waiting'] is True

        yield self.db.updateReleaseState(1)
        release = yield self.db.getRelease(1)
        assert release['lock'] is False
        assert release['waiting'] is False

    @defer.inlineCallbacks
    def test_getFlow(self):
        """
        We can get information about a release flow.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        flow = yield self.db.getFlow(1)
        assert flow == RELEASEFLOW_QA

    def test_getFlowNotifyList_empty(self):
        """
        We get an empty notify list when a flow has nobody to notify.
        """
        notify_list = self.db.getFlowNotifyList(RELEASEFLOW_QA)
        assert notify_list == []

    @defer.inlineCallbacks
    def test_getReleaseFlow_missing(self):
        """
        We can't get information about a release flow that doesn't exist.
        """
        yield self.assertFailure(self.db.getFlow(42), Exception)

    @defer.inlineCallbacks
    def test_getAutoFlows(self):
        """
        We can get all the autorelease flows for a project.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_PROD)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_PROD)
        flows = yield self.db.getAutoFlows(1)
        assert flows == [RELEASEFLOW_QA]

    @defer.inlineCallbacks
    def test_getAutoFlows_no_flows(self):
        """
        If a project has no autorelease flows, we get an empty list of them.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        flows = yield self.db.getAutoFlows(1)
        assert flows == []

    @defer.inlineCallbacks
    def test_getWebhooks(self):
        """
        We can get all webhooks for a release flow.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)
        yield self.db.runInsert('sideloader_webhook', WEBHOOK_QA_1)
        yield self.db.runInsert('sideloader_webhook', WEBHOOK_QA_2)

        webhooks = yield self.db.getWebhooks(RELEASEFLOW_QA['id'])
        assert id_sorted(webhooks) == [WEBHOOK_QA_1, WEBHOOK_QA_2]

    @defer.inlineCallbacks
    def test_getWebhooks_no_webhooks(self):
        """
        If a release flow has no webhooks, we get an empty list of them.
        """
        yield self.db.runInsert('sideloader_releasestream', RELEASESTREAM_QA)
        yield self.db.runInsert('sideloader_project', PROJECT_SIDELOADER)
        yield self.db.runInsert('sideloader_releaseflow', RELEASEFLOW_QA)

        webhooks = yield self.db.getWebhooks(RELEASEFLOW_QA['id'])
        assert webhooks == []
