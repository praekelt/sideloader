from datetime import timedelta
import uuid
import urlparse
import json
import hashlib, hmac, base64
import yaml

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.conf import settings

from sideloader import forms, tasks, models

from celery.task.control import revoke

def verifyHMAC(request, data=None):
    clientauth = request.META['HTTP_AUTHORIZATION']
    sig = request.META['HTTP_SIG']

    if clientauth != settings.SPECTER_AUTHCODE:
        return False

    sign = [settings.SPECTER_AUTHCODE, request.method, request.path]

    if data:
        sign.append(
            hashlib.sha1(data).hexdigest()
        )

    mysig = hmac.new(
        key = settings.SPECTER_SECRET,
        msg = '\n'.join(sign),
        digestmod = hashlib.sha1
    ).digest()

    return base64.b64encode(mysig) == sig

def getProjects(request):
    if request.user.is_superuser:
        return models.Project.objects.all().order_by('name')
    else:
        return request.user.project_set.all().order_by('name')

@login_required
def index(request):
    projects = getProjects(request)

    if request.user.is_superuser:
        builds = models.Build.objects.filter(state=0).order_by('-build_time')
        last_builds = models.Build.objects.filter(state__gt=0).order_by('-build_time')[:10]
    else:
        all_builds = models.Build.objects.filter(state=0).order_by('-build_time')
        last_builds = models.Build.objects.filter(state__gt=0, project__in=projects).order_by('-build_time')[:10]

        builds = []
        for build in all_builds:
            if build.project in projects:
                builds.append(build)
            else:
                builds.append({'build_time': build.build_time, 'project': {'name': 'Private'}})

    return render(request, "index.html", {
        'builds': builds,
        'last_builds': last_builds,
        'projects': projects
    })

@login_required
def accounts_profile(request):
    projects = getProjects(request)
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
        'form': form,
        'projects': projects
    })

@login_required
def server_index(request):
    servers = models.Server.objects.all()
    return render(request, "servers/index.html", {
        'servers': servers,
        'projects': getProjects(request)
    })

@login_required
def server_log(request, id):
    # Accepts workflow target ID
    target = models.Target.objects.get(id=id)

    projects = getProjects(request)
    d = {
        'target': target,
        'project': target.release.project,
        'projects': projects
    }

    if (request.user.is_superuser) or (
        target.release.project in request.user.project_set.all()):
        d['target'] = target

    return render(request, "servers/server_log.html", d)

@login_required
def release_index(request):
    releases = models.ReleaseStream.objects.all()
    return render(request, "releases/index.html", {
        'releases': releases,
        'projects': getProjects(request)
    })

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
        'form': form,
        'projects': getProjects(request)
    })

@login_required
def release_edit(request, id):
    if not request.user.is_superuser:
        return redirect('home')

    release = models.ReleaseStream.objects.get(id=id)
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
        'release': release,
        'projects': getProjects(request)
    })

@login_required
def workflow_create(request, project):
    p = models.Project.objects.get(id=project)

    if not request.user.is_superuser:
        return redirect('projects_view', id=p.id)

    if request.method == "POST":
        form = forms.FlowForm(request.POST)
        if form.is_valid():
            flow = form.save(commit=False)

            flow.project = p 
            flow.save()

            # Create target link if none exists
            for server in form.cleaned_data['targets']:
                try:
                    target = models.Target.objects.get(server=server, release=flow)
                except models.Target.DoesNotExist:
                    target = models.Target.objects.create(server=server, release=flow)
                    target.save()

            return redirect('projects_view', id=project)
    else:
        form = forms.FlowForm()

    return render(request, 'flows/create_edit.html', {
        'form': form,
        'project': p,
        'projects': getProjects(request)
    })

@login_required
def workflow_edit(request, id):
    workflow = models.ReleaseFlow.objects.get(id=id)

    if not request.user.is_superuser:
        return redirect('projects_view', id=workflow.project.id)

    if request.method == "POST":
        form = forms.FlowForm(request.POST, instance=workflow)

        if form.is_valid():
            workflow = form.save(commit=False)
            workflow.save()

            # Create target link if none exists
            for server in form.cleaned_data['targets']:
                try:
                    target = models.Target.objects.get(server=server, release=workflow)
                except models.Target.DoesNotExist:
                    target = models.Target.objects.create(server=server, release=workflow)
                    target.save()

            # Delete old target links
            ids = [server.id for server in form.cleaned_data['targets']]
            targets = workflow.target_set.all()
            for target in targets:
                if target.server.id not in ids:
                    print "Deleting old target", target

            return redirect('projects_view', id=workflow.project.id)

    else:
        form = forms.FlowForm(instance=workflow)
        form.initial['targets'] = [t.server for t in workflow.target_set.all()]
        

    return render(request, 'flows/create_edit.html', {
        'form': form, 
        'workflow': workflow,
        'project': workflow.project,
        'projects': getProjects(request)
    })

