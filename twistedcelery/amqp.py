import os

from txamqp.content import Content
from txamqp.endpoint import AMQEndpoint
from txamqp.factory import AMQFactory

from twisted.internet import defer, reactor


class AmqpBackend(object):
    """AMQP Backend."""

    def __init__(self, tx_app):
        self.tx_app = tx_app
        # The Celery app.
        self.app = tx_app.app

        # Configure the factory with broker information.
        broker_url = self.app.conf.broker_url.replace(':5672', '')
        self.endpoint = AMQEndpoint.from_uri(reactor, broker_url)
        self.endpoint._auth_mechanism = 'PLAIN'
        self.factory = AMQFactory(spec=os.path.join(os.path.dirname(__file__), "amqp0-9-1.stripped.xml"))

        self._connected = False

    @defer.inlineCallbacks
    def ensure_connected(self):
        """Ensure that the producer is connected (and the consumer is ready to receive results)."""
        if not self._connected:
            # Connect to the broker.
            self.client = yield self.endpoint.connect(self.factory)

            # Ensure there's a channel open.
            self.channel = yield self.client.channel(1)
            yield self.channel.channel_open()

            # Declare the result queue. See celery.backends.rpc.binding
            yield self.channel.queue_declare(
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
            # responses back up with the proper (in-memory) queue, we only have one
            # consumer on a results queue, so just re-use the queue name.
            yield self.channel.basic_consume(
                queue=self.app.backend.binding.name,
                no_ack=True,
                consumer_tag=self.app.backend.binding.name)
            queue = yield self.client.queue(self.app.backend.binding.name)

            queue.get().addCallback(self.got_result)

            self._connected = True

    def got_result(self, message):
        self.tx_app.got_result(message.content.body)

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
        return Content(body, properties=properties)

    def basic_publish(self, content, exchange, routing_key, mandatory, immediate):
        # Pass publishing to the underlying implementation.
        return self.channel.basic_publish(content=content, exchange=exchange, routing_key=routing_key, mandatory=mandatory, immediate=immediate)

    def disconnect(self):
        if self._connected:
            # Disconnect politely.
            self.client.transport.loseConnection()
