# -*- coding: utf-8 -*-
from django.conf import settings
from ws4redis.redis_store import RedisStore, SELF


class RedisSubscriber(RedisStore):
    """
    Subscriber class, used by the websocket code to listen for subscribed channels
    """
    subscription_channels = ['subscribe-session', 'subscribe-group', 'subscribe-user', 'subscribe-broadcast']
    publish_channels = ['publish-session', 'publish-group', 'publish-user', 'publish-broadcast']

    def __init__(self, connection):
        self._subscription = None
        super(RedisSubscriber, self).__init__(connection)

    def get_online_subscriber_key(self, facility):
        prefix      = self.get_prefix()
        return '{prefix}online_subscribers:{facility}'.format(prefix=prefix, facility=facility)

    def user_connect(self, request):
        if not request.session:
            return

        user_id     = request.session.get('_auth_user_id')
        if not user_id:
            return

        facility    = self.get_facility(request)
        key         = self.get_online_subscriber_key(facility)
        self._connection.sadd(key, user_id)

    def user_disconnect(self, request):
        if not request.session:
            return

        user_id     = request.session.get('_auth_user_id')
        if not user_id:
            return

        facility    = self.get_facility(request)
        key         = self.get_online_subscriber_key(facility)
        self._connection.srem(key, user_id)

    def get_online_users_from_facility(self, facility):
        key = self.get_online_subscriber_key(facility)
        return self._connection.smembers(key)

    def parse_response(self):
        """
        Parse a message response sent by the Redis datastore on a subscribed channel.
        """
        return self._subscription.parse_response()

    def get_facility(self, request):
        return request.path_info.replace(settings.WEBSOCKET_URL, '', 1)

    def set_pubsub_channels(self, request, channels):
        """
        Initialize the channels used for publishing and subscribing messages through the message queue.
        """
        facility = self.get_facility(request)

        # initialize publishers
        audience = {
            'users': 'publish-user' in channels and [SELF] or [],
            'groups': 'publish-group' in channels and [SELF] or [],
            'sessions': 'publish-session' in channels and [SELF] or [],
            'broadcast': 'publish-broadcast' in channels,
        }
        self._publishers = set()
        for key in self._get_message_channels(request=request, facility=facility, **audience):
            self._publishers.add(key)

        # initialize subscribers
        audience = {
            'users': 'subscribe-user' in channels and [SELF] or [],
            'groups': 'subscribe-group' in channels and [SELF] or [],
            'sessions': 'subscribe-session' in channels and [SELF] or [],
            'broadcast': 'subscribe-broadcast' in channels,
        }
        self._subscription = self._connection.pubsub()
        for key in self._get_message_channels(request=request, facility=facility, **audience):
            self._subscription.subscribe(key)

    def send_persited_messages(self, websocket):
        """
        This method is called immediately after a websocket is openend by the client, so that
        persisted messages can be sent back to the client upon connection.
        """
        return
        for channel in self._subscription.channels:
            message = self._connection.get(channel)
            if message:
                websocket.send(message)

    def get_file_descriptor(self):
        """
        Returns the file descriptor used for passing to the select call when listening
        on the message queue.
        """
        return self._subscription.connection and self._subscription.connection._sock.fileno()
