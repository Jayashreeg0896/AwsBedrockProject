import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'lambda'))
import handler as lambda_handler


# Feature: serverless-bedrock-chat, Property 2: Successful response format
@pytest.mark.property
class TestSuccessfulResponseFormatProperty:
    """Property 2: Successful response format
    
    For any successful Bedrock response, the Chat_Service should return 
    HTTP status code 200 and a body that is valid JSON containing the 
    AI-generated text.
    
    Validates: Requirements 1.3
    """
    
    @given(ai_response=st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_any_bedrock_response_returns_200_with_json(self, mock_bedrock, ai_response):
        """Property test: Any Bedrock response results in 200 status with valid JSON"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": ai_response}]
                }
            }
        }
        
        event = {"body": json.dumps({"question": "test"})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        assert response['statusCode'] == 200
        # Verify body is valid JSON
        body = json.loads(response['body'])
        assert 'response' in body
        assert body['response'] == ai_response


# Feature: serverless-bedrock-chat, Property 4: Response JSON structure
@pytest.mark.property
class TestResponseJsonStructureProperty:
    """Property 4: Response JSON structure
    
    For any response returned by the Chat_Service, the body should be 
    valid JSON that can be parsed without errors.
    
    Validates: Requirements 1.5
    """
    
    @given(question=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_all_responses_have_valid_json_body(self, mock_bedrock, question):
        """Property test: All responses have valid JSON body"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Response"}]
                }
            }
        }
        
        event = {"body": json.dumps({"question": question})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert - body must be valid JSON
        try:
            parsed_body = json.loads(response['body'])
            assert isinstance(parsed_body, dict)
        except json.JSONDecodeError as e:
            pytest.fail(f"Response body is not valid JSON: {e}")


# Feature: serverless-bedrock-chat, Property 8: Error status codes
@pytest.mark.property
class TestErrorStatusCodesProperty:
    """Property 8: Error status codes
    
    For any error condition (invalid input, Bedrock failure, hibernation), 
    the Chat_Service should return a non-200 HTTP status code.
    
    Validates: Requirements 8.5
    """
    
    @given(question=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_hibernation_returns_non_200_status(self, question):
        """Property test: Hibernation always returns non-200 status"""
        # Arrange - need to reload handler module with new environment
        import sys
        import importlib
        
        # Set environment before importing
        os.environ['SYSTEM_STATE'] = 'HIBERNATED'
        
        # Reload the handler module to pick up new environment variable
        if 'handler' in sys.modules:
            importlib.reload(sys.modules['handler'])
        
        import handler as lambda_handler
        
        event = {"body": json.dumps({"question": question})}
        context = Mock()
        
        try:
            # Act
            response = lambda_handler.handler(event, context)
            
            # Assert
            assert response['statusCode'] != 200, f"Expected non-200 status but got {response['statusCode']}"
            assert response['statusCode'] == 503
        finally:
            # Cleanup - reset to ACTIVE for other tests
            os.environ['SYSTEM_STATE'] = 'ACTIVE'
            if 'handler' in sys.modules:
                importlib.reload(sys.modules['handler'])
    
    @given(question=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_bedrock_failure_raises_exception(self, mock_bedrock, question):
        """Property test: Bedrock failures result in exceptions (non-200 behavior)"""
        # Arrange
        from botocore.exceptions import ClientError
        
        mock_bedrock.converse.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service error'}},
            'converse'
        )
        
        event = {"body": json.dumps({"question": question})}
        context = Mock()
        
        # Act & Assert - should raise exception (which would result in non-200 in production)
        with pytest.raises(ClientError):
            lambda_handler.handler(event, context)
