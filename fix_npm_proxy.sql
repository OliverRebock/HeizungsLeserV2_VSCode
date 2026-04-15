update proxy_host
set modified_on = datetime('now'),
    forward_host = 'heizungsleser-v2-frontend',
    forward_port = 80,
    forward_scheme = 'http',
    block_exploits = 1,
    allow_websocket_upgrade = 1,
    http2_support = 1,
    ssl_forced = 1,
    locations = '[{"path":"/api","advanced_config":"","forward_scheme":"http","forward_host":"heizungsleser-v2-backend","forward_port":8000}]'
where id = 1;
select id, domain_names, forward_host, forward_port, locations from proxy_host where id = 1;
