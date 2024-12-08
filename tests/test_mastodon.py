import configparser

from polybot.service import Mastodon


def test_instance_info():
    """Test instance info fetching against some known entities."""
    config = configparser.ConfigParser()
    config.add_section("mastodon")
    config.set("mastodon", "base_url", "https://bot.country")

    service = Mastodon(config, "mastodon")
    service.update_instance_info()
    assert service.software == "gotosocial"
    assert service.max_length == 5000
    assert service.max_image_size == 5242880
    assert service.max_image_count == 6

    config.set("mastodon", "base_url", "https://mastodon.social")
    service = Mastodon(config, "mastodon")
    service.update_instance_info()
    assert service.software == "mastodon"
    assert service.max_length == 500
    assert service.max_image_size == 16777216
