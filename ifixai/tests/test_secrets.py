import pytest
from ifixai.providers.secrets import (
    SecretLeakError,
    assert_no_secrets,
    looks_like_secret,
    scrub_secrets,
)


class TestLooksLikeSecret:
    def test_openai_key(self):
        assert looks_like_secret("sk-abcdefghijklmnopqrstuvwxyz123456")

    def test_anthropic_key(self):
        assert looks_like_secret("sk-ant-api03-abcdefghijklmnopqrstuvwxyz")

    def test_openrouter_key(self):
        assert looks_like_secret("sk-or-v1-abcdefghijklmnopqrstuvwxyz12345")

    def test_hf_token(self):
        assert looks_like_secret("hf_abcdefghijklmnopqrstuvwxyz1234")

    def test_short_string_not_secret(self):
        assert not looks_like_secret("short")

    def test_plain_text_not_secret(self):
        assert not looks_like_secret("this is just a normal sentence with some words")

    def test_non_string_not_secret(self):
        assert not looks_like_secret(12345)  # type: ignore[arg-type]


class TestScrubSecrets:
    def test_scrubs_openai_key(self):
        text = "using key sk-abcdefghijklmnopqrstuvwxyz123456 here"
        result = scrub_secrets(text)
        assert "sk-" not in result
        assert "REDACTED" in result

    def test_scrubs_anthropic_key(self):
        text = "key=sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
        result = scrub_secrets(text)
        assert "sk-ant" not in result
        assert "REDACTED" in result

    def test_preserves_uuid(self):
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = scrub_secrets(uuid)
        assert uuid in result

    def test_scrubs_bearer_token(self):
        text = "Authorization: Bearer mytoken123456789abcdefghijklmnop"
        result = scrub_secrets(text)
        assert "mytoken" not in result
        assert "REDACTED_BEARER_TOKEN" in result

    def test_non_string_passthrough(self):
        assert scrub_secrets(None) is None  # type: ignore[arg-type]

    def test_clean_text_unchanged(self):
        text = "no secrets here"
        assert scrub_secrets(text) == text


class TestAssertNoSecrets:
    def test_raises_on_secret_string(self):
        with pytest.raises(SecretLeakError):
            assert_no_secrets("sk-abcdefghijklmnopqrstuvwxyz123456")

    def test_raises_on_secret_in_dict(self):
        with pytest.raises(SecretLeakError):
            assert_no_secrets({"key": "sk-abcdefghijklmnopqrstuvwxyz123456"})

    def test_raises_on_secret_in_list(self):
        with pytest.raises(SecretLeakError):
            assert_no_secrets(["normal", "sk-abcdefghijklmnopqrstuvwxyz123456"])

    def test_clean_dict_passes(self):
        assert_no_secrets({"key": "value", "count": 42})

    def test_clean_string_passes(self):
        assert_no_secrets("just a regular string")
