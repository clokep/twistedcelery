# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import pytest

import pytest_twisted



def test_config(celery_app):
    """Test tasks using just Celery."""
    result = celery_app.send_task('tests.tasks.mul', args=(4, 4))

    assert result.get() == 16


@pytest_twisted.inlineCallbacks
def test_success(twisted_app):
    """Test sending tasks via Twisted."""
    result = yield twisted_app.send_task('tests.tasks.mul', args=(4, 4))

    assert result == 16


@pytest_twisted.inlineCallbacks
def test_failure(twisted_app):
    """Test sending tasks via Twisted that result in an error."""
    with pytest.raises(ZeroDivisionError):
        yield twisted_app.send_task('tests.tasks.div', args=(1, 0))
