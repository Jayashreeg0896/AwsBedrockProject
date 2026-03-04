import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, Mock

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'lambda'))
import handler as lambda_handler


@pytest.mark.unit
class TestBedrockConfiguration:
    """Test Bedrock model configuration"""
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_model_id_is_claude_haiku(self, mock_bedrock):
        """Test that model ID is anthropic.claude-3-haiku-20240307-v1:0"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Response"}]
                }
            }
        }
        
        event = {"body": '{"question": "test"}'}
        context = Mock()
        
        # Act
        lambda_handler.handler(event, context)
        
        # Assert
        call_args = mock_bedrock.converse.call_args
        assert call_args.kwargs['modelId'] == 'anthropic.claude-3-haiku-20240307-v1:0'
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_max_tokens_is_200(self, mock_bedrock):
        """Test that max tokens is configured to 200"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Response"}]
                }
            }
        }
        
        event = {"body": '{"question": "test"}'}
        context = Mock()
        
        # Act
        lambda_handler.handler(event, context)
        
        # Assert
        call_args = mock_bedrock.converse.call_args
        inference_config = call_args.kwargs['inferenceConfig']
        assert inference_config['maxTokens'] == 200
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_uses_converse_api(self, mock_bedrock):
        """Test that converse API is used (not invoke_model)"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Response"}]
                }
            }
        }
        
        event = {"body": '{"question": "test"}'}
        context = Mock()
        
        # Act
        lambda_handler.handler(event, context)
        
        # Assert
        mock_bedrock.converse.assert_called_once()
        # Verify invoke_model is not called
        assert not hasattr(mock_bedrock, 'invoke_model') or not mock_bedrock.invoke_model.called
