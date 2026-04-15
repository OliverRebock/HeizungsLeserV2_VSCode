-- Insert Heizungsleser V2 Frontend & API Proxy Hosts
-- Frontend Proxy
INSERT OR REPLACE INTO proxy_host 
(id, domainNames, customLocationList, forwardHost, forwardPort, accessListId, certId, ssl, podmanNetwork, advancedConfig, locations, meta, ownerUserId, createdDate, modifiedDate, caching_enabled, allowWebsocketUpgrade, http2Support, blockExploits, preserveHost)
VALUES
(1, 
 '[{"domain":"heizungsleser.de","wildcard":false},{"domain":"*.heizungsleser.de","wildcard":true}]',
 '[]',
 'heizungsleser-v2-frontend',
 80,
 null,
 null,  
 1,
 'proxy',
 '',
 '[{"path":"/api","proxyPass":"http://heizungsleser-v2-backend:8000"}]',
 '{}',
 1,
 datetime('now'),
 datetime('now'),
 0,
 1,
 0,
 1,
 0
);
