export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  tenants: UserTenant[];
}

export interface UserTenant {
  tenant_id: number;
  role: 'platform_admin' | 'tenant_admin' | 'tenant_user';
  tenant_name: string;
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  influx_bucket?: string;
  influx_token?: string;
}

export interface Device {
  id: number;
  tenant_id: number;
  display_name: string;
  slug: string;
  source_type: string;
  influx_database_name: string;
  influx_token?: string;
  is_active: boolean;
  is_online: boolean;
  last_seen?: string;
  created_at: string;
}

export interface Entity {
  entity_id: string;
  domain: string;
  friendly_name: string;
  chartable: boolean;
  data_kind: 'numeric' | 'binary' | 'enum' | 'string';
  options?: string[];
  icon?: string;
  device_class?: string;
  last_seen?: string;
  last_value?: string | number;
  unit_of_measurement?: string;
}

export interface TimeSeriesPoint {
  ts: string;
  value: number;
  state?: string;
}

export interface TimeSeries {
  entity_id: string;
  friendly_name: string;
  domain: string;
  data_kind: string;
  chartable: boolean;
  points: TimeSeriesPoint[];
  meta: {
    options?: string[];
    icon?: string;
    device_class?: string;
    unit_of_measurement?: string;
  };
}

export interface DeviceDataResponse {
  device: Device;
  range: {
    from: string;
    to: string;
    interval: string;
  };
  series: TimeSeries[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AnalysisFinding {
  title: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  evidence: string[];
}

export interface AnalysisAnomaly {
  title: string;
  description: string;
}

export interface DetectedErrorCode {
  code: string;
  label: string;
  source_entity: string;
  source_label: string;
  observed_value: string;
}

export interface DeepAnalysisResponse {
  device_id: number;
  device_name: string;
  from: string;
  to: string;
  technical_summary: string;
  diagnostic_steps: string[];
  suspected_causes: string[];
  technical_findings: AnalysisFinding[];
  confidence: string;
  disclaimer: string;
}

export interface AnalysisResponse {
  device_id: number;
  device_name: string;
  from: string;
  to: string;
  summary: string;
  overall_status: string;
  findings: AnalysisFinding[];
  anomalies: AnalysisAnomaly[];
  optimization_hints: string[];
  detected_error_codes?: DetectedErrorCode[];
  recommended_followup_checks: string[];
  confidence: string;
  should_trigger_error_analysis: boolean;
  disclaimer: string;
  raw_summary?: any;
  deep_analysis_result?: DeepAnalysisResponse;
}
