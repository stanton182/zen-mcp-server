import types

from utils.model_context import ModelContext


def test_reserved_for_response_zero_respected():
    mc = ModelContext('dummy-model')
    # Inject capabilities to avoid provider lookup
    mc._capabilities = types.SimpleNamespace(max_tokens=1000)
    allocation = mc.calculate_token_allocation(reserved_for_response=0)
    assert allocation.response_tokens == 0
