$ErrorActionPreference = 'Stop'

$login = curl.exe -k -s -X POST https://heizungsleser.de/api/v1/auth/login -H "Content-Type: application/x-www-form-urlencoded" --data "username=admin@example.com&password=adminpass"
$token = ($login | ConvertFrom-Json).access_token
if (-not $token) { throw 'Login failed: no token' }

$authHeader = "Authorization: Bearer $token"

$tenants = curl.exe -k -s https://heizungsleser.de/api/v1/tenants/ -H $authHeader | ConvertFrom-Json
if (-not $tenants -or $tenants.Count -eq 0) {
    $tenantBody = @{ 
        name = 'Default Tenant'
        is_active = $true
        influx_bucket = 'ha_Input_beyer1V2'
    } | ConvertTo-Json -Compress

    $tenant = curl.exe -k -s -X POST https://heizungsleser.de/api/v1/tenants/ -H $authHeader -H "Content-Type: application/json" --data $tenantBody | ConvertFrom-Json
} else {
    $tenant = $tenants[0]
}

$devices = curl.exe -k -s https://heizungsleser.de/api/v1/devices/ -H $authHeader | ConvertFrom-Json
if (-not $devices -or $devices.Count -eq 0) {
    $deviceBody = @{
        tenant_id = [int]$tenant.id
        display_name = 'Heizungsanlage'
        source_type = 'influxdb_v2'
        influx_database_name = 'ha_Input_beyer1V2'
        is_active = $true
    } | ConvertTo-Json -Compress

    $null = curl.exe -k -s -X POST https://heizungsleser.de/api/v1/devices/ -H $authHeader -H "Content-Type: application/json" --data $deviceBody
}

curl.exe -k -i https://heizungsleser.de/api/v1/devices/ -H $authHeader
