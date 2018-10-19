# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import pytest

import pytest_twisted

from twistedcelery import TwistedCelery


def test_config(celery_app):
    """Test tasks using just Celery."""
    result = celery_app.send_task('tests.tasks.mul', args=(4, 4))

    assert result.get() == 16


@pytest_twisted.inlineCallbacks
def test_success(celery_app):
    """Test sending tasks via Twisted."""
    tx_app = TwistedCelery(celery_app)

    result = yield tx_app.send_task('tests.tasks.mul', args=(4, 4))

    assert result == 16


@pytest_twisted.inlineCallbacks
def test_failure(celery_app):
    """Test sending tasks via Twisted."""
    tx_app = TwistedCelery(celery_app)

    with pytest.raises(ZeroDivisionError):
        yield tx_app.send_task('tests.tasks.div', args=(1, 0))
