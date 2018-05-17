import logging.config
import os
import sys

from twisted.internet import defer, task

from txamqp.endpoint import AMQEndpoint
from txamqp.factory import AMQFactory

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
        'txamqp': {
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


@defer.inlineCallbacks
def _main(reactor):
    try:
        yield main(reactor)
    except Exception as e:
        print(e)




def later():
    print("LATER DUDE")


@defer.inlineCallbacks
def main(reactor):
    # Configure the factory with broker information.
    # TODO Wrap the Celery instance and pull information from there.
    broker_url = app.conf.broker_url.replace(':5672', '')
    endpoint = AMQEndpoint.from_uri(reactor, broker_url)
    endpoint._auth_mechanism = 'PLAIN'
    factory = AMQFactory(spec=os.path.join(os.path.dirname(__file__), "amqp0-9-1.stripped.xml"))

    # Connect to the broker.
    client = yield endpoint.connect(factory)

    # Ensure there's a channel open.
    channel = yield client.channel(1)
    yield channel.channel_open()

    # Create the Twisted Celery application.
    tx_app = txCelery(app)
    tx_app.channel = channel

    # Declare the result queue.
    # See celery.backends.rpc.binding
    yield channel.queue_declare(queue=app.backend.binding.name, durable=False, exclusive=False, auto_delete=True,
                                # Convert to milliseconds.
                                arguments={'x-expires': int(app.backend.binding.expires * 1000)})
    # Do not declare exchanges or bindings on the default queue.
    #yield channel.exchange_declare(exchange=app.backend.binding.exchange.name, type="direct", durable=True)

    #yield channel.queue_bind(queue=app.backend.binding.name,
    #                         exchange=app.backend.binding.exchange.name,
    #                         routing_key=app.backend.binding.routing_key)

    # Send the message.
    print("Sending task")
    result = tx_app.send_task('tasks.add', args=(2, 4))
    result = yield result
    print("Wait for result: %s" % result)

    # Consume from the results queue. The consumer tag is used to match
    # responses back up with the proper (in-memory) queue, we only have one
    # consumer on a results queue, so just re-use the queue name.
    yield channel.basic_consume(queue=app.backend.binding.name, no_ack=True, consumer_tag=app.backend.binding.name)
    queue = yield client.queue(app.backend.binding.name)

    while True:
        print("Getting result from ", queue)
        msg = yield queue.get()
        print('Received: {0} from channel #{1}'.format(msg.content.body, channel.id))
        if msg.content.body == "STOP":
            break

    # Wait a bit.
    yield task.deferLater(reactor, 10, later)

    # Disconnect politely.
    client.transport.loseConnection()


task.react(_main)
