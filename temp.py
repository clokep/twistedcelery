from __future__ import absolute_import, print_function, unicode_literals

import os
import warnings

from celery import signals
from celery.exceptions import AlwaysEagerIgnored

from kombu.common import Broadcast
from kombu.compression import compress
from kombu.entity import Exchange, Queue, maybe_delivery_mode
from kombu.five import string_t, text_t
from kombu.utils.uuid import uuid
from kombu.utils.functional import maybe_list
from kombu.serialization import dumps

from twisted.internet import defer, task

from txamqp.endpoint import AMQEndpoint
from txamqp.factory import AMQFactory
from txamqp.content import Content

from tasks import app


# SET UP LOGGING
import logging.config
import sys

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
        }
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


class txCelery(object):
    def __init__(self, app):
        self.app = app
        self.amqp = app.amqp
        self.conf = app.conf

    def send_task(self, name, args=None, kwargs=None, countdown=None,
                  eta=None, task_id=None, producer=None, connection=None,
                  router=None, result_cls=None, expires=None,
                  publisher=None, link=None, link_error=None,
                  add_to_parent=True, group_id=None, retries=0, chord=None,
                  reply_to=None, time_limit=None, soft_time_limit=None,
                  root_id=None, parent_id=None, route_name=None,
                  shadow=None, chain=None, task_type=None, **options):
        """Send task by name.

        Supports the same arguments as :meth:`@-Task.apply_async`.

        Arguments:
            name (str): Name of task to call (e.g., `"tasks.add"`).
            result_cls (~@AsyncResult): Specify custom result class.
        """
        # This is a copy of (the top of) celery.app.base.Celery.send_task
        parent = have_parent = None
        amqp = self.amqp
        task_id = task_id or uuid()
        producer = producer or publisher  # XXX compat
        router = router or amqp.router
        conf = self.conf
        if conf.task_always_eager:  # pragma: no cover
            warnings.warn(AlwaysEagerIgnored(
                'task_always_eager has no effect on send_task',
            ), stacklevel=2)
        options = router.route(
            options, route_name or name, args, kwargs, task_type)

        # if not root_id or not parent_id:
        #     parent = self.current_worker_task
        #     if parent:
        #         if not root_id:
        #             root_id = parent.request.root_id or parent.request.id
        #         if not parent_id:
        #             parent_id = parent.request.id

        message = amqp.create_task_message(
            task_id, name, args, kwargs, countdown, eta, group_id,
            expires, retries, chord,
            maybe_list(link), maybe_list(link_error),
            reply_to or self.app.oid, time_limit, soft_time_limit,
            self.conf.task_send_sent_event,
            root_id, parent_id, shadow, chain,
        )

        # if connection:
        #     producer = amqp.Producer(connection, auto_declare=False)
        # self.backend.on_task_call(P, task_id)
        self.send_task_message(name, message, **options)

        # result = (result_cls or self.AsyncResult)(task_id)
        result = defer.succeed(task_id)
        # if add_to_parent:
        #     if not have_parent:
        #         parent, have_parent = self.current_worker_task, True
        #     if parent:
        #         parent.add_trail(result)
        return result

    def send_task_message(self, name, message,
                          exchange=None, routing_key=None, queue=None,
                          event_dispatcher=None,
                          retry=None, retry_policy=None,
                          serializer=None, delivery_mode=None,
                          compression=None, declare=None,
                          headers=None, exchange_type=None, **kwargs):
        # This is copied (and modified) from celery.app.amqp.AMQP._create_task_sender.
        default_retry = self.app.conf.task_publish_retry
        default_policy = self.app.conf.task_publish_retry_policy
        default_delivery_mode = self.app.conf.task_default_delivery_mode
        default_queue = self.amqp.default_queue
        queues = self.amqp.queues
        send_before_publish = signals.before_task_publish.send
        before_receivers = signals.before_task_publish.receivers
        send_after_publish = signals.after_task_publish.send
        after_receivers = signals.after_task_publish.receivers

        send_task_sent = signals.task_sent.send   # XXX compat
        sent_receivers = signals.task_sent.receivers

        # XXX
        # default_evd = self._event_dispatcher
        default_exchange = self.amqp.default_exchange

        default_rkey = self.app.conf.task_default_routing_key
        default_serializer = self.app.conf.task_serializer
        default_compressor = self.app.conf.result_compression

        # This is copied from celery.app.amqp.AMQP.send_task_message.
        retry = default_retry if retry is None else retry
        headers2, properties, body, sent_event = message
        if headers:
            headers2.update(headers)
        if kwargs:
            properties.update(kwargs)

        qname = queue
        if queue is None and exchange is None:
            queue = default_queue
        if queue is not None:
            if isinstance(queue, string_t):
                qname, queue = queue, queues[queue]
            else:
                qname = queue.name

        if delivery_mode is None:
            try:
                delivery_mode = queue.exchange.delivery_mode
            except AttributeError:
                pass
            delivery_mode = delivery_mode or default_delivery_mode

        if exchange_type is None:
            try:
                exchange_type = queue.exchange.type
            except AttributeError:
                exchange_type = 'direct'

        # convert to anon-exchange, when exchange not set and direct ex.
        if (not exchange or not routing_key) and exchange_type == 'direct':
                exchange, routing_key = '', qname
        elif exchange is None:
            # not topic exchange, and exchange not undefined
            exchange = queue.exchange.name or default_exchange
            routing_key = routing_key or queue.routing_key or default_rkey
        if declare is None and queue and not isinstance(queue, Broadcast):
            declare = [queue]

        # merge default and custom policy
        retry = default_retry if retry is None else retry
        _rp = (dict(default_policy, **retry_policy) if retry_policy
               else default_policy)

        if before_receivers:
            send_before_publish(
                sender=name, body=body,
                exchange=exchange, routing_key=routing_key,
                declare=declare, headers=headers2,
                properties=properties, retry_policy=retry_policy,
            )
        ret = self.publish(
            body,
            exchange=exchange,
            routing_key=routing_key,
            serializer=serializer or default_serializer,
            compression=compression or default_compressor,
            retry=retry, retry_policy=_rp,
            delivery_mode=delivery_mode, declare=declare,
            headers=headers2,
            **properties
        )
        if after_receivers:
            send_after_publish(sender=name, body=body, headers=headers2,
                               exchange=exchange, routing_key=routing_key)
        if sent_receivers:  # XXX deprecated
            if isinstance(body, tuple):  # protocol version 2
                send_task_sent(
                    sender=name, task_id=headers2['id'], task=name,
                    args=body[0], kwargs=body[1],
                    eta=headers2['eta'], taskset=headers2['group'],
                )
            else:  # protocol version 1
                send_task_sent(
                    sender=name, task_id=body['id'], task=name,
                    args=body['args'], kwargs=body['kwargs'],
                    eta=body['eta'], taskset=body['taskset'],
                )
        # if sent_event:
        #     evd = event_dispatcher or default_evd
        #     exname = exchange
        #     if isinstance(exname, Exchange):
        #         exname = exname.name
        #     sent_event.update({
        #         'queue': qname,
        #         'exchange': exname,
        #         'routing_key': routing_key,
        #     })
        #     evd.publish('task-sent', sent_event,
        #                 producer, retry=retry, retry_policy=retry_policy)
        return ret

    def publish(self, body, routing_key=None, delivery_mode=None,
                mandatory=False, immediate=False, priority=0,
                content_type=None, content_encoding=None, serializer=None,
                headers=None, compression=None, exchange=None, retry=False,
                retry_policy=None, declare=None, expiration=None,
                **properties):
        """Publish message to the specified exchange.

        Arguments:
            body (Any): Message body.
            routing_key (str): Message routing key.
            delivery_mode (enum): See :attr:`delivery_mode`.
            mandatory (bool): Currently not supported.
            immediate (bool): Currently not supported.
            priority (int): Message priority. A number between 0 and 9.
            content_type (str): Content type. Default is auto-detect.
            content_encoding (str): Content encoding. Default is auto-detect.
            serializer (str): Serializer to use. Default is auto-detect.
            compression (str): Compression method to use.  Default is none.
            headers (Dict): Mapping of arbitrary headers to pass along
                with the message body.
            exchange (Exchange, str): Override the exchange.
                Note that this exchange must have been declared.
            declare (Sequence[EntityT]): Optional list of required entities
                that must have been declared before publishing the message.
                The entities will be declared using
                :func:`~kombu.common.maybe_declare`.
            retry (bool): Retry publishing, or declaring entities if the
                connection is lost.
            retry_policy (Dict): Retry configuration, this is the keywords
                supported by :meth:`~kombu.Connection.ensure`.
            expiration (float): A TTL in seconds can be specified per message.
                Default is no expiration.
            **properties (Any): Additional message properties, see AMQP spec.
        """
        # Copied from kombu.messaging.Producer.publish.
        _publish = self._publish

        declare = [] if declare is None else declare
        headers = {} if headers is None else headers
        retry_policy = {} if retry_policy is None else retry_policy
        # routing_key = self.routing_key if routing_key is None else routing_key
        # compression = self.compression if compression is None else compression

        # exchange_name, properties['delivery_mode'] = self._delivery_details(
        #     exchange or self.exchange, delivery_mode,
        # )
        exchange_name, properties['delivery-mode'] = self._delivery_details(
            exchange, delivery_mode,
        )

        if expiration is not None:
            properties['expiration'] = str(int(expiration * 1000))

        body, content_type, content_encoding = self._prepare(
            body, serializer, content_type, content_encoding,
            compression, headers)

        # if self.auto_declare and self.exchange.name:
        #     if self.exchange not in declare:
        #         # XXX declare should be a Set.
        #         declare.append(self.exchange)

        # if retry:
        #     _publish = self.connection.ensure(self, _publish, **retry_policy)
        return _publish(
            body, priority, content_type, content_encoding,
            headers, properties, routing_key, mandatory, immediate,
            exchange_name, declare,
        )

    def _delivery_details(self, exchange, delivery_mode=None,
                          maybe_delivery_mode=maybe_delivery_mode,
                          Exchange=Exchange):
        # Copied from kombu.messaging.Producer._delivery_details.
        if isinstance(exchange, Exchange):
            return exchange.name, maybe_delivery_mode(
                delivery_mode or exchange.delivery_mode,
            )
        # exchange is string, so inherit the delivery
        # mode of our default exchange.
        return exchange, maybe_delivery_mode(
            delivery_mode or self.exchange.delivery_mode,
        )

    def _prepare(self, body, serializer=None, content_type=None,
                 content_encoding=None, compression=None, headers=None):
        # Copied from kombu.messaging.Producer._prepare.

        # No content_type? Then we're serializing the data internally.
        if not content_type:
            serializer = serializer or self.serializer
            (content_type, content_encoding,
             body) = dumps(body, serializer=serializer)
        else:
            # If the programmer doesn't want us to serialize,
            # make sure content_encoding is set.
            if isinstance(body, text_t):
                if not content_encoding:
                    content_encoding = 'utf-8'
                body = body.encode(content_encoding)

            # If they passed in a string, we can't know anything
            # about it. So assume it's binary data.
            elif not content_encoding:
                content_encoding = 'binary'

        if compression:
            body, headers['compression'] = compress(body, compression)

        return body, content_type, content_encoding

    def _publish(self, body, priority, content_type, content_encoding,
                 headers, properties, routing_key, mandatory,
                 immediate, exchange, declare):
        # Copied from kombu.messaging.Producer._publish.
        channel = self.channel
        message = self.prepare_message(
            body, priority, content_type,
            content_encoding, headers, properties,
        )
        # if declare:
        #     maybe_declare = self.maybe_declare
        #     [maybe_declare(entity) for entity in declare]

        # handle autogenerated queue names for reply_to
        reply_to = properties.get('reply_to')
        if isinstance(reply_to, Queue):
            properties['reply-to'] = reply_to.name
        print(headers)
        return channel.basic_publish(
            content=message,
            exchange=exchange, routing_key=routing_key,
            mandatory=int(mandatory), immediate=int(immediate),
        )

    def prepare_message(self, body, priority=0,
                        content_type=None, content_encoding=None,
                        headers=None, properties=None):
        """Prepare message so that it can be sent using this transport."""
        # Inspired by kombu.transport.pyamqp.Channel.prepare_message.
        properties.update({
            'priority': priority,
            'content-type': content_type,
            'content-encoding': content_encoding,
            'headers': headers,
        })
        return Content(body, properties=properties)


def later():
    print("LATER DUDE")


@defer.inlineCallbacks
def main(reactor):
    # Configure the factory with broker information.
    # TODO Wrap the Celery instance and pull information from there.
    broker_url = app.conf.broker_url.replace(':5672', '')
    endpoint = AMQEndpoint.from_uri(reactor, broker_url)
    print(endpoint._host, endpoint._port, endpoint._vhost, endpoint._auth_mechanism)
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

    # Send the message.
    print("Sending task")
    result = tx_app.send_task('tasks.add', args=(42, 42424242))
    print("Got result: %s" % result)
    result = yield result
    print("Wait for result: %s" % result)

    # Wait a bit.
    yield task.deferLater(reactor, 10, later)

    # Disconnect politely.
    client.transport.loseConnection()


task.react(_main)
