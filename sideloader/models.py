import time
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Server(models.Model):
    name = models.CharField(max_length=255)
    last_checkin = models.DateTimeField(auto_now_add=True)
    last_puppet_run = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=255, default='', blank=True)
    change = models.BooleanField(default=True)
    specter_status = models.CharField(max_length=255, default='', blank=True)

    def age(self):
        """Returns seconds since last checkin"""
        now = timezone.now()
        return int((now - self.last_checkin).total_seconds())

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__().encode('utf-8', 'replace')


class ReleaseStream(models.Model):
    name = models.CharField(max_length=255)
    push_command = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__().encode('utf-8', 'replace')

class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    github_url = models.CharField(max_length=255)
    branch = models.CharField(max_length=255)

    package_manager = models.CharField(max_length=64, default='deb')
    deploy_type = models.CharField(max_length=64, default='virtualenv')
    deploy_file = models.CharField(max_length=255, default='.deploy.yaml', blank=True)
    package_name = models.CharField(max_length=255, default='', blank=True)
    build_script = models.CharField(max_length=255, default='', blank=True)
    postinstall_script = models.CharField(
        max_length=255, default='', blank=True)

    created_by_user = models.ForeignKey(User, related_name="ProjectCreatedBy")
    release_stream = models.ForeignKey(ReleaseStream, null=True)
    idhash = models.CharField(max_length=48)
    allowed_users = models.ManyToManyField(User, blank=True)
    notifications = models.BooleanField(default=True)
    slack_channel = models.CharField(max_length=255, default='', blank=True)

class BuildNumbers(models.Model):
    package = models.CharField(max_length=255, unique=True)
    build_num = models.IntegerField(default=0)

class ReleaseFlow(models.Model):
    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project)

    stream_mode = models.IntegerField(default=0)
    stream = models.ForeignKey(ReleaseStream, null=True, blank=True)

    require_signoff = models.BooleanField(default=False)
    signoff_list = models.TextField(blank=True)
    quorum = models.IntegerField(default=0)

    notify = models.BooleanField(default=False)
    notify_list = models.TextField(blank=True)

    service_restart = models.BooleanField(default=True)
    service_pre_stop = models.BooleanField(default=False)
    puppet_run = models.BooleanField(default=True)

    auto_release = models.BooleanField(default=False)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__().encode('utf-8', 'replace')

    def email_list(self):
        if not '@' in self.signoff_list:
            return []

        return self.signoff_list.replace('\r', ' ').replace(
            '\n', ' ').replace(',', ' ').strip().split()

    def last_release(self):
        rs = self.release_set.filter(waiting=False).order_by('-release_date')
        if rs:
            return rs[0]
        else:
            return None

    def next_release(self):
        rs = self.release_set.filter(waiting=True).order_by('-release_date')
        if rs:
            return rs[0]
        else:
            return None

class Build(models.Model):
    project = models.ForeignKey(Project)
    build_time = models.DateTimeField(auto_now_add=True)

    # 0 - queued, 1 - Success, 2 - Failed, 3 - Canceled
    state = models.IntegerField(default=0)

    task_id = models.CharField(max_length=255, default='')

    log = models.TextField(default="")

    build_file = models.CharField(max_length=255)

class Target(models.Model):
    server = models.ForeignKey(Server)
    release = models.ForeignKey(ReleaseFlow)

    # 0 - Nothing, 1 - In progress, 2 - Good, 3 - Bad
    deploy_state = models.IntegerField(default=0)

    current_build = models.ForeignKey(Build, null=True, blank=True)
    log = models.TextField(default="")

class ModuleManifest(models.Model):
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=255)
    structure = models.TextField()

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__().encode('utf-8', 'replace')

class ServerManifest(models.Model):
    module = models.ForeignKey(ModuleManifest)
    value = models.TextField()

    release = models.ForeignKey(ReleaseFlow)

    def __unicode__(self):
        return self.module.name

    def __str__(self):
        return self.__unicode__().encode('utf-8', 'replace')

class Release(models.Model):
    release_date = models.DateTimeField(auto_now_add=True)
    flow = models.ForeignKey(ReleaseFlow)
    build = models.ForeignKey(Build)

    scheduled = models.DateTimeField(blank=True, null=True)
    
    waiting = models.BooleanField(default=True)

    lock = models.BooleanField(default=False)

    def signoff_count(self):
        return self.releasesignoff_set.filter(signed=True).count()

    def signoff_remaining(self):
        q = self.flow.quorum
        if q == 0:
            return len(self.flow.email_list()) - self.signoff_count()
        return self.flow.quorum - self.signoff_count()

    def check_signoff(self):
        if not self.flow.require_signoff:
            return True

        if self.signoff_remaining()>0:
            return False

        return True

    def check_schedule(self):
        if not self.scheduled:
            return True

        t = int(time.mktime(self.scheduled.timetuple()))
        if (time.time() - t) > 0:
            return True
        return False

    def release_state(self):
        if self.waiting:
            if self.flow.require_signoff:
                # Sign-offs required
                remaining = self.signoff_remaining()
                if (remaining > 0):
                    return (3, remaining)

            if self.check_schedule():
                return (4, None)
            return (2, self.scheduled)
        else:
            return (1, None)

    def get_state(self):
        c, s = self.release_state()

        messages = {
            1: lambda t: "Deployed",
            2: lambda t: "Scheduled for %s (UTC)" % t.strftime("%d-%m-%Y @ %H:%M"),
            3: lambda t: "Waiting for %s signature%s" % (t, t>1 and 's' or ''),
            4: lambda t: "Running..."
        }
        
        return messages[c](s)

    def __repr__(self):
        return "<Release(release_date=%s, flow=%s, build=%s, scheduled=%s, waiting=%s, lock=%s)>" % (
            self.release_date, self.flow.id, self.build.id, self.scheduled,
            self.waiting, self.lock
        )

class ReleaseSignoff(models.Model):
    release = models.ForeignKey(Release)
    signature = models.CharField(max_length=255)
    idhash = models.CharField(max_length=48)
    signed = models.BooleanField(default=False)

