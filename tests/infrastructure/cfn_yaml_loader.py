"""Custom YAML loader for CloudFormation templates with intrinsic functions"""
import yaml


class CloudFormationLoader(yaml.SafeLoader):
    """YAML loader that handles CloudFormation intrinsic functions"""
    pass


def cfn_constructor(loader, tag_suffix, node):
    """Constructor for CloudFormation intrinsic functions
    
    Converts CloudFormation tags like !Ref, !GetAtt, !Sub into dictionaries
    that preserve the function name and value for testing.
    """
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        value = loader.construct_mapping(node)
    else:
        value = None
    
    # Return a dict with the function name and value
    return {f'Fn::{tag_suffix}': value}


# Register constructors for common CloudFormation intrinsic functions
CloudFormationLoader.add_multi_constructor('!', cfn_constructor)


def load_cfn_template(file_path):
    """Load a CloudFormation template with support for intrinsic functions
    
    Args:
        file_path: Path to the CloudFormation YAML template
        
    Returns:
        Parsed template as a dictionary
    """
    with open(file_path, 'r') as f:
        return yaml.load(f, Loader=CloudFormationLoader)
