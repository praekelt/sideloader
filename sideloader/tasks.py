import os
import uuid
import shutil
import sys

from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart

#from django.conf import settings
from sideloader import specter, slack
from skeleton import settings

from twisted.mail.smtp import sendmail
from twisted.internet import defer, reactor, protocol
from twisted.python import log
from twisted.enterprise import adbapi

from rhumba import RhumbaPlugin

class BuildProcess(protocol.ProcessProtocol):
    def __init__(self, id, prjid, idhash, db, callback):
        self.id = id
        self.project_id = prjid
        self.idhash = idhash
        self.db = db
        self.data = ""
        self.callback = callback

    def log(self, msg):
        log.msg('[%s] %s' % (self.id, msg))

    @defer.inlineCallbacks
    def outReceived(self, data):
        self.log(data)
        self.data = self.data + data

        yield self.db.updateBuildLog(self.id, self.data)

    @defer.inlineCallbacks
    def errReceived(self, data):
        self.log(data)
        self.data = self.data + data
        
        yield self.db.updateBuildLog(self.id, self.data)

    def processExited(self, reason):
        print "processExited, status %d" % (reason.value.exitCode,)
        reactor.callLater(0, self.callback, reason.value.exitCode,
            self.project_id, self.id, self.idhash)

    def processEnded(self, reason):
        print "processEnded, status %d" % (reason.value.exitCode,)
        reactor.callLater(0, self.callback, reason.value.exitCode,
            self.project_id, self.id, self.idhash)

class SideloaderDB(object):
    def __init__(self):
        self.p = adbapi.ConnectionPool('psycopg2',
            database='sideloader',
            host='localhost',
            user='postgres',
        )

    @defer.inlineCallbacks
    def getProject(self, id):
        
        q = yield self.p.runQuery(
            'SELECT name, github_url, branch, deploy_file, build_script, '
            'package_name, postinstall_script, package_manager, deploy_type, '
            'idhash FROM sideloader_project WHERE id=%s', (id,))

        defer.returnValue(q[0])

    def updateBuildLog(self, id, log):
        return self.p.runOperation('UPDATE sideloader_build SET log=%s WHERE id=%s', (log, id))

    @defer.inlineCallbacks
    def getProjectNotificationSettings(self, id):
        
        q = yield self.p.runQuery(
            'SELECT name, notifications, slack_channel FROM sideloader_project'
            ' WHERE id=%s', (id,))

        defer.returnValue(q[0])


    @defer.inlineCallbacks
    def getBuild(self, id):
        q = yield self.p.runQuery('SELECT state, build_file, project_id FROM sideloader_build WHERE id=%s', (id,))

        defer.returnValue(q[0])

    @defer.inlineCallbacks
    def getBuildNumber(self, repo):
        q = yield self.p.runQuery('SELECT build_num FROM sideloader_buildnumbers WHERE package=%s', (repo,))
        if q:
            defer.returnValue(q[0][0])
        else:
            defer.returnValue(0)

    def setBuildNumber(self, repo, num):
        return self.p.runOperation('UPDATE sideloader_buildnumbers SET build_num=%s WHERE package=%s', (num, repo))

    def setBuildState(self, id, state):
        return self.p.runOperation('UPDATE sideloader_build SET state=%s WHERE id=%s', (state, id))

    def setBuildFile(self, id, f):
        return self.p.runOperation('UPDATE sideloader_build SET build_file=%s WHERE id=%s', (f, id))

