import configparser
import pickle
import logging
import argparse
import signal
import sys
from typing import List, Union, Optional, Any
from .service import Service, PostError, ALL_SERVICES
from .image import Image


class Bot(object):
    path = ""

    def __init__(self, name: str) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
        )
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            "--live",
            action="store_true",
            help="Actually post updates. Without this flag, runs in dev mode.",
        )
        self.parser.add_argument(
            "--setup", action="store_true", help="Configure accounts"
        )
        self.parser.add_argument("--profile", default="", help="Choose profile")
        self.parser.add_argument(
            "--loglevel",
            default="INFO",
            help="Set logging level",
            choices=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
        )

        # Set log levels for common chatty packages
        for package in ["requests", "tweepy", "httpx"]:
            logging.getLogger(package).setLevel(logging.WARN)

        self.log = logging.getLogger(__name__)

        self.name = name
        self.services: List[Service] = []
        self.state: Any = {}

    def run(self) -> None:
        self.args = self.parser.parse_args()
        logging.getLogger("root").setLevel(self.args.loglevel)
        self.log.info("Polybot starting...")

        profile = ""
        if len(self.args.profile):
            profile = "-%s" % self.args.profile
        self.config_path = "%s%s%s.conf" % (self.path, self.name, profile)
        self.state_path = "%s%s%s.state" % (self.path, self.name, profile)
        self.read_config()

        if self.args.setup:
            try:
                self.setup()
            except KeyboardInterrupt:
                pass
            return

        if not self.args.live:
            self.log.warning(
                "Running in test mode - not posting updates. Pass --live to run in live mode."
            )

        for Svc in ALL_SERVICES:
            if Svc.name in self.config:
                svc = Svc(self.config, self.args.live)
                svc.auth()
                self.services.append(svc)

        if len(self.services) == 0:
            self.log.warning("No services to post to. Use --setup to configure some!")
            if self.args.live:
                return

        signal.signal(signal.SIGTERM, self.signal)
        signal.signal(signal.SIGINT, self.signal)
        signal.signal(signal.SIGHUP, lambda _signum, _frame: self.save_state())

        self.load_state()
        self.log.info("Running")
        try:
            self.main()
        finally:
            self.save_state()
            self.log.info("Shut down")

    def signal(self, signum, _frame) -> None:
        self.save_state()
        self.log.info("Shut down on signal %s", signum)
        sys.exit(0)

    def setup(self) -> None:
        print("Polybot setup")
        print("=" * 80)
        for Svc in ALL_SERVICES:
            if Svc.name not in self.config:
                result = input("Configure %s (y/n)? " % Svc.name)
                if result[0] == "y":
                    if Svc(self.config, False).setup():
                        print("Configuring %s succeeded, writing config" % Svc.name)
                        self.write_config()
                    else:
                        print("Configuring %s failed." % Svc.name)
                else:
                    print("OK, skipping.")
            else:
                print("Service %s is already configured" % Svc.name)
            print("-" * 80)
        print(
            "Setup complete. To reconfigure, remove the service details from %s"
            % self.config_path
        )

    def main(self) -> None:
        raise NotImplementedError()

    def load_state(self) -> None:
        try:
            with open(self.state_path, "rb") as f:
                self.state = pickle.load(f)
        except IOError:
            self.log.info("No state file found")

    def save_state(self) -> None:
        if len(self.state) != 0:
            self.log.info("Saving state...")
            with open(self.state_path, "wb") as f:
                pickle.dump(self.state, f, pickle.HIGHEST_PROTOCOL)

    def post(
        self,
        status: Union[str, List[str]],
        wrap: bool = False,
        images: List[Image] = [],
        in_reply_to_id=None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> dict:
        """Publish a post to all configured services.

        If a service fails to post, the error is logged and the post is still sent to the
        remaining services.

        Arguments:
            status: The status text to post (required). It can be a list of strings, in which
                        case the longest string allowed by each service will be used.
            wrap: Whether to wrap the text into multiple posts.
            images: A list of Image objects to attach to the post.
            in_reply_to_id: A dictionary of service names to status IDs to reply to.
            lat: Latitude to attach to the post. (Twitter only)
            lon: Longitude to attach to the post. (Twitter only)
        """
        if isinstance(status, list):
            if wrap:
                raise ValueError("Cannot mix wrap and status list")
            if not len(status):
                raise ValueError("Cannot supply an empty list")

        if not isinstance(images, List) or not all(
            isinstance(i, Image) for i in images
        ):
            raise ValueError("The images argument must be a list of Image objects")

        self.log.info("> %s", status)
        if images:
            self.log.info("Images: %s", images)

        out = {}
        for service in self.services:
            try:
                if in_reply_to_id:
                    in_reply_to_id = in_reply_to_id[service.name]
                out[service.name] = service.post(
                    status, wrap, images, lat, lon, in_reply_to_id
                )
            except PostError:
                self.log.exception("Error posting to %s", service)
        return out

    def read_config(self) -> None:
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

    def write_config(self) -> None:
        with open(self.config_path, "w") as fp:
            self.config.write(fp)
