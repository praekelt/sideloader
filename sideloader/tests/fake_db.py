from copy import deepcopy
from functools import wraps

from twisted.internet import task


def async(f):
    """
    Make the wrapped function async by calling it a millisecond in the future.
    """
    @wraps(f)
    def wrapper(self, *args, **kw):
        return task.deferLater(self.clock, 0.001, f, self, *args, **kw)
    return wrapper


class FakeDB(object):
    """
    A test double for sideloader.task_db.
    """

    def __init__(self, clock):
        self.clock = clock
        self._releasestream = {}
        self._project = {}
        self._build = {}
        self._buildnumbers = {}
        self._releaseflow = {}

    @async
    def runInsert(self, table, keys):
        data = getattr(self, table.replace('sideloader_', '_'))
        data[keys['id']] = deepcopy(keys)
        return (keys['id'],)

    # Project queries

    @async
    def getProject(self, id):
        return deepcopy(self._project[id])

    @async
    def updateBuildLog(self, id, data):
        if id in self._build:
            self._build[id]['log'] = data

    @async
    def getProjectNotificationSettings(self, id):
        prj = self._project[id]
        return (prj['name'], prj['notifications'], prj['slack_channel'])

    # Build queries

    @async
    def getBuild(self, id):
        return deepcopy(self._build[id])

    @async
    def getBuildNumber(self, repo):
        return self._buildnumbers.get(repo, 0)

    @async
    def setBuildNumber(self, repo, num, create=False):
        assert type(num) is int
        if create:
            assert repo not in self._buildnumbers
        elif repo not in self._buildnumbers:
            return
        self._buildnumbers[repo] = num

    @async
    def setBuildState(self, id, state):
        if id in self._build:
            self._build[id]['state'] = int(state)

    @async
    def setBuildFile(self, id, file):
        if id in self._build:
            self._build[id]['build_file'] = file

    # Release queries

    def createRelease(self, release):
        raise NotImplentedError("TODO")

    def checkReleaseSchedule(self, release):
        raise NotImplentedError("TODO")

    def releaseSignoffCount(self, release_id):
        raise NotImplentedError("TODO")

    def signoff_remaining(self, release_id, flow):
        raise NotImplentedError("TODO")

    def checkReleaseSignoff(self, release_id, flow):
        raise NotImplentedError("TODO")

    def countReleases(self, id, waiting=False, lock=False):
        raise NotImplentedError("TODO")

    def getReleases(self, flowid=None, waiting=None, lock=None):
        raise NotImplentedError("TODO")

    def getRelease(self, id):
        raise NotImplentedError("TODO")

    def getReleaseStream(self, id):
        raise NotImplentedError("TODO")

    def updateReleaseLocks(self, id, lock):
        raise NotImplentedError("TODO")

    def updateReleaseState(self, id, lock=False, waiting=False):
        raise NotImplentedError("TODO")

    # Flow queries

    def getFlow(self, id):
        raise NotImplentedError("TODO")

    def getFlowSignoffList(self, flow):
        raise NotImplentedError("TODO")

    def getFlowNotifyList(self, flow):
        raise NotImplentedError("TODO")

    @async
    def getAutoFlows(self, id):
        return [flow for flow in self._releaseflow.values()
                if flow['auto_release'] and flow['project_id'] == id]

    def getNextFlowRelease(self, flow_id):
        raise NotImplentedError("TODO")

    def getLastFlowRelease(self, flow_id):
        raise NotImplentedError("TODO")

    # Targets

    def getFlowTargets(self, flow_id):
        raise NotImplentedError("TODO")

    def getServer(self, id):
        raise NotImplentedError("TODO")

    def updateTargetState(self, id, state):
        raise NotImplentedError("TODO")

    def updateTargetLog(self, id, log):
        raise NotImplentedError("TODO")

    def updateTargetBuild(self, id, build):
        raise NotImplentedError("TODO")

    def updateServerStatus(self, id, status):
        raise NotImplentedError("TODO")
