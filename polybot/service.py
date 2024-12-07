from io import BytesIO
import logging
import textwrap
import mimetypes
from time import time
from typing import List, Union, Optional, Type
from atproto import Client, models  # type: ignore
from atproto_client.exceptions import RequestException  # type: ignore
from mastodon import Mastodon as MastodonClient  # type: ignore
from importlib.metadata import version
import httpx

from .image import Image

POLYBOT_VERSION = version("polybot")


class PostError(Exception):
    """Raised when there was an error posting"""

    pass


class Service(object):
    name = None  # type: str
    ellipsis_length = 1
    max_length = None  # type: int
    max_length_image = None  # type: int
    max_image_size: int = int(10e6)
    max_image_pixels: Optional[int] = None
    max_image_count: int = 4

    def __init__(self, config, live: bool) -> None:
        self.log = logging.getLogger(__name__)
        self.config = config
        self.live = live
        self.user_agent = (
            f"polybot/{POLYBOT_VERSION} (https://github.com/russss/polybot)"
        )

    def auth(self) -> None:
        raise NotImplementedError()

    def setup(self) -> bool:
        raise NotImplementedError()

    def longest_allowed(self, status: list, images: List[Image]) -> str:
        max_len = self.max_length_image if images else self.max_length
        picked = status[0]
        for s in sorted(status, key=len):
            if len(s) < max_len:
                picked = s
        return picked

    def post(
        self,
        status: Union[str, List[str]],
        wrap=False,
        images: List[Image] = [],
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        in_reply_to_id=None,
    ):
        images = [
            i.resize_to_target(self.max_image_size, self.max_image_pixels)
            for i in images[: self.max_image_count]
        ]
        if self.live:
            if wrap:
                return self.do_wrapped(status, images, lat, lon, in_reply_to_id)
            if isinstance(status, list):
                status = self.longest_allowed(status, images)
            return self.do_post(status, images, lat, lon, in_reply_to_id)

    def do_post(
        self,
        status: str,
        images: List[Image] = [],
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        in_reply_to_id=None,
    ):
        raise NotImplementedError()

    def do_wrapped(
        self,
        status,
        images: List[Image] = [],
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        max_len = self.max_length_image if images else self.max_length
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

            if images and first:
                out = self.do_post(line, images, lat, lon, in_reply_to_id)
            else:
                out = self.do_post(
                    line, lat=lat, lon=lon, in_reply_to_id=in_reply_to_id
                )

            if isinstance(out, models.com.atproto.repo.strong_ref.Main):
                if first:
                    in_reply_to_id = {"root": out, "parent": out}
                else:
                    in_reply_to_id["parent"] = out
            elif hasattr(out, "id"):
                in_reply_to_id = out.id
            else:
                in_reply_to_id = out.data["id"]
            first = False


class Twitter(Service):
    name = "twitter"
    max_length = 280
    max_length_image = 280 - 25
    ellipsis_length = 2
    max_image_size = int(5e6)

    def auth(self):
        import tweepy  # type: ignore

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
        import tweepy  # type: ignore

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
        images: List[Image] = [],
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        try:
            media_ids = []
            if images:
                for image in images:
                    if image.mime_type:
                        ext = mimetypes.guess_extension(image.mime_type)
                        if not ext:
                            self.log.warning(
                                "MIME type %s not recognized", image.mime_type
                            )
                            continue
                        filename = "dummy" + ext
                    else:
                        self.log.warning(
                            "Not uploading image with no MIME type to Twitter"
                        )
                        continue
                    media = self.tweepy_v1.media_upload(
                        filename, file=BytesIO(image.data)
                    )
                    media_ids.append(media.media_id)
            return self.tweepy.create_tweet(
                text=status,
                in_reply_to_tweet_id=in_reply_to_id,
                media_ids=media_ids if media_ids else None,
            )
        except Exception as e:
            raise PostError(e)


class Mastodon(Service):
    name = "mastodon"
    software = None
    max_length = 500
    max_length_image = 500
    max_image_size = int(16e6)

    def __init__(self, config, live: bool):
        super().__init__(config, live)
        self.http = httpx.Client(headers={"User-Agent": self.user_agent})

    def auth(self):
        self.update_instance_info()

        base_url = self.config.get("mastodon", "base_url")
        self.mastodon = MastodonClient(
            client_id=self.config.get("mastodon", "client_id"),
            client_secret=self.config.get("mastodon", "client_secret"),
            access_token=self.config.get("mastodon", "access_token"),
            version_check_mode=self.config.get(
                "mastodon", "version_check_mode", fallback="none"
            ),
            api_base_url=base_url,
            user_agent=self.user_agent,
        )
        self.log.info("Connected to %s at %s", self.software, base_url)
        self.log.info(
            "Max post length: %d chars, max image size: %d MB, max image pixels: %d",
            self.max_length,
            self.max_image_size / 1024 / 1024,
            self.max_image_pixels,
        )

    def fetch_endpoint(self, path):
        base_url = self.config.get("mastodon", "base_url")
        if base_url is None:
            return None
        res = self.http.get(base_url + path)
        if res.status_code != 200:
            return None
        return res.json()

    def get_node_software(self):
        data = self.fetch_endpoint("/.well-known/nodeinfo")
        if not data:
            return None

        nodeinfo_url = None
        for link in data.get("links", []):
            if link.get("rel") == "http://nodeinfo.diaspora.software/ns/schema/2.0":
                nodeinfo_url = link.get("href")

        if not nodeinfo_url:
            return None

        res = self.http.get(nodeinfo_url)
        if res.status_code != 200:
            return None

        data = res.json()
        return data.get("software", {}).get("name")

    def update_instance_info(self):
        """Fetch and save details about the instance we're connecting to, including software type
        and post size limits.
        """

        self.software = self.get_node_software()

        instance_info = self.fetch_endpoint("/api/v1/instance")
        if not instance_info:
            return

        try:
            image_size = int(
                instance_info["configuration"]["media_attachments"]["image_size_limit"]
            )
        except Exception:
            image_size = self.max_image_size

        try:
            image_pixels = int(
                instance_info["configuration"]["media_attachments"][
                    "image_matrix_limit"
                ]
            )
        except Exception:
            image_pixels = self.max_image_pixels

        try:
            max_length = int(
                instance_info["configuration"]["statuses"]["max_characters"]
            )
        except Exception:
            max_length = self.max_length

        try:
            max_image_count = int(
                instance_info["configuration"]["statuses"]["max_media_attachments"]
            )
        except Exception:
            max_image_count = self.max_image_count

        self.max_image_size = image_size
        self.max_length = max_length
        self.max_length_image = max_length
        self.max_image_pixels = image_pixels
        self.max_image_count = max_image_count

    def setup(self):
        print()
        print(
            "First, we'll need the base URL of the Mastodon instance you want to connect to,"
        )
        print("e.g. https://mastodon.social")
        base_url = input("Base URL: ")

        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        self.config.add_section("mastodon")
        self.config.set("mastodon", "base_url", base_url)
        self.update_instance_info()

        actually_mastodon = False
        if not self.software:
            print(
                "Unable to determine server software using the nodeinfo endpoint. "
                "Make sure you got your URL right."
            )
            print("Assuming this isn't running stock Mastodon and continuing...")
        else:
            if self.software.lower() == "mastodon":
                actually_mastodon = True
            print(f"Detected server software: {self.software}")

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
            user_agent=self.user_agent,
        )

        req_url = mastodon.auth_request_url()
        print("Visit the following URL, log in, and copy the code it gave you:")
        print(req_url)
        print()
        code = input("Code: ")

        mastodon.log_in(code=code)
        print("Successfully authenticated.")

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
        images: List[Image] = [],
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        try:
            if images:
                media = [
                    self.mastodon.media_post(
                        image.data,
                        mime_type=image.mime_type,
                        description=image.description,
                    )
                    for image in images
                ]
            else:
                media = None

            return self.mastodon.status_post(
                status, in_reply_to_id=in_reply_to_id, media_ids=media
            )
        except Exception as e:
            # Mastodon.py exceptions are currently changing so catchall here for the moment
            raise PostError(e)


