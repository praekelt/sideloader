import os
import uuid
import shutil
import sys
import subprocess

import smtplib

from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart

from django.conf import settings
from sideloader import models, specter, slack
from celery import task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@task(time_limit=10)
def sendNotification(message, project):
    if project.notifications:
        logger.info("Sending notification %s" % repr(message))
        if settings.SLACK_TOKEN:
            if project.slack_channel:
                channel = project.slack_channel
            else:
                channel=settings.SLACK_CHANNEL

            sc = slack.SlackClient(settings.SLACK_HOST,
                    settings.SLACK_TOKEN, channel)

            sc.message(project.name + ": " + message)

@task(time_limit=60)
def sendEmail(to, content, subject):
    start = '<html><head></head><body style="font-family:arial,sans-serif;">'
    end = '</body></html>'

    cont = MIMEText(start+content+end, 'html')

    msg = MIMEMultipart('related')

    msg['Subject'] = subject
    msg['From'] = settings.SIDELOADER_FROM
    msg['To'] = to
    msg.attach(cont)

    s = smtplib.SMTP()
    s.connect()
    s.sendmail(msg['From'], msg['To'], msg.as_string())
    s.close()

@task(time_limit=60)
def sendSignEmail(to, name, release, h):
    cont = 'A build release has been requested for "%s" to release stream "%s".<br/><br/>' % (name, release)
    cont += "You are listed as a contact to approve this release. "
    cont += "If you would like to do so please click the link below,"
    cont += " if you do not agree then simply ignore this mail.<br/><br/>"

    cont += "http://%s/api/rap/%s" % (settings.SIDELOADER_DOMAIN, h)

    sendEmail(to, cont, '%s release approval - action required' % name)

@task(time_limit=60)
def sendScheduleNotification(to, release):
    cont = 'A %s release for %s has been scheduled for %s UTC' % (
        release.flow.name,
        release.flow.project.name,
        release.scheduled
    )

    sendEmail(to, cont, '%s %s release scheduled - %s UTC' % (
        release.flow.project.name,
        release.flow.name,
        release.scheduled
    ))

@task(time_limit=60)
def doRelease(build, flow, scheduled=None):
    release = models.Release.objects.create(
        flow=flow,
        build=build,
        waiting=True,
        scheduled=scheduled
    )

    release.save()

    if scheduled:
        sendNotification.delay('Deployment scheduled for build %s at %s UTC to %s' % (
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

@task(time_limit=1800)
def pushTargets(release, flow):
    """
    Pushes a release using Specter
    """
    targets = flow.target_set.all()

    for target in targets:

        logger.info("Deploing release %s to target %s" % (repr(release), target.server.name))

        sendNotification.delay('Deployment started for build %s -> %s' % (
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
                sendNotification.delay('Deployment of build %s to %s failed!' % (
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
                elif flow.service_restart
                    restart = sc.get_all_stop()['stdout']
                    restart += sc.get_all_start()['stdout']

                target.deploy_state=2
                target.log = '\n'.join([
                    stop, result['stdout'], result['stderr'], puppet, start, restart
                ])
                target.current_build = release.build
                target.save()
                sendNotification.delay('Deployment of build %s to %s complete' % (
                    release.build.build_file,
                    target.server.name
                ), release.flow.project)

            server.specter_status = "Reachable"

        except Exception, e:
            target.log = str(e)
            target.deploy_state=3
            target.save()

            server.specter_status = str(e)
           
            sendNotification.delay('Deployment of build %s to %s failed!' % (
                release.build.build_file,
                target.server.name
            ), release.flow.project)

        server.save()

    release.lock = False
    release.waiting = False
    release.save()

@task(time_limit=300)
def streamRelease(release):
    sendNotification.delay('Pushing build %s to %s stream' % (
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

@task(time_limit=300)
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

@task(time_limit=60)
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

@task(time_limit=1800)
def build(build):
    """
    Use subprocess to execute a build, update the db with results along the way
    """

    project = build.project
    giturl = project.github_url
    chunks = giturl.split(':')[1].split('/')
    repo = chunks[-1][:-4]

    branch = project.branch

    # Get a build number
    try:
        buildnums = models.BuildNumbers.objects.get(package=repo)
    except models.BuildNumbers.DoesNotExist:
        buildnums = models.BuildNumbers.objects.create(package=repo)

    build_num = buildnums.build_num + 1

    # Increment the project build number
    buildnums.build_num += 1
    buildnums.save()

    id = project.idhash

    local = os.path.dirname(sys.argv[0])
    buildpack = os.path.join(local, 'bin/build_package')

    # Figure out some directory paths
    workspace = os.path.join('/workspace', id)
    package = os.path.join(workspace, 'package')
    packages = '/workspace/packages'

    if settings.DEBUG:
        print "Executing build %s %s" % (giturl, branch)

    build.save()

    sendNotification.delay(
        'Build <http://%s/projects/build/view/%s|#%s> started for branch %s' % (
            settings.SIDELOADER_DOMAIN, build.id, build.id, branch
        ), build.project)

    args = [buildpack, '--branch', branch, '--build', str(build_num), '--id', id]

    if build.project.deploy_file:
        args.extend(['--deploy-file', build.project.deploy_file])

    if build.project.release_stream:
        args.extend(['--push', build.project.release_stream.push_command])

    args.append(giturl)

    builder = subprocess.Popen(args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=local, bufsize=1)

    for line in iter(builder.stdout.readline, b''):
        build.log += line
        build.save()

    builder.communicate()


    if builder.returncode != 0:
        build.state = 2
        sendNotification.delay('Build <http://%s/projects/build/view/%s|#%s> failed' % (
            settings.SIDELOADER_DOMAIN, build.id, build.id
        ), build.project)
    else:
        if not os.path.exists(packages):
            os.makedirs(packages)

        debs = [i for i in os.listdir(package) if i[-4:]=='.deb']
        if not debs:
            # We must have failed actually
            build.state = 2
            sendNotification.delay('Build <http://%s/projects/build/view/%s|#%s> failed' % (
                settings.SIDELOADER_DOMAIN, build.id, build.id
            ), build.project)

        else:
            build.state = 1
            sendNotification.delay('Build <http://%s/projects/build/view/%s|#%s> successful' % (
                settings.SIDELOADER_DOMAIN, build.id, build.id
            ), build.project)

            deb = debs[0]
            build.build_file = deb

            # Relocate the package to our archive
            shutil.move(os.path.join(package, deb), os.path.join(packages, deb))

            # Find any auto-release streams
            flows = build.project.releaseflow_set.filter(auto_release=True)
            if flows:
                build.save()
                for flow in flows:
                    doRelease.delay(build, flow)

    build.save()
