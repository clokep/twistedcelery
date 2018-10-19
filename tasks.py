from __future__ import absolute_import, print_function, unicode_literals

from celery import Celery

app = Celery(broker='amqp://guest:guest@127.0.0.1:5672//', backend='rpc', include=['tasks'])

@app.task
def add(a, b):
    print('Adding {} + {} = {}'.format(a, b, a + b))
    return a + b


@app.task
def mul(a, b):
    print('Multiplying {} * {} = {}'.format(a, b, a * b))
    return a * b


@app.task
def div(a, b):
    print('Dividing {} / {} = {}'.format(a, b, a / b))
    return a / b


if __name__ == '__main__':
    app.worker_main()
