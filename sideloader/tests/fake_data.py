from sideloader.tests.utils import datetime_utc


RELEASESTREAM_QA = {
    'id': 1,
    'name': 'QA',
    'push_command': "echo 'Pushing to QA: %s'",
}

RELEASESTREAM_PROD = {
    'id': 2,
    'name': 'PROD',
    'push_command': "echo 'Pushing to PROD: %s'",
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
    'build_time': datetime_utc(2016, 4, 1, 0, 0, 0),
    'task_id': '1',
    'log': '',
    'project_id': 1,
    'state': 0,
    'build_file': '',
}

RELEASE_1 = {
    'id': 1,
    'flow_id': 1,
    'build_id': 1,
    'waiting': True,
    'scheduled': None,
    'release_date': datetime_utc(2016, 4, 1, 1, 0, 0),
    'lock': False,
}

WEBHOOK_QA_1 = {
    'id': 1,
    'flow_id': RELEASEFLOW_QA['id'],
    'description': 'QA webhook',
    'url': 'http://example.com/hook1/token',
    'method': 'GET',
    'content_type': 'application/json',
    'payload': '',
    'after_id': None,
    'last_response': '',
}

WEBHOOK_QA_2 = {
    'id': 2,
    'flow_id': RELEASEFLOW_QA['id'],
    'description': 'Another QA webhook',
    'url': 'http://example.com/hook2/token',
    'method': 'GET',
    'content_type': 'application/json',
    'payload': '',
    'after_id': None,
    'last_response': '',
}
