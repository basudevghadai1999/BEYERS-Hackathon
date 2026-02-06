import unittest
from google.adk.models.registry import LLMRegistry
from google.adk.models.lite_llm import LiteLlm

class TestBedrockIntegration(unittest.TestCase):
    
    def test_bedrock_resolution(self):
        # Verify that bedrock/ prefix resolves to LiteLlm
        print("\nVerifying bedrock/ resolution...")
        model_id = "bedrock/us.anthropic.claude-opus-4-5-20251101-v1:0"
        llm_cls = LLMRegistry.resolve(model_id)
        
        print(f"Model {model_id} resolved to: {llm_cls.__name__}")
        self.assertEqual(llm_cls, LiteLlm)

    def test_bedrock_initialization(self):
        # Verify that we can instantiate the LLM with the bedrock ID
        print("Verifying bedrock/ initialization...")
        model_id = "bedrock/amazon.titan-text-lite-v1"
        llm_instance = LLMRegistry.new_llm(model_id)
        
        print(f"LLM instance created for: {llm_instance.model}")
        self.assertEqual(llm_instance.model, model_id)
        self.setIsInstance(llm_instance, LiteLlm)

    def setIsInstance(self, instance, cls):
        self.assertTrue(isinstance(instance, cls))

if __name__ == "__main__":
    unittest.main()
