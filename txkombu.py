from kombu import transport
from kombu.five import items
from kombu.transport import base
from kombu.transport.pyamqp import DEFAULT_PORT, DEFAULT_SSL_PORT

from twisted.internet import reactor

from txamqp.endpoint import AMQEndpoint
from txamqp.factory import AMQFactory
from txamqp.content import Content

transport.TRANSPORT_ALIASES.update({
    'txamqp': 'txkombu:Transport',
})


class Transport(base.Transport):
    """AMQP Transport using Twisted."""

    default_port = DEFAULT_PORT
    default_ssl_port = DEFAULT_SSL_PORT

    def establish_connection(self):
        """Establish connection to the AMQP broker."""
        conninfo = self.client
        for name, default_value in items(self.default_connection_params):
            if not getattr(conninfo, name, None):
                setattr(conninfo, name, default_value)
        if conninfo.hostname == 'localhost':
            conninfo.hostname = '127.0.0.1'

        # This expects the host and port separately.
        try:
            host, port = conninfo.host.split(':')
        except ValueError:
            port = 5672

        # TODO SSL
        endpoint = AMQEndpoint(
            reactor=reactor,
            host=host,
            port=port,
            username=conninfo.userid,
            password=conninfo.password,
            vhost=conninfo.virtual_host,
            auth_mechanism=conninfo.login_method,
            heartbeat=conninfo.heartbeat,
            timeout=conninfo.connect_timeout)

        # TODO
        endpoint._auth_mechanism = 'PLAIN'

        factory = AMQFactory(spec=os.path.join(os.path.dirname(__file__), "amqp0-9-1.stripped.xml"))

        client = yield endpoint.connect(factory)

        conn = self.Connection(**opts)
        conn.client = self.client
        conn.connect()
        return conn

    @property
    def default_connection_params(self):
        return {
            'userid': 'guest',
            'password': 'guest',
            'port': (self.default_ssl_port if self.client.ssl
                     else self.default_port),
            'hostname': 'localhost',
            'login_method': 'AMQPLAIN',
        }
