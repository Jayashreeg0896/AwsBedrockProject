import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'lambda'))
import handler as lambda_handler


@pytest.mark.unit
class TestHandlerDefaultQuestion:
    """Test default question behavior when question field is missing"""
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_missing_question_uses_default(self, mock_bedrock):
        """Test that missing question field uses 'whats your name?' as default"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "I am Claude"}]
                }
            }
        }
        
        event = {"body": "{}"}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        mock_bedrock.converse.assert_called_once()
        call_args = mock_bedrock.converse.call_args
        messages = call_args.kwargs['messages']
        assert messages[0]['content'][0]['text'] == "whats your name?"
        assert response['statusCode'] == 200
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_empty_body_uses_default_question(self, mock_bedrock):
        """Test that empty body uses default question"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "I am Claude"}]
                }
            }
        }
        
        event = {}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        call_args = mock_bedrock.converse.call_args
        messages = call_args.kwargs['messages']
        assert messages[0]['content'][0]['text'] == "whats your name?"


@pytest.mark.unit
class TestHandlerHibernation:
    """Test hibernation mode behavior"""
    
    @patch.dict(os.environ, {'SYSTEM_STATE': 'HIBERNATED'})
    def test_hibernated_returns_503(self):
        """Test that SYSTEM_STATE=HIBERNATED returns HTTP 503"""
        # Arrange
        event = {"body": json.dumps({"question": "test question"})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        assert response['statusCode'] == 503
        assert 'System parked' in response['body']
    
    @patch.dict(os.environ, {'SYSTEM_STATE': 'HIBERNATED'})
    @patch('handler.bedrock')
    def test_hibernated_does_not_call_bedrock(self, mock_bedrock):
        """Test that hibernated state prevents Bedrock invocation"""
        # Arrange
        event = {"body": json.dumps({"question": "test question"})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        mock_bedrock.converse.assert_not_called()
        assert response['statusCode'] == 503


@pytest.mark.unit
class TestHandlerActiveMode:
    """Test active mode behavior"""
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_active_mode_processes_request(self, mock_bedrock):
        """Test that SYSTEM_STATE=ACTIVE allows normal processing"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Test response"}]
                }
            }
        }
        
        event = {"body": json.dumps({"question": "What is AI?"})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        mock_bedrock.converse.assert_called_once()
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == "Test response"
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_active_mode_invokes_bedrock_with_question(self, mock_bedrock):
        """Test that active mode invokes Bedrock with the provided question"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Answer"}]
                }
            }
        }
        
        test_question = "How does Lambda work?"
        event = {"body": json.dumps({"question": test_question})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        call_args = mock_bedrock.converse.call_args
        messages = call_args.kwargs['messages']
        assert messages[0]['content'][0]['text'] == test_question


@pytest.mark.unit
class TestHandlerErrorHandling:
    """Test error handling behavior"""
    
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_bedrock_api_failure_raises_exception(self, mock_bedrock):
        """Test that Bedrock API failure is handled gracefully"""
        # Arrange
        from botocore.exceptions import ClientError
        
        mock_bedrock.converse.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'converse'
        )
        
        event = {"body": json.dumps({"question": "test"})}
        context = Mock()
        
        # Act & Assert
        with pytest.raises(ClientError):
            lambda_handler.handler(event, context)
