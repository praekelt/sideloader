from datetime import datetime, timedelta, tzinfo


class UTC(tzinfo):
    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)

utc = UTC()


RELEASESTREAM_QA = {
    'id': 1,
    'name': 'QA',
    'push_command': 'push push push',
}

RELEASESTREAM_PROD = {
    'id': 2,
    'name': 'PROD',
    'push_command': 'push push push',
}

PROJECT_SIDELOADER = {
    'id': 1,
    'name': 'Test project',
    'github_url': 'https://github.com/praekelt/sideloader.git',
    'branch': 'develop',
    'deploy_file': '.deploy.yaml',
    'idhash': '6d8adfebec3011e59599b88d121fe884',
    'notifications': False,
    'slack_channel': '#mychan',
    'created_by_user_id': 1,
    'release_stream_id': 1,
    'build_script': 'scripts/test_build.sh',
    'package_name': 'test_package',
    'postinstall_script': 'scripts/test_post.sh',
    'package_manager': 'deb',
    'deploy_type': 'virtualenv',
}

RELEASEFLOW_QA = {
    'id': 1,
    'name': 'QA Flow',
    'project_id': 1,
    'stream_mode': 0,
    'stream_id': 1,
    'require_signoff': False,
    'signoff_list': '',
    'quorum': 0,
    'notify': False,
    'notify_list': '',
    'service_restart': True,
    'service_pre_stop': False,
    'puppet_run': True,
    'auto_release': True,
}

RELEASEFLOW_PROD = {
    'id': 2,
    'name': 'PROD Flow',
    'project_id': 1,
    'stream_mode': 0,
    'stream_id': 2,
    'require_signoff': False,
    'signoff_list': '',
    'quorum': 0,
    'notify': False,
    'notify_list': '',
    'service_restart': True,
    'service_pre_stop': False,
    'puppet_run': True,
    'auto_release': False,
}

BUILD_1 = {
    'id': 1,
    'build_time': datetime(2016, 4, 1, tzinfo=utc),
    'task_id': '1',
    'log': '',
    'project_id': 1,
    'state': 0,
    'build_file': '',
}
