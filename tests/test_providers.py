"""Tests for the model provider abstraction system"""

import os
from unittest.mock import Mock, patch

from providers import ModelProviderRegistry, ModelResponse
from providers.base import ProviderType
from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider


class TestModelProviderRegistry:
    """Test the model provider registry"""

    def setup_method(self):
        """Clear registry before each test"""
        ModelProviderRegistry._providers.clear()
        ModelProviderRegistry._initialized_providers.clear()

    def test_register_provider(self):
        """Test registering a provider"""
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        assert ProviderType.GOOGLE in ModelProviderRegistry._providers
        assert ModelProviderRegistry._providers[ProviderType.GOOGLE] == GeminiModelProvider

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_get_provider(self):
        """Test getting a provider instance"""
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        provider = ModelProviderRegistry.get_provider(ProviderType.GOOGLE)

        assert provider is not None
        assert isinstance(provider, GeminiModelProvider)
        assert provider.api_key == "test-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_provider_no_api_key(self):
        """Test getting provider without API key returns None"""
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        provider = ModelProviderRegistry.get_provider(ProviderType.GOOGLE)

        assert provider is None

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_get_provider_for_model(self):
        """Test getting provider for a specific model"""
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        provider = ModelProviderRegistry.get_provider_for_model("gemini-2.5-flash-preview-05-20")

        assert provider is not None
        assert isinstance(provider, GeminiModelProvider)

    def test_get_available_providers(self):
        """Test getting list of available providers"""
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

        providers = ModelProviderRegistry.get_available_providers()

        assert len(providers) == 2
        assert ProviderType.GOOGLE in providers
        assert ProviderType.OPENAI in providers

    @patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "test-gemini",
            "OPENAI_API_KEY": "test-openai",
        },
    )
    def test_get_available_models(self):
        """Test mapping of models to providers when API keys are configured"""
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

        models = ModelProviderRegistry.get_available_models()

        assert models["gemini-2.5-flash-preview-05-20"] == ProviderType.GOOGLE
        assert models["gemini-2.5-pro-preview-06-05"] == ProviderType.GOOGLE
        # Gemini also exposes shorthand aliases that should be included
        assert models["flash"] == ProviderType.GOOGLE
        assert models["pro"] == ProviderType.GOOGLE

        assert models["o3"] == ProviderType.OPENAI
        assert models["o3-mini"] == ProviderType.OPENAI


class TestGeminiProvider:
    """Test Gemini model provider"""

    def test_provider_initialization(self):
        """Test provider initialization"""
        provider = GeminiModelProvider(api_key="test-key")

        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.GOOGLE

    def test_get_capabilities(self):
        """Test getting model capabilities"""
        provider = GeminiModelProvider(api_key="test-key")

        capabilities = provider.get_capabilities("gemini-2.5-flash-preview-05-20")

        assert capabilities.provider == ProviderType.GOOGLE
        assert capabilities.model_name == "gemini-2.5-flash-preview-05-20"
        assert capabilities.max_tokens == 1_048_576
        assert capabilities.supports_extended_thinking

    def test_get_capabilities_pro_model(self):
        """Test getting capabilities for Pro model with thinking support"""
        provider = GeminiModelProvider(api_key="test-key")

        capabilities = provider.get_capabilities("gemini-2.5-pro-preview-06-05")

        assert capabilities.supports_extended_thinking

    def test_model_shorthand_resolution(self):
        """Test model shorthand resolution"""
        provider = GeminiModelProvider(api_key="test-key")

        assert provider.validate_model_name("flash")
        assert provider.validate_model_name("pro")

        capabilities = provider.get_capabilities("flash")
        assert capabilities.model_name == "gemini-2.5-flash-preview-05-20"

    def test_supports_thinking_mode(self):
        """Test thinking mode support detection"""
        provider = GeminiModelProvider(api_key="test-key")

        assert provider.supports_thinking_mode("gemini-2.5-flash-preview-05-20")
        assert provider.supports_thinking_mode("gemini-2.5-pro-preview-06-05")

    @patch("google.genai.Client")
    def test_generate_content(self, mock_client_class):
        """Test content generation"""
        # Mock the client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Generated content"
        # Mock candidates for finish_reason
        mock_candidate = Mock()
        mock_candidate.finish_reason = "STOP"
        mock_response.candidates = [mock_candidate]
        # Mock usage metadata
        mock_usage = Mock()
        mock_usage.prompt_token_count = 10
        mock_usage.candidates_token_count = 20
        mock_response.usage_metadata = mock_usage
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GeminiModelProvider(api_key="test-key")

        response = provider.generate_content(
            prompt="Test prompt", model_name="gemini-2.5-flash-preview-05-20", temperature=0.7
        )

        assert isinstance(response, ModelResponse)
        assert response.content == "Generated content"
        assert response.model_name == "gemini-2.5-flash-preview-05-20"
        assert response.provider == ProviderType.GOOGLE
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.usage["total_tokens"] == 30


class TestOpenAIProvider:
    """Test OpenAI model provider"""

    def test_provider_initialization(self):
        """Test provider initialization"""
        provider = OpenAIModelProvider(api_key="test-key", organization="test-org")

        assert provider.api_key == "test-key"
        assert provider.organization == "test-org"
        assert provider.get_provider_type() == ProviderType.OPENAI

    def test_get_capabilities_o3(self):
        """Test getting O3 model capabilities"""
        provider = OpenAIModelProvider(api_key="test-key")

        capabilities = provider.get_capabilities("o3-mini")

        assert capabilities.provider == ProviderType.OPENAI
        assert capabilities.model_name == "o3-mini"
        assert capabilities.max_tokens == 200_000
        assert not capabilities.supports_extended_thinking

    def test_validate_model_names(self):
        """Test model name validation"""
        provider = OpenAIModelProvider(api_key="test-key")

        assert provider.validate_model_name("o3")
        assert provider.validate_model_name("o3-mini")
        assert not provider.validate_model_name("gpt-4o")
        assert not provider.validate_model_name("invalid-model")

    def test_no_thinking_mode_support(self):
        """Test that no OpenAI models support thinking mode"""
        provider = OpenAIModelProvider(api_key="test-key")

        assert not provider.supports_thinking_mode("o3")
        assert not provider.supports_thinking_mode("o3-mini")
