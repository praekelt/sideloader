from django.contrib.auth.models import User
from django import forms
from bootstrap.forms import BootstrapModelForm, BootstrapForm
import models

class ProjectForm(BootstrapModelForm):

    class Meta:
        model = models.Project
        exclude = ('idhash', 'created_by_user',)

