from django.contrib.auth.models import User
from django.test import TestCase


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
