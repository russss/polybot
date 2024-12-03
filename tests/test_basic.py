from polybot import Bot


class BotTest(Bot):
    def main(self):
        pass


def test_init():
    # Very basic test to exercise the initialisation code
    bot = BotTest("test_bot")
    assert bot.name == "test_bot"
    bot.run()
