$key="C:\Users\reboc\.ssh\copilot_heizungsleser_ed25519"
$remote="root@10.8.0.1"
$files=@(
  "apps/backend/app/core/query_validation.py|backend/app/core/query_validation.py",
  "apps/backend/app/core/token_encryption.py|backend/app/core/token_encryption.py",
  "apps/backend/app/core/audit_logger.py|backend/app/core/audit_logger.py",
  "apps/backend/app/models/audit.py|backend/app/models/audit.py",
  "apps/backend/alembic/versions/a1b2c3d4e5f6_add_audit_logging_token_encryption.py|backend/alembic/versions/a1b2c3d4e5f6_add_audit_logging_token_encryption.py",
  "apps/backend/app/services/influx.py|backend/app/services/influx.py"
)

foreach($f in $files) {
  $parts=$f.Split("|")
  $src=$parts[0]
  $dst=$parts[1]
  $dir=Split-Path $dst
  ssh -i $key $remote "mkdir -p /opt/heizungsleser-v2/$dir" | Out-Null
  scp -i $key "$src" "${remote}:/opt/heizungsleser-v2/${dst}" | Out-Null
  Write-Host "OK: $dst"
}

Write-Host "DONE"
