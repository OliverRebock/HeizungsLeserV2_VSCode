export interface User {
  id: number;
  email: string;
  full_name?: string;
  is_active?: boolean;
  is_superuser: boolean;
  tenants: UserTenant[];
}

export interface UserTenant {
  tenant_id: number;
  role: string;
  tenant_name: string;
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
  retention_policy?: string;
  source_config?: Record<string, any>;
  is_active: boolean;
  is_online: boolean;
  last_seen?: string;
  created_at: string;
  updated_at: string;
}

export interface Entity {
  entity_id: string;
  domain: string;
  friendly_name?: string;
  data_kind: string; // numeric, binary, enum, string
  chartable: boolean;
  icon?: string;
  device_class?: string;
  unit_of_measurement?: string;
  options?: string[];
  last_seen?: string;
  last_value?: string | number;
  source_table?: string;
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
  device_id: number;
  range: {
    from: string;
    to?: string;
  };
  series: TimeSeries[];
}

export interface DashboardDataPoint {
  ts: string;
  value?: number;
  state?: string;
  is_actual: boolean;
}

export interface DashboardEntityData {
  entity_id: string;
  friendly_name: string;
  domain: string;
  data_kind: string;
  latest_point?: DashboardDataPoint;
  sparkline: DashboardDataPoint[];
  is_stale: boolean;
  freshness_info: string;
}

export interface DeviceDashboardResponse {
  device_id: number;
  entities: DashboardEntityData[];
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

export interface ErrorCandidate {
  entity_id: string;
  label: string;
  raw_value: string;
  parsed_code?: string;
  classification: string;
  confidence: string;
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
  detected_error_codes: DetectedErrorCode[];
  error_candidates?: ErrorCandidate[];
  recommended_followup_checks: string[];
  confidence: string;
  should_trigger_error_analysis: boolean;
  disclaimer: string;
  raw_summary?: any;
  deep_analysis_result?: DeepAnalysisResponse;
  analysis_run_id?: string;
}
