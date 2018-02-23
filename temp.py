from __future__ import absolute_import, print_function, unicode_literals

import json
import os

from kombu.compression import compress
from kombu.utils.uuid import uuid
from kombu.serialization import dumps

from twisted.internet import protocol, defer, endpoints, task
from twisted.python import failure

from txamqp.endpoint import AMQEndpoint
from txamqp.factory import AMQFactory
from txamqp.content import Content

from tasks import app


@defer.inlineCallbacks
def _main(reactor):
    try:
        yield main(reactor)
    except Exception as e:
        print(e)


@defer.inlineCallbacks
def main(reactor):
    # Configure the factory with broker information.
    # TODO Wrap the Celery instance and pull information from there.
    broker_url = app.conf.broker_url.replace(':5672', '')
    endpoint = AMQEndpoint.from_uri(reactor, broker_url)
    print(endpoint._host, endpoint._port, endpoint._vhost, endpoint._auth_mechanism)
    endpoint._auth_mechanism = 'PLAIN'
    factory = AMQFactory(spec=os.path.join(os.path.dirname(__file__), "amqp0-9-1.stripped.xml"))

    # The "task call".
    task_name = 'tasks.add'
    task_args = (1, 2)
    task_kwargs = {}

    # Connect to the broker.
    client = yield endpoint.connect(factory)

    # Ensure there's a channel open.
    channel = yield client.channel(1)
    print(channel)
    yield channel.channel_open()

    # The AMQP instance of Celery.
    amqp = app.amqp

    # Generate the message
    # See celery.app.base.Celery.send_task.
    task_id = uuid()
    task_message = amqp.create_task_message(task_id, task_name, args=task_args, kwargs=task_kwargs)

    # Split the message into pieces.
    # See celery.app.amqp.AMQP.send_task_message
    headers, properties, body, sent_event = task_message

    # Serializer.
    rkey = app.conf.task_default_routing_key
    serializer = app.conf.task_serializer
    compressor = app.conf.result_compression

    # See kombu.messaging.Producer._prepare.
    content_type, content_encoding, body = dumps(body, serializer=serializer)
    if compressor:
        body, headers['compression'] = compress(body, compression)

    # Prepare the message for sending, e.g. like kombu.transport.pyamqp.Channel.prepare_message.
    properties.update({
        'priority': 0,  # XXX
        'content_type': content_type,
        'content_encoding': content_encoding,
        'application_headers': headers,
    })

    msg = Content(body, properties=properties)

    # XXX Handle how this gets passed into send_task_message.
    options = amqp.router.route({}, 'tasks.add')
    queue = options['queue']

    # Send the message.
    try:
        result = yield channel.basic_publish(exchange=queue.exchange.name, routing_key=queue.routing_key, content=msg)
    except Exception as e:
        print(e)

    print(result)

    # Disconnect politely.
    client.transport.loseConnection()


task.react(_main)
