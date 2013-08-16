from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from sideloader.models import Project
from sideloader import forms

import hashlib
import uuid
import time
import random


@login_required
def index(request):
    if request.user.is_superuser:
        pass

    return render(request, "index.html")

@login_required
def projects_index(request):
    projects = Project.objects.all()
    
    d = {'projects': projects}
    return render(request, "projects/projects.html", d)

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
    return redirect('projects_index')

# API methods

def api_build(request, hash):
    return redirect('projects_index')


