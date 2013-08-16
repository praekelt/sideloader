from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    name = models.CharField(max_length=255)
    github_url = models.CharField(max_length=255, unique=True)
    branch = models.CharField(max_length=255)
    created_by_user = models.ForeignKey(User, related_name="ProjectCreatedBy")
    
    idhash = models.CharField(max_length=48)
    allowed_users = models.ManyToManyField(User, blank=True)

class Build(models.Model):
    project = models.ForeignKey(Project)
    build_time = models.DateTimeField(auto_now_add=True)

    # 0 - queued, 1 - Success, 2 - Failed
    state = models.IntegerField(default=0)

    log = models.TextField(default="")
