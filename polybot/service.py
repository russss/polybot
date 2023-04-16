from io import BytesIO
import logging
import textwrap
import mimetypes
from typing import List, Type, Union  # noqa
from mastodon import Mastodon as MastodonClient
import tweepy
import requests


class PostError(Exception):
    """Raised when there was an error posting"""

    pass


class Service(object):
    name = None  # type: str
    ellipsis_length = 1
    max_length = None  # type: int
    max_length_image = None  # type: int

    def __init__(self, config, live: bool) -> None:
        self.log = logging.getLogger(__name__)
        self.config = config
        self.live = live

    def auth(self) -> None:
        raise NotImplementedError()

    def setup(self) -> bool:
        raise NotImplementedError()

    def longest_allowed(self, status: list, imagefile) -> str:
        max_len = self.max_length_image if imagefile else self.max_length
        picked = status[0]
        for s in sorted(status, key=len):
            if len(s) < max_len:
                picked = s
        return picked

    def post(
        self,
        status: Union[str, List[str]],
        wrap=False,
        imagefile=None,
        mime_type=None,
        lat: float = None,
        lon: float = None,
        in_reply_to_id=None,
    ):
        if self.live:
            if wrap:
                return self.do_wrapped(
                    status, imagefile, mime_type, lat, lon, in_reply_to_id
                )
            if isinstance(status, list):
                status = self.longest_allowed(status, imagefile)
            return self.do_post(status, imagefile, mime_type, lat, lon, in_reply_to_id)

    def do_post(
        self,
        status: str,
        imagefile=None,
        mime_type=None,
        lat: float = None,
        lon: float = None,
        in_reply_to_id=None,
    ) -> None:
        raise NotImplementedError()

    def do_wrapped(
        self,
        status,
        imagefile=None,
        mime_type=None,
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        max_len = self.max_length_image if imagefile else self.max_length
        if len(status) > max_len:
            wrapped = textwrap.wrap(status, max_len - self.ellipsis_length)
        else:
            wrapped = [status]
        first = True
        for line in wrapped:
            if first and len(wrapped) > 1:
                line = "%s\u2026" % line
            if not first:
                line = "\u2026%s" % line

            if imagefile and first:
                out = self.do_post(line, imagefile, mime_type, lat, lon, in_reply_to_id)
            else:
                out = self.do_post(
                    line, lat=lat, lon=lon, in_reply_to_id=in_reply_to_id
                )

            in_reply_to_id = out.id
            first = False


class Twitter(Service):
    name = "twitter"
    max_length = 280
    max_length_image = 280 - 25
    ellipsis_length = 2

    def auth(self):
        self.tweepy = tweepy.Client(
            consumer_key=self.config.get("twitter", "api_key"),
            consumer_secret=self.config.get("twitter", "api_secret"),
            access_token=self.config.get("twitter", "access_key"),
            access_token_secret=self.config.get("twitter", "access_secret"),
        )
        # API v1 is required to upload images.
        self.tweepy_v1 = tweepy.API(
            tweepy.OAuth1UserHandler(
                consumer_key=self.config.get("twitter", "api_key"),
                consumer_secret=self.config.get("twitter", "api_secret"),
                access_token=self.config.get("twitter", "access_key"),
                access_token_secret=self.config.get("twitter", "access_secret"),
            )
        )
        res = self.tweepy.get_me()
        self.log.info("Connected to Twitter as %s", res.data["username"])

    def setup(self):
        print(
            "You'll need a consumer token and secret from your twitter app configuration here."
        )
        api_key = input("Consumer key: ")
        api_secret = input("Consumer secret: ")
        access_token = input("Access token: ")
        access_token_secret = input("Access token secret: ")

        print("Checking everything works...")
        self.tweepy = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        res = self.tweepy.get_me()
        print("Authenticated as", res.data["username"])

        self.config.add_section("twitter")
        self.config.set("twitter", "api_key", api_key)
        self.config.set("twitter", "api_secret", api_secret)
        self.config.set("twitter", "access_key", access_token)
        self.config.set("twitter", "access_secret", access_token_secret)

        return True

    def do_post(
        self,
        status,
        imagefile=None,
        mime_type=None,
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        try:
            media_ids = []
            if imagefile:
                if mime_type:
                    ext = mimetypes.guess_extension(mime_type)
                    f = BytesIO(imagefile)
                    imagefile = "dummy" + ext
                else:
                    f = None
                media = self.tweepy_v1.media_upload(imagefile, file=f)
                media_ids.append(media.media_id)
            return self.tweepy.create_tweet(
                text=status,
                in_reply_to_tweet_id=in_reply_to_id,
                media_ids=media_ids,
            )
        except Exception as e:
            raise PostError(e)


class Mastodon(Service):
    name = "mastodon"
    max_length = 500
    max_length_image = 500

    def auth(self):
        base_url = self.config.get("mastodon", "base_url")
        self.mastodon = MastodonClient(
            client_id=self.config.get("mastodon", "client_id"),
            client_secret=self.config.get("mastodon", "client_secret"),
            access_token=self.config.get("mastodon", "access_token"),
            version_check_mode=self.config.get(
                "mastodon", "version_check_mode", fallback="none"
            ),
            api_base_url=base_url,
        )
        self.log.info("Connected to Mastodon %s", base_url)

    def get_server_software(self, hostname):
        res = requests.get(hostname + "/.well-known/nodeinfo")
        if res.status_code != 200:
            return None
        data = res.json()

        nodeinfo_url = None
        for link in data.get("links", []):
            if link.get("rel") == "http://nodeinfo.diaspora.software/ns/schema/2.0":
                nodeinfo_url = link.get("href")

        if not nodeinfo_url:
            return None

        res = requests.get(nodeinfo_url)
        if res.status_code != 200:
            return None

        data = res.json()
        return data.get("software", None)

    def setup(self):
        print()
        print(
            "First, we'll need the base URL of the Mastodon instance you want to connect to,"
        )
        print("e.g. https://mastodon.social or https://botsin.space")
        base_url = input("Base URL: ")

        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        software = self.get_server_software(base_url)

        actually_mastodon = False
        if not software:
            print(
                "Unable to determine server software using the nodeinfo endpoint. "
                "Make sure you got your URL right."
            )
            print("Assuming this isn't running stock Mastodon and continuing...")
        else:
            name = software.get("name")
            if name and name.lower() == "mastodon":
                actually_mastodon = True
            print(f"Detected server software: {name}")

        result = input("Do you already have an app registered on this server (y/N)? ")
        if result[0].lower() == "y":
            client_id = input("Client ID: ")
            client_secret = input("Client Secret: ")
        else:
            print("OK, we'll create an app first")
            app_name = input("App name: ")
            client_id, client_secret = MastodonClient.create_app(
                app_name, api_base_url=base_url
            )
            print("App successfully created.")

        print("Now we'll need to log in...")
        mastodon = MastodonClient(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url=base_url,
            version_check_mode="created" if actually_mastodon else "none",
        )

        req_url = mastodon.auth_request_url()
        print("Visit the following URL, log in, and copy the code it gave you:")
        print(req_url)
        print()
        code = input("Code: ")

        mastodon.log_in(code=code)
        print("Successfully authenticated.")

        self.config.add_section("mastodon")
        self.config.set("mastodon", "base_url", base_url)
        self.config.set("mastodon", "client_id", client_id)
        self.config.set("mastodon", "client_secret", client_secret)
        self.config.set("mastodon", "access_token", mastodon.access_token)
        self.config.set(
            "mastodon", "version_check_mode", "created" if actually_mastodon else "none"
        )

        return True

    def do_post(
        self,
        status,
        imagefile=None,
        mime_type=None,
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        try:
            if imagefile:
                if isinstance(imagefile, list):
                    media = []
                    for f in imagefile:
                        media.append(self.mastodon.media_post(f, mime_type=mime_type))
                else:
                    media = [self.mastodon.media_post(imagefile, mime_type=mime_type)]
            else:
                media = None

            return self.mastodon.status_post(
                status, in_reply_to_id=in_reply_to_id, media_ids=media
            )
        except Exception as e:
            # Mastodon.py exceptions are currently changing so catchall here for the moment
            raise PostError(e)


ALL_SERVICES = [Twitter, Mastodon]  # type: List[Type[Service]]
