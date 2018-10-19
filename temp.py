import logging.config
import sys

from celery import Celery

from twisted.internet import defer, task
from twisted.python import log

from twistedcelery import TwistedCelery

app = Celery(broker='amqp://guest:guest@127.0.0.1:5672//', backend='rpc', include=['tests.tasks'])


# SET UP LOGGING

# Configure the logger.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s %(message)s'
        },
    },
    'handlers': {
        'normal': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'stream': sys.stdout,
        },
    },
    'loggers': {
        'temp': {
            'handlers': ['normal'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'twistedcelery': {
            'handlers': ['normal'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'pika': {
            'handlers': ['normal'],
            'propagate': True,
            'level': 'DEBUG',
        },
    },
}

logging.config.dictConfig(LOGGING)


observer = log.PythonLoggingObserver('temp.twisted')
observer.start()

# END LOGGING


@defer.inlineCallbacks
def main(reactor):
    # Create the Twisted Celery application.
    tx_app = TwistedCelery(app)

    # result = yield tx_app.send_task('tasks.div', args=(2, 0))

    # Send the message.
    print("Sending task(s)")
    result = tx_app.send_task('tests.tasks.add', args=(2, 4))
    result2 = tx_app.send_task('tests.tasks.add', args=(4, 4))
    result = yield result
    result2 = yield result2
    print("Got results: ", result, result2)

    yield task.deferLater(reactor, 3, lambda: True)

    result = yield tx_app.send_task('tests.tasks.div', args=(2, 2))
    print("Got result: ", result)
    result = yield tx_app.send_task('tests.tasks.div', args=(2, 0))

    tx_app.disconnect()


#result = app.send_task('tasks.div', args=(2, 0))
#result.get()

if __name__ == '__main__':
    task.react(main)
