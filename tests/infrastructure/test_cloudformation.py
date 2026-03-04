import pytest
import yaml
from pathlib import Path
from .cfn_yaml_loader import load_cfn_template


@pytest.mark.infrastructure
class TestFoundationTemplate:
    """Test foundation.yaml CloudFormation template"""
    
    @pytest.fixture
    def foundation_template(self):
        """Load foundation.yaml template"""
        template_path = Path('infra/foundation.yaml')
        return load_cfn_template(template_path)
    
    def test_iam_role_exists(self, foundation_template):
        """Test that IAM role resource exists"""
        resources = foundation_template.get('Resources', {})
        assert 'LambdaRole' in resources
        assert resources['LambdaRole']['Type'] == 'AWS::IAM::Role'
    
    def test_bedrock_invoke_permission(self, foundation_template):
        """Test that Bedrock invoke permission is granted"""
        resources = foundation_template.get('Resources', {})
        policy = resources.get('LambdaPolicy', {})
        policy_doc = policy.get('Properties', {}).get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        
        # Find statement with Bedrock permissions
        bedrock_actions = []
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            bedrock_actions.extend([a for a in actions if 'bedrock' in a.lower()])
        
        assert 'bedrock:InvokeModel' in bedrock_actions
    
    def test_cloudwatch_logs_permission(self, foundation_template):
        """Test that CloudWatch Logs write permissions are granted"""
        resources = foundation_template.get('Resources', {})
        policy = resources.get('LambdaPolicy', {})
        policy_doc = policy.get('Properties', {}).get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        
        # Find statement with CloudWatch Logs permissions
        logs_actions = []
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            logs_actions.extend([a for a in actions if 'logs:' in a])
        
        assert 'logs:CreateLogGroup' in logs_actions
        assert 'logs:CreateLogStream' in logs_actions
        assert 'logs:PutLogEvents' in logs_actions
    
    def test_lambda_role_arn_output(self, foundation_template):
        """Test that Lambda role ARN is exported as output"""
        outputs = foundation_template.get('Outputs', {})
        assert 'LambdaRoleArn' in outputs


@pytest.mark.infrastructure
class TestECRTemplate:
    """Test ecr.yaml CloudFormation template"""
    
    @pytest.fixture
    def ecr_template(self):
        """Load ecr.yaml template"""
        template_path = Path('infra/ecr.yaml')
        return load_cfn_template(template_path)
    
    def test_ecr_repository_exists(self, ecr_template):
        """Test that ECR repository resource exists"""
        resources = ecr_template.get('Resources', {})
        assert 'Repo' in resources
        assert resources['Repo']['Type'] == 'AWS::ECR::Repository'
    
    def test_repository_uri_output(self, ecr_template):
        """Test that repository URI is exported as output"""
        outputs = ecr_template.get('Outputs', {})
        assert 'RepoUri' in outputs


