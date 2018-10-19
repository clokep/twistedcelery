import pytest

from twistedcelery import TwistedCelery


@pytest.fixture(scope='session', params=[1, 2])
def celery_config(request):
    return {
        #'broker_url': 'memory://',
        #'result_backend': 'cache+memory://',
        'broker_url': 'amqp://',
        'result_backend': 'rpc://',
        # Test both protocol 1 and 2 via the parameterized fixture.
        'task_protocol': request.param,
    }


@pytest.fixture
def twisted_app(celery_app):
    """Return a TwistedCelery app instead of a Celery app."""
    return TwistedCelery(celery_app)
