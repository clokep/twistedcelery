from __future__ import absolute_import, print_function, unicode_literals

from kombu import Connection, Exchange, Queue
from kombu import transport

import txkombu


def main(reactor):
    media_exchange = Exchange('media', 'direct', durable=True)
    video_queue = Queue('video', exchange=media_exchange, routing_key='video')

    def process_media(body, message):
        print("Processing:", body)
        message.ack()

    # connections
    with Connection('txamqp://strongarm:guest@10.10.6.81:5672//') as conn:

        # produce
        producer = conn.Producer(serializer='json')
        producer.publish({'name': '/tmp/lolcat1.avi', 'size': 1301013},
                          exchange=media_exchange, routing_key='video',
                          declare=[video_queue])

        # consume
        #with conn.Consumer(video_queue, callbacks=[process_media]) as consumer:
        #    # Process messages and handle events on all channels
        #    while True:
        #        conn.drain_events()


if __name__ == '__main__':
    main(None)
