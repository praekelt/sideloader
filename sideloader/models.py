from django.db import models
from django.contrib.auth.models import User


class ReleaseStream(models.Model):
    name = models.CharField(max_length=255)
    push_command = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__().encode('utf-8', 'replace')

class Project(models.Model):
    name = models.CharField(max_length=255)
    github_url = models.CharField(max_length=255, unique=True)
    branch = models.CharField(max_length=255)
    deploy_file = models.CharField(max_length=255, default='.deploy.yaml')
    created_by_user = models.ForeignKey(User, related_name="ProjectCreatedBy")
    release_stream = models.ForeignKey(ReleaseStream, null=True)
    idhash = models.CharField(max_length=48)
    allowed_users = models.ManyToManyField(User, blank=True)

class Build(models.Model):
    project = models.ForeignKey(Project)
    build_time = models.DateTimeField(auto_now_add=True)

    # 0 - queued, 1 - Success, 2 - Failed
    state = models.IntegerField(default=0)

    log = models.TextField(default="")
