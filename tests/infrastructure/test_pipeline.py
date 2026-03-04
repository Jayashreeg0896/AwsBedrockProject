import pytest
import yaml
from pathlib import Path
from .cfn_yaml_loader import load_cfn_template


@pytest.mark.infrastructure
class TestGitHubActionsWorkflow:
    """Test GitHub Actions workflow configuration"""
    
    @pytest.fixture
    def workflow(self):
        """Load deploy.yaml workflow"""
        workflow_path = Path('.github/workflows/deploy.yaml')
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_trigger_on_push_to_main(self, workflow):
        """Test that workflow triggers on push to main branch"""
        # 'on' is a Python keyword, so access it via dict methods
        on_config = workflow.get('on', workflow.get(True, {}))
        
        # Handle both dict and list formats
        if isinstance(on_config, dict):
            push_config = on_config.get('push', {})
            if isinstance(push_config, dict):
                branches = push_config.get('branches', [])
            else:
                branches = []
        else:
            branches = []
        
        # If still empty, check the raw YAML string
        if not branches:
            import yaml
            workflow_path = Path('.github/workflows/deploy.yaml')
            with open(workflow_path, 'r') as f:
                content = f.read()
                # Simple string check as fallback
                assert 'branches: [ main ]' in content or 'branches: [main]' in content or '- main' in content, \
                    "Workflow should trigger on push to main branch"
        else:
            assert 'main' in branches, f"Expected 'main' in branches but got: {branches}"
    
    def test_aws_authentication_secrets(self, workflow):
        """Test that workflow uses AWS authentication secrets"""
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find Configure AWS step
        aws_config_step = None
        for step in steps:
            if 'Configure AWS' in step.get('name', ''):
                aws_config_step = step
                break
        
        assert aws_config_step is not None
        with_config = aws_config_step.get('with', {})
        
        # Check for AWS credential secrets
        assert 'secrets.AWS_ACCESS_KEY_ID' in str(with_config.get('aws-access-key-id', ''))
        assert 'secrets.AWS_SECRET_ACCESS_KEY' in str(with_config.get('aws-secret-access-key', ''))
    
    def test_docker_build_step_exists(self, workflow):
        """Test that workflow includes Docker build step"""
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find build step
        build_step = None
        for step in steps:
            if 'Build image' in step.get('name', ''):
                build_step = step
                break
        
        assert build_step is not None
        run_command = build_step.get('run', '')
        assert 'docker build' in run_command
        assert './lambda' in run_command
    
    def test_image_tagged_with_commit_sha(self, workflow):
        """Test that workflow tags image with Git commit SHA"""
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find tag step
        tag_step = None
        for step in steps:
            if 'Tag image' in step.get('name', ''):
                tag_step = step
                break
        
        assert tag_step is not None
        run_command = tag_step.get('run', '')
        assert 'docker tag' in run_command
        assert 'github.sha' in run_command
    
    def test_ecr_push_step_exists(self, workflow):
        """Test that workflow includes ECR push step"""
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find push step
        push_step = None
        for step in steps:
            if 'Push image' in step.get('name', ''):
                push_step = step
                break
        
        assert push_step is not None
        run_command = push_step.get('run', '')
        assert 'docker push' in run_command
    
    def test_cloudformation_deployment_step(self, workflow):
        """Test that workflow includes CloudFormation deployment step"""
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find deploy step
        deploy_step = None
        for step in steps:
            if 'Deploy' in step.get('name', ''):
                deploy_step = step
                break
        
        assert deploy_step is not None
        run_command = deploy_step.get('run', '')
        assert 'aws cloudformation deploy' in run_command
        assert 'infra/app.yaml' in run_command
    
    def test_deployment_uses_new_image_uri(self, workflow):
        """Test that deployment passes new image URI with commit SHA"""
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find deploy step
        deploy_step = None
        for step in steps:
            if 'Deploy' in step.get('name', ''):
                deploy_step = step
                break
        
        assert deploy_step is not None
        run_command = deploy_step.get('run', '')
        assert 'ImageUri=' in run_command
        assert 'github.sha' in run_command
    
    def test_required_secrets_referenced(self, workflow):
        """Test that all required secrets are referenced in workflow"""
        workflow_str = yaml.dump(workflow)
        
        required_secrets = [
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_REGION',
            'ECR_REPO_URI',
            'LAMBDA_ROLE_ARN',
            'STACK_NAME',
            'PROJECT'
        ]
        
        for secret in required_secrets:
            assert f'secrets.{secret}' in workflow_str, f"Secret {secret} not found in workflow"