@pytest.mark.infrastructure
class TestGitHubUserTemplate:
    """Test github-user.yaml CloudFormation template"""
    
    @pytest.fixture
    def github_user_template(self):
        """Load github-user.yaml template"""
        template_path = Path('infra/github-user.yaml')
        return load_cfn_template(template_path)
    
    def test_iam_user_exists(self, github_user_template):
        """Test that IAM user resource exists"""
        resources = github_user_template.get('Resources', {})
        assert 'GitHubDeployerUser' in resources
        assert resources['GitHubDeployerUser']['Type'] == 'AWS::IAM::User'
    
    def test_ecr_permissions(self, github_user_template):
        """Test that ECR permissions are granted"""
        resources = github_user_template.get('Resources', {})
        policy = resources.get('GitHubDeployerPolicy', {})
        policy_doc = policy.get('Properties', {}).get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        
        # Find ECR permissions
        ecr_actions = []
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            ecr_actions.extend([a for a in actions if 'ecr:' in a])
        
        assert len(ecr_actions) > 0
        assert 'ecr:PutImage' in ecr_actions
    
    def test_cloudformation_permissions(self, github_user_template):
        """Test that CloudFormation permissions are granted"""
        resources = github_user_template.get('Resources', {})
        policy = resources.get('GitHubDeployerPolicy', {})
        policy_doc = policy.get('Properties', {}).get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        
        # Find CloudFormation permissions
        cfn_actions = []
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            cfn_actions.extend([a for a in actions if 'cloudformation:' in a.lower()])
        
        assert len(cfn_actions) > 0
    
    def test_lambda_permissions(self, github_user_template):
        """Test that Lambda permissions are granted"""
        resources = github_user_template.get('Resources', {})
        policy = resources.get('GitHubDeployerPolicy', {})
        policy_doc = policy.get('Properties', {}).get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        
        # Find Lambda permissions
        lambda_actions = []
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            lambda_actions.extend([a for a in actions if 'lambda:' in a.lower()])
        
        assert len(lambda_actions) > 0
    
    def test_iam_passrole_permission(self, github_user_template):
        """Test that IAM PassRole permission is granted"""
        resources = github_user_template.get('Resources', {})
        policy = resources.get('GitHubDeployerPolicy', {})
        policy_doc = policy.get('Properties', {}).get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        
        # Find IAM PassRole permission
        iam_actions = []
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            iam_actions.extend([a for a in actions if 'iam:' in a.lower()])
        
        assert 'iam:PassRole' in iam_actions


@pytest.mark.infrastructure
class TestAppTemplate:
    """Test app.yaml CloudFormation template"""
    
    @pytest.fixture
    def app_template(self):
        """Load app.yaml template"""
        template_path = Path('infra/app.yaml')
        return load_cfn_template(template_path)
    
    def test_lambda_function_exists(self, app_template):
        """Test that Lambda function resource exists"""
        resources = app_template.get('Resources', {})
        assert 'ChatFunction' in resources
        assert resources['ChatFunction']['Type'] == 'AWS::Lambda::Function'
    
    def test_container_image_configuration(self, app_template):
        """Test that Lambda is configured for container image"""
        resources = app_template.get('Resources', {})
        lambda_func = resources.get('ChatFunction', {})
        properties = lambda_func.get('Properties', {})
        
        assert properties.get('PackageType') == 'Image'
        assert 'Code' in properties
        assert 'ImageUri' in properties['Code']
    
    def test_system_state_environment_variable(self, app_template):
        """Test that SYSTEM_STATE environment variable is defined"""
        resources = app_template.get('Resources', {})
        lambda_func = resources.get('ChatFunction', {})
        properties = lambda_func.get('Properties', {})
        env = properties.get('Environment', {})
        variables = env.get('Variables', {})
        
        assert 'SYSTEM_STATE' in variables
    
    def test_image_uri_parameter(self, app_template):
        """Test that ImageUri parameter exists"""
        parameters = app_template.get('Parameters', {})
        assert 'ImageUri' in parameters
    
    def test_lambda_role_arn_parameter(self, app_template):
        """Test that LambdaRoleArn parameter exists"""
        parameters = app_template.get('Parameters', {})
        assert 'LambdaRoleArn' in parameters
    
    def test_tag_parameters(self, app_template):
        """Test that tag parameters exist"""
        parameters = app_template.get('Parameters', {})
        assert 'ProjectTag' in parameters
        assert 'OwnerTag' in parameters
        assert 'EnvTag' in parameters
    
    def test_tags_applied_to_lambda(self, app_template):
        """Test that tags are applied to Lambda function"""
        resources = app_template.get('Resources', {})
        lambda_func = resources.get('ChatFunction', {})
        properties = lambda_func.get('Properties', {})
        tags = properties.get('Tags', [])
        
        tag_keys = [tag['Key'] for tag in tags]
        assert 'Project' in tag_keys
        assert 'Owner' in tag_keys
        assert 'Environment' in tag_keys