@login_required
def release_delete(request, id):
    release = models.Release.objects.get(id=id)
    project_id = release.flow.project.id
    release.delete()

    return redirect('projects_view', id=project_id)

@login_required
def workflow_delete(request, id):
    flow = models.ReleaseFlow.objects.get(id=id)
    project_id = flow.project.id
    flow.delete()

    return redirect('projects_view', id=project_id)

@login_required
def workflow_push(request, flow, build):
    flow = models.ReleaseFlow.objects.get(id=flow)
    build = models.Build.objects.get(id=build)

    tasks.doRelease.delay(build, flow)

    project_id = flow.project.id
    return redirect('projects_view', id=project_id)

@login_required
def workflow_schedule(request, flow, build):
    flow = models.ReleaseFlow.objects.get(id=flow)
    build = models.Build.objects.get(id=build)

    if request.method == "POST":
        form = forms.ReleasePushForm(request.POST)
        if form.is_valid():
            release = form.cleaned_data

            schedule = release['scheduled'] + timedelta(hours=int(release['tz']))

            tasks.doRelease.delay(build, flow, scheduled=schedule)

            return redirect('projects_view', id=flow.project.id)
    else:
        form = forms.ReleasePushForm()

    return render(request, 'flows/schedule.html', {
        'projects': getProjects(request),
        'project': flow.project,
        'form': form,
        'flow': flow,
        'build': build
    })

@login_required
def build_view(request, id):
    build = models.Build.objects.get(id=id)

    d = {
        'projects': getProjects(request),
        'project': build.project
    }

    if (request.user.is_superuser) or (
        build.project in request.user.project_set.all()):
        d['build'] = build

    return render(request, 'projects/build_view.html', d)

@login_required
def projects_view(request, id):

    project = models.Project.objects.get(id=id)
    if (request.user.is_superuser) or (project in request.user.project_set.all()):
        builds = models.Build.objects.filter(project=project).order_by('-build_time')

        hook_uri = urlparse.urljoin(request.build_absolute_uri(), 
            reverse('api_build', kwargs={'hash':project.idhash}))

        flows = models.ReleaseFlow.objects.filter(project=project)
        releases = []
        for flow in flows:
            release_set = flow.release_set.all().order_by('-release_date')

            for release in release_set:
                releases.append(release)

        releases.sort(key=lambda r: r.release_date)

        d = {
            'project': project, 
            'hook_uri': hook_uri,
            'builds': builds,
            'releases': reversed(releases[-5:]),
            'projects': getProjects(request) 
        }
    else:
        d = {}

    return render(request, 'projects/view.html', d)

@login_required
def projects_delete(request, id):
    if not request.user.is_superuser:
        return redirect('home')

    models.Project.objects.get(id=id).delete()

    return redirect('home')

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

            prdStream = models.ReleaseStream.objects.filter(name__icontains='prod')
            qaStream = models.ReleaseStream.objects.filter(name__icontains='qa')

            if prdStream:
                # Create some default workflows
                prd = models.ReleaseFlow.objects.create(name="Production",
                    project=project,
                    stream=prdStream[0],
                    require_signoff=False,
                    quorum=0,
                    auto_release=False
                )
                prd.save()

            if qaStream:
                qa = models.ReleaseFlow.objects.create(name="QA",
                    project=project,
                    stream=qaStream[0],
                    require_signoff=False,
                    quorum=0,
                    auto_release=True
                )
                qa.save()

            return redirect('projects_view', id=project.id)

    else:
        form = forms.ProjectForm()

    return render(request, 'projects/create_edit.html', {
        'projects': getProjects(request),
        'form': form
    })

@login_required
def projects_edit(request, id):
    projects = getProjects(request)
    if not request.user.is_superuser:
        return redirect('home')

    project = models.Project.objects.get(id=id)
    if request.method == "POST":
        form = forms.ProjectForm(request.POST, instance=project)

        if form.is_valid():
            project = form.save(commit=False)
            project.save()
            form.save_m2m()

            return redirect('projects_view', id=id)

    else:
        form = forms.ProjectForm(instance=project)
    d = {
        'form': form, 
        'project': project,
        'projects': projects
    }

    return render(request, 'projects/create_edit.html', d)

