from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    github_url = models.CharField(max_length=255)
    created_by_user = models.ForeignKey(User, related_name="ProjectCreatedBy")
