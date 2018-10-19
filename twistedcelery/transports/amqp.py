import os

import pika
from pika import exceptions
from pika.adapters.twisted_connection import TwistedProtocolConnection

from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientCreator


class AmqpBackend(object):
    """AMQP Backend."""

    def __init__(self, tx_app):
        self.tx_app = tx_app
        # The Celery app.
        self.app = tx_app.app

        self._protocol = None
        self._connecting = False
        self._connection_deferred = defer.Deferred()

    @defer.inlineCallbacks
    def ensure_connected(self):
        """Ensure that the producer is connected (and the consumer is ready to receive results)."""
        if self._connecting:
            yield self._connection_deferred
            return

        self._connecting = True
        self._connection_deferred = defer.Deferred()

        # Initialize pika.
        parameters = pika.connection.URLParameters(self.app.conf.broker_url)
        if parameters.virtual_host == '':
            parameters.virtual_host = '/'
        creator = ClientCreator(reactor, TwistedProtocolConnection, parameters)

        # Connect to the broker.
        self._protocol = yield creator.connectTCP(parameters.host, parameters.port)
        yield self._protocol.ready

        # Ensure there's a channel open.
        self._channel = yield self._protocol.channel(1)

        # Declare the result queue. See celery.backends.rpc.binding
        yield self._channel.queue_declare(
            queue=self.app.backend.binding.name,
            durable=False,
            exclusive=False,
            auto_delete=True,
            # Convert to milliseconds.
            arguments={
                'x-expires': int(self.app.backend.binding.expires * 1000),
            })

        # Note: It is illegal to declare exchanges or bindings on the
        # default queue.

        # Consume from the results queue. The consumer tag is used to match
        # responses back up with the proper (in-memory) queue, we only have
        # one consumer on a results queue, so just re-use the queue name.
        queue, consumer_tag = yield self._channel.basic_consume(
            queue=self.app.backend.binding.name,
            no_ack=True,
            consumer_tag=self.app.backend.binding.name)

        # Continually read from this queue.
        def process_queue(result):
            self.process_result(result)
            queue.get().addCallback(process_queue)
        queue.get().addCallback(process_queue)

        self._connection_deferred.callback(True)

    def process_result(self, message):
        channel, method, properties, body = message
        self.tx_app.process_result(body)

    def prepare_message(self, body, priority=0,
                        content_type=None, content_encoding=None,
                        headers=None, properties=None):
        """Prepare message so that it can be sent using this transport."""
        # Inspired by kombu.transport.pyamqp.Channel.prepare_message.
        properties.update({
            'priority': priority,
            'content_type': content_type,
            'content_encoding': content_encoding,
            'headers': headers,
        })
        return body, properties

    def basic_publish(self, content, exchange, routing_key, mandatory, immediate):
        body, properties = content
        # Pass publishing to the underlying implementation.
        return self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.spec.BasicProperties(**properties),
            mandatory=mandatory,
            immediate=immediate)

    def disconnect(self):
        if self._protocol:
            # Disconnect politely.
            self._channel.close()
            self._protocol.transport.loseConnection()