@pytest.mark.infrastructure
class TestBootstrapScript:
    """Test bootstrap.sh script configuration"""
    
    @pytest.fixture
    def bootstrap_script(self):
        """Load bootstrap.sh script"""
        script_path = Path('bootstrap.sh')
        with open(script_path, 'r') as f:
            return f.read()
    
    def test_deployment_sequence(self, bootstrap_script):
        """Test that stacks are deployed in correct order"""
        # Find positions of each deployment command
        foundation_pos = bootstrap_script.find('bedrock-foundation')
        ecr_pos = bootstrap_script.find('bedrock-ecr')
        github_pos = bootstrap_script.find('github-deployer')
        
        # Verify all deployments exist
        assert foundation_pos != -1, "Foundation deployment not found"
        assert ecr_pos != -1, "ECR deployment not found"
        assert github_pos != -1, "GitHub user deployment not found"
        
        # Verify correct order: foundation -> ECR -> GitHub user
        assert foundation_pos < ecr_pos, "Foundation should be deployed before ECR"
        assert ecr_pos < github_pos, "ECR should be deployed before GitHub user"
    
    def test_iam_capabilities_for_foundation(self, bootstrap_script):
        """Test that foundation deployment uses IAM capabilities flag"""
        # Find foundation deployment section
        lines = bootstrap_script.split('\n')
        
        foundation_section = []
        in_foundation = False
        for line in lines:
            if 'bedrock-foundation' in line:
                in_foundation = True
            if in_foundation:
                foundation_section.append(line)
                if 'ProjectTag=' in line:  # End of foundation command
                    break
        
        foundation_text = '\n'.join(foundation_section)
        assert '--capabilities CAPABILITY_NAMED_IAM' in foundation_text
    
    def test_iam_capabilities_for_github_user(self, bootstrap_script):
        """Test that GitHub user deployment uses IAM capabilities flag"""
        # Find GitHub user deployment section
        lines = bootstrap_script.split('\n')
        
        github_section = []
        in_github = False
        for line in lines:
            if 'github-deployer' in line:
                in_github = True
            if in_github:
                github_section.append(line)
                if line.strip() and not line.strip().startswith('--') and 'github-deployer' not in line:
                    break
        
        github_text = '\n'.join(github_section)
        assert '--capabilities CAPABILITY_NAMED_IAM' in github_text
    
    def test_foundation_template_path(self, bootstrap_script):
        """Test that foundation deployment references correct template"""
        assert 'infra/foundation.yaml' in bootstrap_script
    
    def test_ecr_template_path(self, bootstrap_script):
        """Test that ECR deployment references correct template"""
        assert 'infra/ecr.yaml' in bootstrap_script
    
    def test_github_user_template_path(self, bootstrap_script):
        """Test that GitHub user deployment references correct template"""
        assert 'infra/github-user.yaml' in bootstrap_script


@pytest.mark.infrastructure
class TestCloudFormationOutputs:
    """Test that CloudFormation templates define required outputs"""
    
    def test_foundation_defines_role_arn_output(self):
        """Test that foundation.yaml defines Lambda role ARN output"""
        template_path = Path('infra/foundation.yaml')
        template = load_cfn_template(template_path)
        
        outputs = template.get('Outputs', {})
        assert 'LambdaRoleArn' in outputs
    
    def test_ecr_defines_repository_uri_output(self):
        """Test that ecr.yaml defines repository URI output"""
        template_path = Path('infra/ecr.yaml')
        template = load_cfn_template(template_path)
        
        outputs = template.get('Outputs', {})
        assert 'RepoUri' in outputs
