from __future__ import absolute_import, print_function, unicode_literals

from celery import shared_task


@shared_task
def add(a, b):
    print('Adding {} + {} = {}'.format(a, b, a + b))
    return a + b


@shared_task
def mul(a, b):
    print('Multiplying {} * {} = {}'.format(a, b, a * b))
    return a * b


@shared_task
def div(a, b):
    print('Dividing {} / {} = {}'.format(a, b, a / b))
    return a / b
