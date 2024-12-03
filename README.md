[![PyPI version](https://badge.fury.io/py/polybot.svg)](https://badge.fury.io/py/polybot)

# Polybot

Polybot is a simple framework for building robust social media bots for multiple networks in Python.

## Features

* Automatically post to X/Twitter, Mastodon, Bluesky.
* A friendly command-line setup interface to handle the authentication hassle for you.
* Automatic state persistence - just put your state in the `self.state`
  dict and it'll get saved/restored across runs.

X/Twitter support is no longer regularly tested as the authors no longer use it. Reliability can't
be guaranteed but pull requests are welcome.

## Limitations/Wishlist

* Polybot currently doesn't have support for receiving messages, so it's only useful for post-only
  bots.

## Getting started
Install Polybot [from PyPi](https://pypi.org/project/polybot/) using your package manager of choice.

```python
from polybot import Bot

class HelloWorldBot(Bot):
  def main(self):
    while True:
      self.post("Hello World")
      sleep(300)

HelloWorldBot('helloworldbot').run()
```

To configure the accounts the bot uses, just run:

    ./helloworldbot.py --setup

You'll be guided through authenticating and a config file will be automatically created.

Use the `--profile [name]` to save and use a specific state/config.

By default, the bot will run in development mode, where it doesn't actually post to services. To run
in live mode, pass the `--live` flag.

### Images

One or more images can be attached by creating an [`Image` object](./polybot/image.py), which can be
created from a path, a file object, or `bytes`.

```python
from polybot import Image

self.post("Hello World",
  images=[Image(path="/path/to/image", mime_type="image/png", description="Alt text")]
)
```

Images are automatically resized to below the maximum allowable size on each platform.

### Handling post length limitations

Services have differing post length limits, so a list of messages can be passed to the `post` method,
and Polybot will choose the longest message which is supported by each configured service.

```python
self.post(["This is a short message", "This is a much longer message......"])
```

Alternatively, the `wrap` argument can be used to split a message into multiple posts:

```python
self.post("Long message...", wrap=True)
```

## State management

Polybot provides a dictionary at `self.state` where your bot can store any data which needs to be
persisted, to avoid repeating posts.

The state dictionary is serialised to a file called `<bot_name>.state` in the local directory.
This automatically happens when the process is terminated, but you can also trigger this
by calling `self.save_state()`.

## Bots which use Polybot

* [@dscovr_epic](https://bot.country/@dscovr_epic)
* [Matthew's bots](https://github.com/dracos/scheduler)
