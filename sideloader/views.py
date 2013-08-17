from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse

from sideloader.models import Project, Build
from sideloader import forms, tasks

import hashlib
import uuid
import time
import random
import urlparse

from celery.result import AsyncResult

@login_required
def index(request):
    if request.user.is_superuser:
        pass
    builds = Build.objects.filter(state=0).order_by('-build_time')

    return render(request, "index.html", {
        'builds': builds
    })

@login_required
def accounts_profile(request):
    if request.method == "POST":
        form = forms.UserForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            messages.info(request, 'User settings updated.')
            return redirect('home')
    else:
        form = forms.UserForm(instance=request.user)

    return render(request, "accounts_profile.html", {
        'form': form
    })

@login_required
def projects_index(request):
    projects = Project.objects.all()
    
    d = {'projects': projects}
    return render(request, "projects/projects.html", d)

@login_required
def build_view(request, id):
    build = Build.objects.get(id=id)

    return render(request, 'projects/build_view.html', {
        'build': build
    })

@login_required
def projects_view(request, id):
    project = Project.objects.get(id=id)
    builds = Build.objects.filter(project=project).order_by('-build_time')

    hook_uri = urlparse.urljoin(request.build_absolute_uri(), 
        reverse('api_build', kwargs={'hash':project.idhash}))

    return render(request, 'projects/view.html', {
        'project': project, 
        'hook_uri': hook_uri,
        'builds': builds
    })

@login_required
def projects_create(request):
    if request.method == "POST":
        form = forms.ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by_user = request.user

            # "Security", meep meep
            project.idhash = uuid.uuid1().get_hex()

            project.save()
            form.save_m2m()

            return redirect('projects_index')

    else:
        form = forms.ProjectForm()

    return render(request, 'projects/create_edit.html', {
        'form': form
    })

@login_required
def projects_edit(request, id):
    project = Project.objects.get(id=id)
    if request.method == "POST":
        form = forms.ProjectForm(request.POST, instance=project)

        if form.is_valid():
            project = form.save(commit=False)
            project.save()
            form.save_m2m()

            return redirect('projects_index')

    else:
        form = forms.ProjectForm(instance=project)

    return render(request, 'projects/create_edit.html', {
        'form': form,
        'project': project
    })

@login_required
def projects_build(request, id):
    project = Project.objects.get(id=id)
    if project:
        current_builds = Build.objects.filter(project=project, state=0)
        if not current_builds:
            build = Build.objects.create(project=project, state=0)
            task = tasks.build.delay(build, project.github_url, project.branch)
            build.save()

    return redirect('projects_index')

#############
# API methods

def api_build(request, hash):
    project = Project.objects.get(idhash=hash)
    if project:
        current_builds = Build.objects.filter(project=project, state=0)
        if not current_builds:
            build = Build.objects.create(project=project, state=0)
            task = tasks.build.delay(build, project.github_url, project.branch)
            build.save()

    return redirect('projects_index')

