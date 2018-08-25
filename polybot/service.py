from io import BytesIO
import logging
import mimetypes
from typing import List, Type  # noqa
from mastodon import Mastodon as MastodonClient
import tweepy
from tweepy.error import TweepError


class PostError(Exception):
    """ Raised when there was an error posting """
    pass


class Service(object):
    name = None  # type: str

    def __init__(self, config, live: bool) -> None:
        self.log = logging.getLogger(__name__)
        self.config = config
        self.live = live

    def auth(self) -> None:
        raise NotImplementedError()

    def setup(self) -> bool:
        raise NotImplementedError()

    def post(self, status: str,
             imagefile=None,
             mime_type=None,
             lat: float=None,
             lon: float=None) -> None:
        if self.live:
            self.do_post(status, imagefile, mime_type, lat, lon)

    def do_post(self,
                status: str,
                imagefile=None,
                mime_type=None,
                lat: float =None,
                lon: float =None) -> None:
        raise NotImplementedError()


class Twitter(Service):
    name = 'twitter'

    def auth(self):
        auth = tweepy.OAuthHandler(self.config.get('twitter', 'api_key'),
                                   self.config.get('twitter', 'api_secret'))
        auth.set_access_token(self.config.get('twitter', 'access_key'),
                              self.config.get('twitter', 'access_secret'))
        self.tweepy = tweepy.API(auth)
        me = self.tweepy.me()
        self.log.info("Connected to Twitter as %s", me.screen_name)

    def setup(self):
        print("You'll need a consumer token and secret from your twitter app configuration here.")
        api_key = input("Consumer token: ")
        api_secret = input("Consumer secret: ")
        auth = tweepy.OAuthHandler(api_key, api_secret)
        try:
            redirect_url = auth.get_authorization_url()
        except tweepy.TweepError:
            print("Unable to fetch a request token! Check your consumer credentials")
            return False
        print("OK, now visit this URL and get the verifier from there: %s" % redirect_url)
        verifier = input("Verifier: ")
        try:
            auth.get_access_token(verifier)
        except tweepy.TweepError:
            print("Unable to fetch the access token! Verifier may not have been correct.")
            return False

        print("Checking everything works...")
        self.tweepy = tweepy.API(auth)
        print("Successfully authenticated as %s" % self.tweepy.me().screen_name)

        self.config.add_section('twitter')
        self.config.set('twitter', 'api_key', api_key)
        self.config.set('twitter', 'api_secret', api_secret)
        self.config.set('twitter', 'access_key', auth.access_token)
        self.config.set('twitter', 'access_secret', auth.access_token_secret)

        return True

    def do_post(self, status, imagefile=None, mime_type=None, lat=None, lon=None):
        try:
            if imagefile:
                if mime_type:
                    ext = mimetypes.guess_extension(mime_type)
                    f = BytesIO(imagefile)
                    imagefile = 'dummy' + ext
                else:
                    f = None
                self.tweepy.update_with_media(imagefile, status=status,
                                              lat=lat, long=lon, file=f)
            else:
                self.tweepy.update_status(status, lat=lat, long=lon)
        except TweepError as e:
            raise PostError(e)


class Mastodon(Service):
    name = 'mastodon'

    def auth(self):
        base_url = self.config.get('mastodon', 'base_url')
        self.mastodon = MastodonClient(client_id=self.config.get('mastodon', 'client_id'),
                                       client_secret=self.config.get('mastodon', 'client_secret'),
                                       access_token=self.config.get('mastodon', 'access_token'),
                                       api_base_url=base_url)
        self.log.info("Connected to Mastodon %s", base_url)

    def setup(self):
        print("First, we'll need the base URL of the Mastodon instance you want to connect to,")
        print("e.g. https://mastodon.social or https://botsin.space")
        base_url = input("Base URL: ")

        result = input("Do you already have a Mastodon app registered (y/n)? ")
        if result[0] == 'n':
            print("OK, we'll create an app first")
            app_name = input("App name: ")
            client_id, client_secret = MastodonClient.create_app(app_name, api_base_url=base_url)
            print("App successfully created.")
        else:
            client_id = input("Client ID: ")
            client_secret = input("Client Secret: ")

        print("Now we'll need your user credentials")
        mastodon = MastodonClient(client_id=client_id, client_secret=client_secret, api_base_url=base_url)
        email = input("Email address: ")
        password = input("Password: ")
        mastodon.log_in(email, password)
        print("Successfully authenticated to Mastodon")

        self.config.add_section('mastodon')
        self.config.set('mastodon', 'base_url', base_url)
        self.config.set('mastodon', 'client_id', client_id)
        self.config.set('mastodon', 'client_secret', client_secret)
        self.config.set('mastodon', 'access_token', mastodon.access_token)

        return True

    def do_post(self, status, imagefile=None, mime_type=None, lat=None, lon=None):
        try:
            if imagefile:
                media = [self.mastodon.media_post(imagefile, mime_type=mime_type)]
            else:
                media = None

            self.mastodon.status_post(status, media_ids=media)
        except Exception as e:
            # Mastodon.py exceptions are currently changing so catchall here for the moment
            raise PostError(e)


ALL_SERVICES = [Twitter, Mastodon]  # type: List[Type[Service]]
