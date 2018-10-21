Twisted-Celery
##############

Twisted-Celery is a connector to call Celery tasks (and receive results) from an
application running with Twisted.

The Problem
===========

Twisted and Celery are both "asynchronous", but have dramatically different
use-cases. Twisted is an event-drive networking framework, but doesn't perform
well for long lived CPU-intensive tasks. Celery is a distributed task runner
that excels at short-lived CPU bound work.

Sometimes you want to run a task from Twisted...but this is harder than it
seems. You might think you can just import your Celery app and run the tasks,
but this causes synchronous I/O to happen in the middle of your Twisted process.
Another solution might be to do all Celery calls inside of a thread (by using
``deferToThread`` and friends), while this is better than doing I/O on the
reactor thread you'll quickly cause thread-pool starvation.

Luckily, there's another way...

The Solution
============

Twisted-Celery uses the internals of Celery to create Celery-compatible
messages, but then uses Twisted to do distributed I/O to communicate with your
configured Celery broker and backend. It does this while exposing a
``send_task`` API identical to Celery's. Additionally, when calling a task it
returns a native ``Deferred`` instead of an ``AsyncResult`` so you can write
Twisted-compatible code easily.

Supported Features
==================

Currently the only supported broker and backend are over AMQP. Support for AMQP
in Twisted is provided via `pika <https://pika.readthedocs.io>`_.

If you'd like to use a different backend or broker, please contribute!

How it Works
============

Twisted-Celery sits somewhere in-between the Celery and Kombu layers of a
traditional Celery application. This is because much of Celery is really
implemented inside of Kombu (e.g. the serialization and message creation
facilities), while some of the higher level constructs are from Celery.

Where possible, calls into Celery and Kombu are made. Unfortunately much of the
internals of those frameworks assume synchonrous code (e.g.
``ensure_connection`` blocks if a new connection needs to be opened). The
easiest way to implement this was to copy portions of code out of Celery and
Kombu in order to make them asynchronous.

Getting Started
===============

After creating a Celery application as normal, import the ``TwistedCelery``
class and use it to wrap your Celery app. Use the ``send_task`` method provided
on this class within Twisted. It returns a ``Deferred`` that resolves to the
result of the task call.

.. code-block:: python

    from twistedcelery import TwistedCelery

    from twisted.internet import defer, task

    from my_app import app

    @defer.inlineCallbacks
    def main(reactor):
        # Create the Twisted Celery application.
        tx_app = TwistedCelery(app)

        # Execute a task (and get the result).
        print("Sending task")
        result = yield tx_app.send_task('my_app.tasks.some_task')
        print("Got result: ", result)

        tx_app.disconnect()

    if __name__ == '__main__':
        task.react(main)
