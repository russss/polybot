[![PyPI version](https://badge.fury.io/py/polybot.svg)](https://badge.fury.io/py/polybot)

Polybot is a framework for making social media bots for multiple
networks in Python 3.

It currently only supports post-only bots.

## Features

* Automatically post to Twitter, Mastodon, Bluesky.
* A friendly setup interface to handle the OAuth hassle for you.
* Automatic state persistence - just put your state in the `self.state`
  dict and it'll get saved/restored across runs.

## Example

```python
from polybot import Bot

class HelloWorldBot(Bot):
  def main(self):
    self.post("Hello World")

HelloWorldBot('helloworldbot').run()
```

To configure the accounts the bot uses, just run:

    ./helloworldbot.py --setup

You'll be guided through authenticating and a config file will be
automatically created.

Use the `--profile [name]` to save and use a specific state/config.

By default, the bot will run in development mode, which avoids actually
posting to networks. To run in live mode, pass the `--live` flag.

## Bots which use polybot

* [@dscovr_epic](https://twitter.com/dscovr_epic) / [@dscovr_epic@botsin.space](https://botsin.space/@dscovr_epic)
* [@dsn_status](https://twitter.com/dsn_status) / [@dsn_status@botsin.space](https://botsin.space/@dsn_status)
* [@insight_images@botsin.space](https://botsin.space/@insight_images) (Not on Twitter)
* [Matthew's bots](https://github.com/dracos/scheduler)
