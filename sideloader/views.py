from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    if request.user.is_superuser:
        pass

    d = {'user': request.user}
    return render_to_response("index.html", d)