class Plugin(RhumbaPlugin):
    def __init__(self, *a):
        RhumbaPlugin.__init__(self, *a)

        self.db = SideloaderDB()

    @defer.inlineCallbacks
    def sendEmail(self, to, content, subject):
        start = '<html><head></head><body style="font-family:arial,sans-serif;">'
        end = '</body></html>'

        cont = MIMEText(start+content+end, 'html')

        msg = MIMEMultipart('related')

        msg['Subject'] = subject
        msg['From'] = settings.SIDELOADER_FROM
        msg['To'] = to
        msg.attach(cont)

        yield sendmail(msg['From'], msg['To'], msg.as_string())

    @defer.inlineCallbacks
    def sendNotification(self, message, project_id):
        defer.returnValue(None)
        (name, notify, slack_channel
            ) = yield self.db.getProjectNotificationSettings(project_id)
        
        if notify:
            logger.info("Sending notification %s" % repr(message))
            if settings.SLACK_TOKEN:
                if slack_channel:
                    channel = slack_channel
                else:
                    channel=settings.SLACK_CHANNEL

                sc = slack.SlackClient(settings.SLACK_HOST,
                        settings.SLACK_TOKEN, channel)

                yield sc.message(name + ": " + message)


    def sendSignEmail(self, to, name, release, h):
        cont = 'A build release has been requested for "%s" to release stream "%s".<br/><br/>' % (name, release)
        cont += "You are listed as a contact to approve this release. "
        cont += "If you would like to do so please click the link below,"
        cont += " if you do not agree then simply ignore this mail.<br/><br/>"

        cont += "http://%s/api/rap/%s" % (settings.SIDELOADER_DOMAIN, h)

        return self.sendEmail(to, cont, '%s release approval - action required' % name)

    def sendScheduleNotification(to, release):
        cont = 'A %s release for %s has been scheduled for %s UTC' % (
            release.flow.name,
            release.flow.project.name,
            release.scheduled
        )

        yield sendEmail(to, cont, '%s %s release scheduled - %s UTC' % (
            release.flow.project.name,
            release.flow.name,
            release.scheduled
        ))

    @defer.inlineCallbacks
    def doRelease(self, build, flow, scheduled=None):
        release = models.Release.objects.create(
            flow=flow,
            build=build,
            waiting=True,
            scheduled=scheduled
        )

        release.save()

        if scheduled:
            self.sendNotification.delay('Deployment scheduled for build %s at %s UTC to %s' % (
                release.build.build_file,
                release.scheduled,
                release.flow.name
            ), release.flow.project)

            for name, email in settings.ADMINS:
                sendScheduleNotification.delay(email, release)

        if flow.require_signoff:
            # Create a signoff release
            # Turn whatever junk is in the email text into a list
            users = flow.email_list()

            for email in users:
                so = models.ReleaseSignoff.objects.create(
                    release=release,
                    signature=email,
                    idhash=uuid.uuid1().get_hex(),
                    signed=False
                )
                so.save()
                sendSignEmail.delay(email, build.project.name, flow.name, so.idhash)

    def pushTargets(release, flow):
        """
        Pushes a release using Specter
        """
        targets = flow.target_set.all()

        for target in targets:

            logger.info("Deploing release %s to target %s" % (repr(release), target.server.name))

            self.sendNotification.delay('Deployment started for build %s -> %s' % (
                release.build.build_file,
                target.server.name
            ), release.flow.project)

            server = target.server

            target.deploy_state=1
            target.save()

            sc = specter.SpecterClient(target.server.name,
                    settings.SPECTER_AUTHCODE, settings.SPECTER_SECRET)

            url = target.release.project.github_url
            package = url.split(':')[1].split('/')[-1][:-4]
            
            url = "%s/%s" % (
                settings.SIDELOADER_PACKAGEURL, 
                release.build.build_file
            )

            stop, start, restart, puppet = "", "", "", ""

            try:
                if flow.service_pre_stop:
                    stop = sc.get_all_stop()['stdout']

                result = sc.post_install({
                    'package': package,
                    'url': url
                })

                if ('error' in result) or (result.get('code',2) > 0) or (
                    result.get('stderr') and not result.get('stdout')):
                    # Errors during deployment
                    target.deploy_state=3
                    if 'error' in result:
                        target.log = '\n'.join([stop, result['error']])
                    else:
                        target.log = '\n'.join([
                            stop, result['stdout'], result['stderr']
                        ])
                    target.save()
                    self.sendNotification.delay('Deployment of build %s to %s failed!' % (
                        release.build.build_file,
                        target.server.name
                    ), release.flow.project)

                    # Start services back up even on failure
                    if flow.service_pre_stop:
                        start = sc.get_all_start()['stdout']
                else:
                    if flow.puppet_run:
                        puppet = sc.get_puppet_run()['stdout']

                    if flow.service_pre_stop:
                        start = sc.get_all_start()['stdout']
                    elif flow.service_restart:
                        restart = sc.get_all_stop()['stdout']
                        restart += sc.get_all_start()['stdout']

                    target.deploy_state=2
                    target.log = '\n'.join([
                        stop, result['stdout'], result['stderr'], puppet, start, restart
                    ])
                    target.current_build = release.build
                    target.save()
                    self.sendNotification.delay('Deployment of build %s to %s complete' % (
                        release.build.build_file,
                        target.server.name
                    ), release.flow.project)

                server.specter_status = "Reachable"

            except Exception, e:
                target.log = str(e)
                target.deploy_state=3
                target.save()

                server.specter_status = str(e)
               
                self.sendNotification.delay('Deployment of build %s to %s failed!' % (
                    release.build.build_file,
                    target.server.name
                ), release.flow.project)

            server.save()

        release.lock = False
        release.waiting = False
        release.save()

    def streamRelease(release):
        self.sendNotification.delay('Pushing build %s to %s stream' % (
            release.build.build_file,
            release.flow.stream.name
        ), release.flow.project)
        # Stream release
        push_cmd = release.flow.stream.push_command
        os.system(push_cmd % os.path.join(
            '/workspace/packages/', release.build.build_file))

        release.lock = False
        release.waiting = False
        release.save()

    def cleanReleases(release):
        if release.waiting:
            flow = release.flow
            next_release = flow.next_release()
            last_release = flow.last_release()

            # Cleanup stale releases, deprecated by request date
            if next_release:
                if release.release_date < next_release.release_date:
                    release.waiting = False
                    release.lock = False
                    release.save()

            if last_release:
                if release.release_date < last_release.release_date:
                    release.waiting = False
                    release.lock = False
                    release.save()

    def runRelease(release):
        if release.waiting:
            flow = release.flow

            if release.check_schedule() and release.check_signoff():
                release.lock = True
                release.save()

                # Release the build
                if flow.stream_mode == 0:
                    # Stream only
                    streamRelease.delay(release)
                elif flow.stream_mode == 2:
                    # Stream and targets
                    streamRelease.delay(release)
                    pushTargets.delay(release, flow)
                else:
                    # Target only
                    pushTargets.delay(release, flow)

    def checkReleases():
        releases = models.Release.objects.filter(waiting=True, lock=False)
        logger.info("Release queue is at %s" % len(releases))

        skip = []

        # Clean old releases
        for release in releases:
            cleanReleases(release)

            current = models.Release.objects.filter(flow=release.flow, waiting=True, lock=True).count()

            if current > 0:
                logger.info("Skipping release %s on this run - %s in queue" % (repr(release), current))
                skip.append(release.id)

        # Lock all the release objects we now see
        releases = models.Release.objects.filter(waiting=True, lock=False).exclude(id__in=skip)

        for release in releases:
            release.lock=True
            release.save()

        for release in releases:
            logger.info("Running release %s" % repr(release))
            runRelease.delay(release)

    @defer.inlineCallbacks
    def endBuild(self, code, project_id, build_id, idhash):
        workspace = os.path.join('/workspace', idhash)
        package = os.path.join(workspace, 'package')
        packages = '/workspace/packages'

        if code != 0:
            yield self.db.setBuildState(build_id, 2)

            reactor.callLater(0, self.sendNotification,
                'Build <http://%s/projects/build/view/%s|#%s> failed' % (
                    settings.SIDELOADER_DOMAIN, build_id, build_id
                ), project_id)

        else:
            if not os.path.exists(packages):
                os.makedirs(packages)

            debs = [i for i in os.listdir(package) if ((i[-4:]=='.deb') or (i[-4:]=='.rpm'))]

            if not debs:
                # We must have failed actually
                yield self.db.setBuildState(build_id, 2)

                reactor.callLater(0, self.sendNotification,
                    'Build <http://%s/projects/build/view/%s|#%s> failed' % (
                        settings.SIDELOADER_DOMAIN, build_id, build_id
                    ), project_id)

            else:
                deb = debs[0]

                yield self.db.setBuildState(build_id, 1)
                yield self.db.setBuildFile(build_id, deb)

                reactor.callLater(0, self.sendNotification,
                    'Build <http://%s/projects/build/view/%s|#%s> successful' % (
                        settings.SIDELOADER_DOMAIN, build_id, build_id
                    ),
                    project_id)

                # Relocate the package to our archive
                shutil.move(os.path.join(package, deb), os.path.join(packages, deb))

                # Find any auto-release streams
                # XXX Implement auto flow XXX
                #flows = build.project.releaseflow_set.filter(auto_release=True)
                #if flows:
                #    build.save()
                #    for flow in flows:
                #        doRelease.delay(build, flow)

    @defer.inlineCallbacks
    def call_build(self, params):
        """
        Use subprocess to execute a build, update the db with results along the way
        """
        
        print params 

        build_id = params['build_id']

        state, build_file, project_id = yield self.db.getBuild(build_id)

        (
            name, giturl, branch, deploy_file, build_script, package_name,
            postinstall_script, package_manager, deploy_type, idhash
        ) = yield self.db.getProject(project_id)
        
        chunks = giturl.split(':')[1].split('/')
        repo = chunks[-1][:-4]

        # Get a build number
        build_num = yield self.db.getBuildNumber(repo)
        build_num += 1

        # Increment the project build number
        yield self.db.setBuildNumber(repo, build_num)

        local = self.config.get('localdir', 
            os.path.join(os.path.dirname(sys.argv[0]), '../..'))
        buildpack = os.path.join(local, 'bin/build_package')

        # Figure out some directory paths

        if settings.DEBUG:
            print "Executing build %s %s" % (giturl, branch)

        reactor.callLater(0, self.sendNotification, 
            'Build <http://%s/projects/build/view/%s|#%s> started for branch %s' % (
                settings.SIDELOADER_DOMAIN, build_id, build_id, branch
            ), project_id)

        args = ['build_package', '--branch', branch, '--build', str(build_num), '--id', idhash]

        if deploy_file:
            args.extend(['--deploy-file', deploy_file])

        if package_name:
            args.extend(['--name', package_name])

        if build_script:
            args.extend(['--build-script', build_script])

        if postinstall_script:
            args.extend(['--postinst-script', postinstall_script])

        if package_manager:
            args.extend(['--packman', package_manager])

        if deploy_type:
            args.extend(['--dtype', deploy_type])

        args.append(giturl)

        self.log('Spawning build %s: %s :: %s %s' % (build_id, local, buildpack, repr(args)))

        buildProcess = BuildProcess(build_id, project_id, idhash, self.db, self.endBuild)

        proc = reactor.spawnProcess(buildProcess, buildpack, args=args, path=local, env=os.environ)


