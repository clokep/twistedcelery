import logging.config
import sys

from twisted.internet import defer, task

from twistedcelery import txCelery

from tasks import app


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


from twisted.python import log

observer = log.PythonLoggingObserver('temp.twisted')
observer.start()

# END LOGGING


def later():
    print("LATER DUDE")


@defer.inlineCallbacks
def main(reactor):
    # Create the Twisted Celery application.
    tx_app = txCelery(app)

    # Send the message.
    print("Sending task")
    result = tx_app.send_task('tasks.add', args=(2, 4))
    print("Result", result)
    result = yield result
    print("Wait for result", result)

    # Wait a bit.
    yield task.deferLater(reactor, 10, later)

    tx_app.disconnect()


task.react(main)
