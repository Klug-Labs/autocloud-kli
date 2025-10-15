"""
Autoklug Run - Local Development Server

A local development server that works exactly like setup/app.py but integrates
with the autoklug configuration system and global project detection.
"""
import click
from flask import Flask, request, make_response, jsonify, Response
from flask_cors import CORS, cross_origin
from pathlib import Path
import sys
import importlib
import datetime
from itertools import groupby
import os

from .utils import (
    ConfigManager, log_header, log_step, log_success, log_warning, 
    log_error, log_info, log_detail, detect_project_context, find_best_config_files
)


class LocalAuthorizer:
    """
    A class to simulate API Gateway authorizer functionality for local development
    """
    
    def __init__(self, use_cache: bool = False, cache_ttl: int = 300, config: ConfigManager = None):
        """
        Initialize the authorizer
        
        Args:
            use_cache: Whether to cache authorization results
            cache_ttl: Time-to-live for cache entries in seconds
            config: ConfigManager instance with environment variables
        """
        self.use_cache = use_cache
        self.cache_ttl = cache_ttl
        self.auth_cache = {}
        self.config = config
        log_info(f"Authorizer initialized with cache {'enabled' if use_cache else 'disabled'}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if a cache entry is still valid based on TTL"""
        if not self.use_cache or cache_key not in self.auth_cache:
            return False
        
        entry = self.auth_cache[cache_key]
        return (datetime.datetime.now().timestamp() - entry['timestamp']) < self.cache_ttl
    
    def authorize(self, request, route_key: str):
        """
        Authorize a request
        
        Args:
            request: Flask request object
            route_key: API route key (e.g. "GET /path")
            
        Returns:
            Tuple containing:
            - bool: Whether the request is authorized
            - dict: Authorizer context (or None if unauthorized)
            - str: Error message (or None if authorized)
        """
        # For now, implement a simple JWT-based authorization
        # This can be extended based on your specific needs
        
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return False, None, jsonify({'error': 'Missing Authorization header'})
        
        try:
            # Extract token from "Bearer <token>" format
            token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else auth_header
            
            # Simple token validation (you can implement proper JWT validation here)
            if token == 'valid-token':
                context = {
                    'user_id': '12345',
                    'username': 'testuser',
                    'roles': ['user']
                }
                return True, context, None
            else:
                return False, None, jsonify({'error': 'Invalid token'})
                
        except Exception as e:
            return False, None, jsonify({'error': f'Authorization error: {str(e)}'})


def read_router(config: ConfigManager, api_path=None):
    """Read router configuration from the API directory structure"""
    l = []
    root = Path(api_path if api_path else config.tool_config.get('API_PATH', './api'))
    
    if not root.exists():
        log_error(f"API path does not exist: {root}")
        return []
    
    for path_object in root.rglob('*'):
        if '.py' not in path_object.suffixes or path_object.name == '__init__.py':
            continue
        
        relative_path = path_object.relative_to(root)
        full_path_parts = path_object.parts[1:-1]
        relative_path_parts = relative_path.parts[0:-1]
        
        # Skip files that are directly in the root directory
        if len(full_path_parts) == 0:
            continue
        
        url = '/' + '/'.join(relative_path_parts)\
            .replace('.py', '')\
            .lstrip('/')\
            .rstrip('/')
        url = url if url.endswith('/') else f'{url}/'
        
        import re
        url_rule = re.sub(r'/__([^_]+)__/', r'/<\1>/', url)
        
        if url_rule.endswith('/share/'):
            continue
        
        l.append({
            'method': path_object.stem.upper(),
            'path': '.'.join(full_path_parts),
            'filePath': path_object.relative_to(root).as_posix(),
            'pathParameters': [p[2:-2] for p in full_path_parts if p.startswith('__') and p.endswith('__')],
            'urlRule': url_rule.rstrip('/'),
            'urlRuleAG': url_rule.rstrip('/').replace('<', '{').replace('>', '}'),
            'rootPath': full_path_parts[0]
        })
    
    return l


def generate_event(request, config: ConfigManager, now=None, kwargs=None):
    """Generate AWS Lambda event from Flask request"""
    if now is None:
        now = datetime.datetime.now()
    
    if kwargs is None:
        kwargs = {}
    
    # Build the event structure similar to API Gateway
    event = {
        'httpMethod': request.method,
        'path': request.path,
        'pathParameters': kwargs,
        'queryStringParameters': dict(request.args) if request.args else None,
        'headers': dict(request.headers),
        'body': request.get_data(as_text=True) if request.get_data() else None,
        'isBase64Encoded': False,
        'requestContext': {
            'requestId': f"local-{datetime.datetime.now().timestamp()}",
            'stage': 'local',
            'resourcePath': request.path,
            'httpMethod': request.method,
            'requestTime': now.isoformat(),
            'protocol': 'HTTP/1.1',
            'accountId': config.tool_config.get('AWS_ACCOUNT_ID', '123456789012'),
            'apiId': 'local-api',
            'identity': {
                'sourceIp': request.remote_addr,
                'userAgent': request.headers.get('User-Agent', '')
            }
        }
    }
    
    return event


def inject_endpoints_in_app(app, config: ConfigManager, now=None):
    """Generate Flask endpoints from the local structure"""
    methods_by_path = {}
    endpoints_by_path = {}
    
    # Determine the API prefix based on the API_PATH
    api_path = config.tool_config.get('API_PATH', './api')
    if 'api-public' in api_path or 'api_public' in api_path:
        api_prefix = 'api_public'
    else:
        api_prefix = 'api'
    
    endpoints = read_router(config)
    
    for url_rule, endpoints_group in groupby(endpoints, lambda x: x['urlRule']):
        endpoints_by_path[url_rule] = list(endpoints_group)
        methods_by_path[url_rule] = [e['method'] for e in endpoints_by_path[url_rule]]
        
        def create_handler(url_rule, api_prefix):
            def f(**kwargs):
                # Get the route key from the request
                route_key = f"{request.method} {str(request.url_rule)}"
                
                # Check authorization if authorizer is enabled
                if hasattr(app, 'authorizer') and app.authorizer is not None:
                    is_authorized, context, error = app.authorizer.authorize(request, route_key)
                    if not is_authorized:
                        return Response(error, status=401, content_type='application/json')
                
                file_path = f'{api_prefix}.' + \
                    '.'.join(str(request.url_rule).replace('<', '__').replace('>', '__').split(
                        '/') + [request.method.lower()]).lstrip('.')
                
                try:
                    module = importlib.import_module(file_path)
                    event = generate_event(request, config, now, kwargs)
                    
                    # Add authorizer context if available
                    if hasattr(app, 'authorizer') and app.authorizer is not None and context:
                        event['requestContext']['authorizer'] = context
                    
                    res = module.lambda_handler(event, None)
                    if type(res) is dict and 'statusCode' in res:
                        return Response(res.get('body'), status=res.get('statusCode'), content_type='application/json')
                    else:
                        return Response(res.get('body'), status=200, content_type='application/json')
                        
                except ImportError as e:
                    log_error(f"Failed to import module {file_path}: {e}")
                    return Response(jsonify({'error': 'Module not found'}), status=404, content_type='application/json')
                except Exception as e:
                    log_error(f"Error executing handler: {e}")
                    return Response(jsonify({'error': 'Internal server error'}), status=500, content_type='application/json')
            
            f.__name__ = f"handler_{url_rule.replace('/', '_').replace('<', '_').replace('>', '_')}"
            return f
        
        handler = create_handler(url_rule, api_prefix)
        app.route(url_rule, methods=methods_by_path[url_rule])(handler)
        log_detail(f"Injected route: {url_rule} methods: {methods_by_path[url_rule]}")


def start_local_server(tool_path=None, env_path=None, now=None, use_authorizer=False, 
                      use_auth_cache=False, auth_cache_ttl=300, port=None):
    """Start the local development server"""
    
    # Detect project context if not provided
    if not tool_path or not env_path:
        context = detect_project_context()
        detected_tool, detected_env = find_best_config_files(context)
        
        tool_path = tool_path or detected_tool
        env_path = env_path or detected_env
        
        log_info(f"Auto-detected project context:")
        log_detail(f"  Tool config: {tool_path}")
        log_detail(f"  Env config: {env_path}")
    
    # Load configuration
    config = ConfigManager(tool_path, env_path)
    
    log_header("AUTOKLUG LOCAL DEVELOPMENT SERVER")
    log_info(f"Tool config: {tool_path}")
    log_info(f"Env config: {env_path}")
    log_info(f"API path: {config.tool_config.get('API_PATH', './api')}")
    log_info(f"Layer path: {config.tool_config.get('LAYER_PATH', './layers')}")
    
    # Create Flask app
    app = Flask(__name__)
    cors = CORS(app)
    
    # Set up authorizer if requested
    if use_authorizer:
        app.authorizer = LocalAuthorizer(use_cache=use_auth_cache, cache_ttl=auth_cache_ttl, config=config)
        log_info("API Gateway authorizer simulation enabled")
    else:
        app.authorizer = None
    
    # Add paths to Python path
    api_path = Path(config.tool_config.get('API_PATH', './api'))
    layer_path = Path(config.tool_config.get('LAYER_PATH', './layers'))
    
    sys.path.append(str(api_path.parent.absolute()))
    sys.path.append(str((layer_path / 'shared').absolute()))
    
    # Inject endpoints
    inject_endpoints_in_app(app, config, now)
    
    # Set environment variables
    for var, val in config.env_config.items():
        os.environ[var] = val
    
    # Get port
    server_port = port or config.tool_config.get('PORT', 5000)
    
    log_success(f"Starting local server on port {server_port}")
    log_info("Press Ctrl+C to stop the server")
    
    try:
        app.run(debug=True, port=server_port, host='0.0.0.0')
    except KeyboardInterrupt:
        log_info("Server stopped by user")
    except Exception as e:
        log_error(f"Server error: {e}")


@click.command()
@click.option('--tool', '-t',
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--env', '-e',
              help='Path to .env file for environment variables (auto-detected if not provided)')
@click.option('--now', default=None, help='An ISO date to use as now')
@click.option('--use-authorizer', is_flag=True, help='Enable API Gateway authorizer simulation')
@click.option('--use-auth-cache', is_flag=True, help='Enable caching for authorizer results')
@click.option('--auth-cache-ttl', default=300, help='TTL for authorizer cache in seconds')
@click.option('--port', '-p', type=int, help='Port to run the server on (overrides .tool PORT setting)')
def run(tool, env, now, use_authorizer, use_auth_cache, auth_cache_ttl, port):
    """🚀 Start local development server"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        click.echo(click.style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        click.echo(click.style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    # Start the server
    start_local_server(
        tool_path=tool,
        env_path=env,
        now=now,
        use_authorizer=use_authorizer,
        use_auth_cache=use_auth_cache,
        auth_cache_ttl=auth_cache_ttl,
        port=port
    )
