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


# Feature: serverless-bedrock-chat, Property 5: Message role formatting
@pytest.mark.property
class TestMessageRoleFormattingProperty:
    """Property 5: Message role formatting
    
    For any question string, when formatted for Bedrock, the message should 
    have role "user" and content containing the question text.
    
    Validates: Requirements 2.4
    """
    
    @given(question=st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_all_messages_have_user_role(self, mock_bedrock, question):
        """Property test: All messages formatted with role 'user'"""
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
        lambda_handler.handler(event, context)
        
        # Assert
        call_args = mock_bedrock.converse.call_args
        messages = call_args.kwargs['messages']
        
        # Verify message structure
        assert len(messages) > 0
        message = messages[0]
        assert message['role'] == 'user'
        assert 'content' in message
        assert len(message['content']) > 0
        assert message['content'][0]['text'] == question


# Feature: serverless-bedrock-chat, Property 6: Response text extraction
@pytest.mark.property
class TestResponseTextExtractionProperty:
    """Property 6: Response text extraction
    
    For any valid Bedrock response structure, the text extraction should 
    successfully retrieve the AI-generated content from the nested response object.
    
    Validates: Requirements 2.5
    """
    
    @given(response_text=st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_text_extracted_from_any_valid_response_structure(self, mock_bedrock, response_text):
        """Property test: Text is correctly extracted from any valid Bedrock response"""
        # Arrange
        # Create valid Bedrock response structure with any text
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": response_text}]
                }
            }
        }
        
        event = {"body": json.dumps({"question": "test"})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert - extracted text should match what was in the response
        body = json.loads(response['body'])
        assert body['response'] == response_text
    
    @given(
        response_text=st.text(min_size=1, max_size=200),
        question=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100)
    @patch('handler.bedrock')
    @patch.dict(os.environ, {'SYSTEM_STATE': 'ACTIVE'})
    def test_extraction_works_for_any_question_response_pair(self, mock_bedrock, response_text, question):
        """Property test: Extraction works regardless of question/response content"""
        # Arrange
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": response_text}]
                }
            }
        }
        
        event = {"body": json.dumps({"question": question})}
        context = Mock()
        
        # Act
        response = lambda_handler.handler(event, context)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # The response should contain the exact text from Bedrock
        assert body['response'] == response_text
        # Verify it's not accidentally using the question
        if question != response_text:
            assert body['response'] != question
