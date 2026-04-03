"""Tests for the redaction module."""

from anamnesis_mcp.redaction import redact


class TestRedaction:
    def test_clean_text_passes_through(self):
        result = redact("Solved the Lambda cold-start issue by adjusting concurrency.")
        assert result.was_redacted is False
        assert result.patterns_fired == []
        assert "Lambda" in result.text

    def test_api_key_assignment(self):
        result = redact("Set api_key = sk-abc123def456 in the config")
        assert result.was_redacted is True
        assert "api_key_assignment" in result.patterns_fired
        assert "sk-abc123def456" not in result.text
        assert "[REDACTED:api_key_assignment]" in result.text

    def test_password_assignment(self):
        result = redact("password: mysecretpassword123")
        assert result.was_redacted is True
        assert "api_key_assignment" in result.patterns_fired

    def test_token_assignment(self):
        result = redact("token = ghp_xxxxxxxxxxxxxxxxxxxx")
        assert result.was_redacted is True

    def test_base64_blob(self):
        blob = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrs"  # 45 mixed base64 chars
        result = redact(f"Data: {blob}")
        assert result.was_redacted is True
        assert "base64_blob" in result.patterns_fired
        assert blob not in result.text

    def test_hex_key(self):
        # 32 hex chars — below base64 threshold (40) but meets hex threshold (32)
        hex_key = "a1b2c3d4" * 4
        result = redact(f"hash {hex_key} end")
        assert result.was_redacted is True
        assert "hex_key" in result.patterns_fired
        assert hex_key not in result.text

    def test_aws_credential(self):
        result = redact("aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        assert result.was_redacted is True
        assert "aws_credential" in result.patterns_fired

    def test_api_key_prefix_sk(self):
        result = redact("Using sk-proj-abcdefghij1234567890 for the API")
        assert result.was_redacted is True
        assert "api_key_prefix" in result.patterns_fired
        assert "sk-proj-abcdefghij1234567890" not in result.text

    def test_api_key_prefix_pk(self):
        result = redact("pk_live_abcdefghij1234567890")
        assert result.was_redacted is True
        assert "api_key_prefix" in result.patterns_fired

    def test_multiple_patterns_fire(self):
        text = "api_key = sk-proj-abcdefghij1234567890extra and aws_secret_key = AKIAIOSFODNN7EXAMPLE"
        result = redact(text)
        assert result.was_redacted is True
        assert len(result.patterns_fired) >= 2

    def test_short_hex_not_redacted(self):
        result = redact("Commit hash abc123 is fine")
        assert "hex_key" not in result.patterns_fired

    def test_short_base64_not_redacted(self):
        result = redact("The word Hello is not a secret")
        assert "base64_blob" not in result.patterns_fired

    def test_bearer_token(self):
        result = redact("Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig")
        assert result.was_redacted is True
        assert "bearer_token" in result.patterns_fired

    def test_jwt_token(self):
        result = redact("Got token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
        assert result.was_redacted is True
        assert "jwt_token" in result.patterns_fired

    def test_pem_private_key(self):
        result = redact("Found -----BEGIN RSA PRIVATE KEY----- in the config")
        assert result.was_redacted is True
        assert "pem_private_key" in result.patterns_fired

    def test_connection_string(self):
        result = redact("Using postgresql://admin:secret@db.example.com:5432/mydb")
        assert result.was_redacted is True
        assert "connection_string" in result.patterns_fired

    def test_github_pat(self):
        result = redact("github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWX")
        assert result.was_redacted is True
        assert "api_key_prefix" in result.patterns_fired

    def test_slack_token(self):
        # Token prefix + 20 random chars (enough to trigger the pattern)
        result = redact("xoxb-FAKE_TEST_VALUE_NOT_REAL_01234567890")
        assert result.was_redacted is True
        assert "api_key_prefix" in result.patterns_fired

    def test_google_api_key(self):
        result = redact("Using AIzaSyA1234567890abcdefghijklmnopqrstuvw for maps")
        assert result.was_redacted is True
        assert "google_api_key" in result.patterns_fired
