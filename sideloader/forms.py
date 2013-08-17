from django.contrib.auth.models import User
from django import forms
from bootstrap.forms import BootstrapModelForm, BootstrapForm
import models

class ProjectForm(BootstrapModelForm):

    class Meta:
        model = models.Project
        exclude = ('idhash', 'created_by_user',)

class UserForm(BootstrapModelForm):
    class Meta:
        model = User
        exclude = (
            'email', 'username', 'is_staff', 'is_active', 'is_superuser',
            'last_login', 'date_joined', 'groups', 'user_permissions'
        )
