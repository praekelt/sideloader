from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse

from sideloader.models import Project, Build, ReleaseStream
from sideloader import forms, tasks

import hashlib
import uuid
import time
import random
import urlparse

from celery.task.control import revoke

@login_required
def index(request):
    if request.user.is_superuser:
        builds = Build.objects.filter(state=0).order_by('-build_time')
        last_builds = Build.objects.filter(state__gt=0).order_by('-build_time')[:10]
    else:
        projects = request.user.project_set.all()
        all_builds = Build.objects.filter(state=0).order_by('-build_time')
        last_builds = Build.objects.filter(state__gt=0, project__in=projects).order_by('-build_time')[:10]

        builds = []
        for build in all_builds:
            if build.project in projects:
                builds.append(build)
            else:
                builds.append({'build_time': build.build_time, 'project': {'name': 'Private'}})

    return render(request, "index.html", {
        'builds': builds, 
        'last_builds': last_builds
    })

@login_required
def accounts_profile(request):
    if request.method == "POST":
        form = forms.UserForm(request.POST, instance=request.user)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return redirect('home')
    else:
        form = forms.UserForm(instance=request.user)

    return render(request, "accounts_profile.html", {
        'form': form
    })

@login_required
def release_index(request):
    releases = ReleaseStream.objects.all()
    return render(request, "releases/index.html", {'releases': releases})

@login_required
def release_create(request):
    if not request.user.is_superuser:
        return redirect('home')

    if request.method == "POST":
        form = forms.ReleaseForm(request.POST)
        if form.is_valid():
            release = form.save(commit=False)
            release.save()

            return redirect('release_index')

    else:
        form = forms.ReleaseForm()

    return render(request, 'releases/create_edit.html', {
        'form': form
    })

@login_required
def release_edit(request, id):
    if not request.user.is_superuser:
        return redirect('home')

    release = ReleaseStream.objects.get(id=id)
    if request.method == "POST":
        form = forms.ReleaseForm(request.POST, instance=release)

        if form.is_valid():
            release = form.save(commit=False)
            release.save()

            return redirect('release_index')

    else:
        form = forms.ReleaseForm(instance=release)

    return render(request, 'releases/create_edit.html', {
        'form': form, 
        'release': release
    })

@login_required
def projects_index(request):
    if request.user.is_superuser:
        projects = Project.objects.all()
    else:
        projects = request.user.project_set.all()
    
    d = {'projects': projects}
    return render(request, "projects/projects.html", d)

@login_required
def build_view(request, id):
    build = Build.objects.get(id=id)

    if (request.user.is_superuser) or (
        build.project in request.user.project_set.all()):
        d = {'build': build}
    else:
        d = {}

    return render(request, 'projects/build_view.html', d)

@login_required
def projects_view(request, id):
    project = Project.objects.get(id=id)
    if project in request.user.project_set.all():
        builds = Build.objects.filter(project=project).order_by('-build_time')

        hook_uri = urlparse.urljoin(request.build_absolute_uri(), 
            reverse('api_build', kwargs={'hash':project.idhash}))

        d = {
            'project': project, 
            'hook_uri': hook_uri,
            'builds': builds
        }
    else:
        d = {}

    return render(request, 'projects/view.html', d)

@login_required
def projects_create(request):
    if not request.user.is_superuser:
        return redirect('home')

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
    if not request.user.is_superuser:
        return redirect('home')

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
    d = {
        'form': form, 
        'project': project
    }

    return render(request, 'projects/create_edit.html', d)

@login_required
def build_cancel(request, id):
    build = Build.objects.get(id=id)
    if build.project in request.user.project_set.all():
        build.state = 3 
        build.save()
        revoke(build.task_id, terminate=True)

    return redirect('home')

@login_required
def projects_build(request, id):
    project = Project.objects.get(id=id)
    if project and (project in request.user.project_set.all()):
        current_builds = Build.objects.filter(project=project, state=0)
        if not current_builds:
            build = Build.objects.create(project=project, state=0)
            task = tasks.build.delay(build, project.github_url, project.branch)
            build.task_id = task.task_id
            build.save()
            return redirect('home')

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