@login_required
def help_index(request):
    return render(request, 'help/index.html')

@login_required
def build_cancel(request, id):
    build = models.Build.objects.get(id=id)
    if build.project in request.user.project_set.all():
        build.state = 3 
        build.save()
        revoke(build.task_id, terminate=True)

    return redirect('home')

@login_required
def projects_build(request, id):
    project = models.Project.objects.get(id=id)
    if project and (request.user.is_superuser or (
        project in request.user.project_set.all())):
        current_builds = models.Build.objects.filter(project=project, state=0)
        if current_builds:
            return redirect('build_view', id=current_builds[0].id)
        else:
            build = models.Build.objects.create(project=project, state=0)
            task = tasks.build.delay(build, project.github_url, project.branch)
            build.task_id = task.task_id
            build.save()
            return redirect('build_view', id=build.id)

    return redirect('home')

@login_required
def build_output(request, id):
    build = models.Build.objects.get(id=id)

    if (request.user.is_superuser) or (
        build.project in request.user.project_set.all()):
        d = {'state': build.state, 'log': build.log}
    else:
        d = {}

    return HttpResponse(json.dumps(d), content_type='application/json')

@login_required
def get_servers(request):
    d = [s.name for s in models.Server.objects.all()]

    return HttpResponse(json.dumps(d), content_type='application/json')

@login_required
def get_workflow_servers(request, id):
    workflow = models.ReleaseFlow.objects.get(id=id)

    d = [s.server.name for s in workflow.target_set.all()]

    return HttpResponse(json.dumps(d), content_type='application/json')

#############
# API methods

@csrf_exempt
def api_build(request, hash):
    project = models.Project.objects.get(idhash=hash)
    if project:
        if request.method == 'POST':
            if request.POST.get('payload'):
                r = json.loads(request.POST['payload'])
            else:
                r = json.loads(request.body)
            ref = r.get('ref', '')
            branch = ref.split('/',2)[-1]
            if branch != project.branch:
                return HttpResponse('{"result": "Request ignored"}',
                        content_type='application/json')

        current_builds = models.Build.objects.filter(project=project, state=0)
        if not current_builds:
            build = models.Build.objects.create(project=project, state=0)
            task = tasks.build.delay(build, project.github_url, project.branch)
            build.task_id = task.task_id
            build.save()

            return HttpResponse('{"result": "Building"}',
                    content_type='application/json')
        return HttpResponse('{"result": "Already building"}',
                content_type='application/json')

    return redirect('home')

@csrf_exempt
def api_sign(request, hash):
    signoff = models.ReleaseSignoff.objects.get(idhash=hash)
    signoff.signed = True
    signoff.save()

    if signoff.release.waiting:
        if signoff.release.check_signoff():
            tasks.runRelease.delay(signoff.release)

    return render(request, "sign.html", {
        'signoff': signoff
    })

@csrf_exempt
def api_checkin(request):
    # Server checkin endpoint
    if request.method == 'POST':
        if verifyHMAC(request, request.body):
            data = json.loads(request.body)
            try:
                server = models.Server.objects.get(name=data['hostname'])

            except models.Server.DoesNotExist:
                server = models.Server.objects.create(name=data['hostname'])

            server.save()

            return HttpResponse(json.dumps({}), 
                content_type='application/json')

    return HttpResponse(
            json.dumps({"error": "Not authorized"}), 
            content_type='application/json'
        )

@csrf_exempt
def api_enc(request, server):
    # Puppet ENC
    if verifyHMAC(request):
        # Build our ENC dict
        try:
            server = models.Server.objects.get(name=server)
        except:
            server = None

        if server:
            releases = [target.release for target in server.target_set.all()]

            cdict = {}
            for release in releases:
                for manifest in release.servermanifest_set.all():
                    key = manifest.module.key
                    value = json.loads(manifest.value)

                    if isinstance(value, list):
                        if key in cdict:
                            cdict[key].extend(value)
                        else:
                            cdict[key] = value

                    if isinstance(value, dict):
                        for k, v in value.items():
                            if key in cdict:
                                cdict[key][k] = v
                            else:
                                cdict[key] = {k: v}

            node = {
                'classes':{
                    'firewall':{},
                    'sideloader':{}
                },
                'parameters': cdict
            }
        else:
            node = {}

        print node

        return HttpResponse(yaml.dump(node),
            content_type='application/yaml')

    return HttpResponse(
            json.dumps({"error": "Not authorized"}), 
            content_type='application/json'
        )

