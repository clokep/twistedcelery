import pytest

from tasks import add, mul

@pytest.fixture()
def celery_enable_logging():
    return True


@pytest.fixture()
def celery_config():
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
    }


@pytest.fixture()
def celery_includes():
    return [
        'tasks',
    ]


def test_create_task(celery_app, celery_worker):
    celery_app.set_current()

    print(sorted(celery_app.tasks.keys()))
    assert mul(4, 4) == 16

    mul.delay(4, 4)

    #assert mul.delay(4, 4).get(timeout=10) == 16
