
import sys
import unittest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

# Mock config.settings before importing core.agent
with patch('config.settings.settings') as mock_settings:
    mock_settings.load_prompts.return_value = {}
    
    # Mock agno module and submodules to bypass import errors
    mock_agno = MagicMock()
    sys.modules['agno'] = mock_agno
    sys.modules['agno.agent'] = mock_agno.agent
    sys.modules['agno.models'] = mock_agno.models
    sys.modules['agno.models.openai'] = mock_agno.models.openai

    from core.agent import agent, PostAction

class TestTokenLogging(unittest.TestCase):
    @patch('core.agent.logger')
    def test_token_logging(self, mock_logger):
        # Mock the Agent inside the InstagramAgent instance
        mock_agno_agent = MagicMock()
        agent.agent = mock_agno_agent

        # Create a mock response object mimicking Agno's RunResponse
        # structure: it has .content (PostAction) and .metrics (dict)
        mock_response_obj = MagicMock()
        mock_response_obj.content = PostAction(
            should_comment=True,
            comment_text="Nice photo!",
            reasoning="Test reasoning"
        )
        mock_response_obj.metrics = {"input_tokens": 100, "output_tokens": 50}
        
        mock_agno_agent.run.return_value = mock_response_obj

        # Define a test candidate
        candidate = {
            'username': 'test_user',
            'caption': 'Hello world',
            'media_type': 1,
            'media_id': '12345'
        }

        # Run the method
        agent.decide_and_comment(candidate)

        # Verify logger.info was called with the metrics
        # We look for the call that contains "💰 Token Usage"
        found = False
        for call in mock_logger.info.call_args_list:
            args, _ = call
            if args and "💰 Token Usage" in args[0] and "{'input_tokens': 100, 'output_tokens': 50}" in args[0]:
                found = True
                break
        
        self.assertTrue(found, "Token Usage log not found in logger calls")
        print("\n✅ Verification passed: Token usage logged successfully.")

if __name__ == '__main__':
    unittest.main()