class Bluesky(Service):
    name = "bluesky"
    max_length = 300
    max_length_image = 300
    # As of 2024-12-03 the maximum image size allowed on Bluesky is 1 metric megabyte.
    max_image_size = int(1e6)

    def __init__(self, config, live: bool):
        super().__init__(config, live)
        self.login_ratelimit_expiry = 0
        self.connected = False

    def auth(self):
        self.bluesky = Client()
        if self.login_ratelimit_expiry > time():
            self.log.warning(
                "Not connecting to Bluesky as login rate limit is still active. "
                "Will re-attempt connection in %d seconds.",
                self.login_ratelimit_expiry - time(),
            )
            return

        try:
            self.bluesky.login(
                self.config.get("bluesky", "email"),
                self.config.get("bluesky", "password"),
            )
        except RequestException as e:
            if e.response.status_code == 429:
                self.login_ratelimit_expiry = int(e.response.headers["ratelimit-reset"])
                self.log.warning(
                    "Rate-limited by Bluesky when connecting. "
                    "Will re-attempt connection in %d seconds.",
                    self.login_ratelimit_expiry - time(),
                )
                return
            raise

        self.connected = True
        self.log.info("Connected to Bluesky")

    def setup(self):
        print("We need your Bluesky email and password")
        email = input("Email: ")
        password = input("Password: ")
        self.config.add_section("bluesky")
        self.config.set("bluesky", "email", email)
        self.config.set("bluesky", "password", password)
        return True

    def do_post(
        self,
        status,
        images: List[Image] = [],
        lat=None,
        lon=None,
        in_reply_to_id=None,
    ):
        if not self.connected:
            self.auth()

        if not self.connected:
            self.log.warning("Skipping Bluesky post, not connected")
            return

        if in_reply_to_id:
            in_reply_to_id = models.AppBskyFeedPost.ReplyRef(
                parent=in_reply_to_id["parent"], root=in_reply_to_id["root"]
            )
        try:
            if len(images) > 0:
                resp = self.bluesky.send_images(
                    status,
                    [i.data for i in images],
                    [i.description for i in images],
                    self.bluesky.me.did,
                    in_reply_to_id,
                )
            else:
                resp = self.bluesky.send_post(
                    status, self.bluesky.me.did, in_reply_to_id
                )
            return models.create_strong_ref(resp)

        except Exception as e:
            raise PostError(e)


ALL_SERVICES: List[Type[Service]] = [Twitter, Mastodon, Bluesky]
