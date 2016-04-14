from django.contrib.auth.models import User
from django.test import TestCase
from django.core.urlresolvers import reverse

from sideloader.models import Project, ReleaseFlow, ReleaseStream


class TestIndex(TestCase):
    def test_auth_required(self):
        """
        We can't look at things if we're not logged in.
        """
        resp = self.client.get("/")
        self.assertRedirects(resp, "/accounts/login/?next=/")

    def test_logged_in(self):
        """
        We can look at things if we're logged in.
        """
        User.objects.create_user("me", "me@example.com", "p455w0rd")
        self.client.login(username="me", password="p455w0rd")
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        # We have no data, so all these will be empty.
        self.assertQuerysetEqual(resp.context["builds"], [])
        self.assertQuerysetEqual(resp.context["last_builds"], [])
        self.assertQuerysetEqual(resp.context["projects"], [])


class TestProject(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            "root", "root@localhost", "pass")

    def test_new_project_non_superuser(self):
        """
        We can't create a new project if we're not a superuser.
        """
        self.client.login(username="me", password="pass")
        resp = self.client.post(reverse("projects_create"))
        self.assertRedirects(resp, "/")

    def test_new_project(self):
        """
        We can create a new project.
        """
        self.client.login(username="root", password="pass")
        self.assertEqual(list(Project.objects.all()), [])
        resp = self.client.post(reverse("projects_create"), {
            "name": "My Project",
            "github_url": "foo.git",
            "branch": "develop",
            "deploy_type": "virtualenv",
            "package_manager": "deb",
        })
        [proj] = Project.objects.all()
        self.assertEqual(proj.name, "My Project")
        self.assertEqual(proj.github_url, "foo.git")
        self.assertEqual(proj.branch, "develop")
        self.assertRedirects(resp, reverse("projects_view", args=[proj.pk]))

    def test_new_project_default_flows(self):
        """
        When we create a new project, we get some default workflows.
        """
        prod_stream = ReleaseStream.objects.create(name="Production")
        qa_stream = ReleaseStream.objects.create(name="QA")
        self.client.login(username="root", password="pass")
        self.assertEqual(list(Project.objects.all()), [])
        self.assertEqual(list(ReleaseFlow.objects.all()), [])
        self.client.post(reverse("projects_create"), {
            "name": "My Project",
            "github_url": "foo.git",
            "branch": "develop",
            "deploy_type": "virtualenv",
            "package_manager": "deb",
        })
        [proj] = Project.objects.all()

        [prod_f, qa_f] = list(ReleaseFlow.objects.all().order_by("name"))
        self.assertEqual(prod_f.project, proj)
        self.assertEqual(prod_f.stream, prod_stream)
        self.assertEqual(qa_f.project, proj)
        self.assertEqual(qa_f.stream, qa_stream)


class TestReleaseFlow(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            "root", "root@localhost", "pass")
        self.prod_stream = ReleaseStream.objects.create(name="Production")
        self.qa_stream = ReleaseStream.objects.create(name="QA")
        self.proj = Project.objects.create(
            name="My Project", github_url="foo.git", branch="develop",
            created_by_user=self.root, idhash="seekrit")

    def test_new_flow_stream(self):
        """
        We can create a new stream-mode release flow for a project.
        """
        self.client.login(username="root", password="pass")
        self.assertEqual(list(ReleaseFlow.objects.all()), [])
        url = reverse("workflow_create", args=[self.proj.pk])
        resp = self.client.post(url, {
            "name": "My Flow",
            "stream_mode": 0,
        })
        [flow] = ReleaseFlow.objects.all()
        self.assertEqual(flow.name, "My Flow")
        self.assertEqual(flow.stream_mode, 0)
        self.assertRedirects(
            resp, reverse("projects_view", args=[self.proj.pk]))

    def test_new_flow_server(self):
        """
        We can create a new server-mode release flow for a project.
        """
        self.client.login(username="root", password="pass")
        self.assertEqual(list(ReleaseFlow.objects.all()), [])
        url = reverse("workflow_create", args=[self.proj.pk])
        resp = self.client.post(url, {
            "name": "My Flow",
            "stream_mode": 1,
        })
        [flow] = ReleaseFlow.objects.all()
        self.assertEqual(flow.name, "My Flow")
        self.assertEqual(flow.stream_mode, 1)
        self.assertRedirects(
            resp, reverse("projects_view", args=[self.proj.pk]))
