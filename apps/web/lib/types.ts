export type OrgRole = "owner" | "admin" | "member" | "viewer";
export type EvidenceStatus = "fact" | "hypothesis" | "inference" | "unknown";
export type ICPStatus = "ai_hypothesis" | "founder_confirmed" | "archived";
export type CompanyFitCategory = "excellent" | "strong" | "potential" | "low_priority";
export type PipelineStage =
  | "prospect" | "qualified" | "drafted" | "approved" | "sent" | "replied" | "meeting" | "won" | "lost" | "not_now";
export type InvestorStage =
  | "discovered" | "researching" | "shortlisted" | "contacted" | "replied" | "meeting" | "follow_up" | "due_diligence" | "passed" | "invested";
export type OpportunityType =
  | "customer" | "investor" | "marketing" | "launch" | "community" | "content" | "partnership" | "media" | "event"
  | "seo" | "geo" | "ai_visibility" | "competitor" | "social" | "grant" | "accelerator" | "podcast" | "newsletter" | "other";
export type LearningInsightStatus = "pending" | "accepted" | "ignored";
export type ActionStatus = "today" | "upcoming" | "waiting" | "completed" | "snoozed";
export type ActionCategory = "customer" | "investor" | "marketing" | "content" | "competitor" | "launch" | "visibility";
export type ContentStatus =
  | "idea" | "generating" | "draft" | "ready" | "approval_required" | "approved"
  | "scheduled" | "published" | "failed" | "rejected" | "archived";
export type VideoStatus = "script_ready" | "rendering" | "ready" | "failed";
export type OutreachMessageStatus = "drafted" | "approved" | "sent" | "rejected";
export type MentionCategory = "positive" | "neutral" | "negative" | "question" | "purchase_intent" | "competitor_comparison" | "feedback";

// ---- Visibility module ----
export type ConfidenceLabelType = "verified" | "estimated" | "unknown";
export type RiskLevelType = "low" | "medium" | "high" | "critical";
export type OptimizationModeType = "analyze_only" | "propose" | "prepare" | "autonomous";
export type WebsiteChangeStatusType = "drafted" | "validated" | "blocked" | "approved" | "branch_created" | "pr_created" | "merged" | "rejected";
export type OpportunityCoverageType = "low" | "medium" | "high";
export type WebsiteOpportunityStatusType = "open" | "proposed" | "rejected" | "completed";
export type VisibilityCoverageStatusType = "mentioned" | "not_detected";

export interface ScanField<T = unknown> {
  value: T;
  confidence: ConfidenceLabelType;
}

export interface Website {
  id: string;
  workspace_id: string;
  product_id: string;
  name: string;
  url: string;
  repository_owner: string;
  repository_name: string;
  default_branch: string;
  deployment_platform: string;
  framework: string;
  framework_confidence: ConfidenceLabelType;
}

export interface WebsiteScan {
  id: string;
  website_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  raw_result: Record<string, ScanField>;
  summary_scores: Record<string, number>;
  error: string;
}

export interface SEOIssue {
  id: string;
  website_scan_id: string;
  issue_type: string;
  impact: string;
  evidence: string;
  recommendation: string;
  confidence: number;
  status: string;
}

export interface VisibilityQuestion {
  id: string;
  website_id: string;
  question: string;
  category: string;
  coverage_status: VisibilityCoverageStatusType;
  evidence_snippet: string;
  confidence: number;
}

export interface ProductTruth {
  id: string;
  product_id: string;
  definition: string;
  target_customer: string;
  problem: string;
  solution: string;
  core_features: string[];
  positioning: string;
  approved_claims: string[];
  forbidden_claims: string[];
  brand_voice: string;
  competitors: string[];
  pricing: string;
  differentiators: string[];
}

export interface WebsiteGuardrails {
  id: string;
  website_id: string;
  protect_product_meaning: boolean;
  protect_brand_voice: boolean;
  protect_visual_design: boolean;
  require_approval_content: boolean;
  require_approval_code: boolean;
  require_approval_production: boolean;
  block_unsupported_claims: boolean;
  run_build_checks: boolean;
  run_visual_checks: boolean;
}

export interface WebsiteOpportunity {
  id: string;
  website_id: string;
  opportunity_id: string | null;
  title: string;
  description: string;
  target_path: string;
  current_coverage: OpportunityCoverageType;
  product_fit_score: number;
  impact: string;
  confidence: number;
  status: WebsiteOpportunityStatusType;
}

export interface WebsiteChangeFile {
  path: string;
  before: string;
  after: string;
  sha?: string;
}

export interface WebsiteChange {
  id: string;
  website_id: string;
  website_opportunity_id: string | null;
  risk_level: RiskLevelType;
  mode: OptimizationModeType;
  status: WebsiteChangeStatusType;
  branch_name: string;
  base_branch: string;
  commit_sha: string;
  pr_number: number | null;
  pr_url: string;
  files_changed: WebsiteChangeFile[];
  semantic_diff: Record<string, unknown>;
  reason: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  is_demo: boolean;
}

export interface Product {
  id: string;
  workspace_id: string;
  name: string;
  website: string;
  description: string;
  category: string;
  target_markets: string[];
  target_countries: string[];
  pricing: string;
  business_model: string;
  stage: string;
  competitors: string[];
  differentiators: string[];
  brand_voice: string;
  cta: string;
  launch_status: string;
  is_demo: boolean;
}

export interface ProductProfile {
  id: string;
  product_id: string;
  product_category: string;
  primary_problem: string;
  primary_buyer: string;
  secondary_buyers: string[];
  target_industries: string[];
  use_cases: string[];
  competitive_categories: string[];
  keywords: string[];
  search_queries: string[];
}

export interface ICPProfile {
  id: string;
  product_id: string;
  name: string;
  criteria: Record<string, unknown>;
  score: number;
  factors: Record<string, number>;
  status: ICPStatus;
  created_by: string;
}

export interface Company {
  id: string;
  workspace_id: string;
  product_id: string;
  name: string;
  website: string;
  industry: string;
  country: string;
  employee_estimate: string;
  funding_stage: string;
  funding_amount: string;
  technology_signals: string[];
  growth_signals: string[];
  potential_pain: string;
  icp_fit_score: number;
  icp_fit_category: CompanyFitCategory;
  manual_score_override: number | null;
  evidence_ids: string[];
  source_urls: string[];
  confidence: EvidenceStatus;
  pipeline_stage: PipelineStage;
}

export interface CompanyTrigger {
  id: string;
  company_id: string;
  trigger_type: string;
  description: string;
  trigger_date: string | null;
  source_url: string;
  confidence: number;
  relevance_score: number;
  product_fit_score: number;
  why_it_matters: string;
}

export interface Contact {
  id: string;
  company_id: string;
  name: string;
  role: string;
  public_profile_url: string;
  email: string;
  source: string;
  confidence: EvidenceStatus;
  pipeline_stage: PipelineStage;
}

export interface Investor {
  id: string;
  fund_name: string;
  investor_name: string;
  investor_type: string;
  website: string;
  stage: string[];
  geography: string[];
  sector: string[];
  thesis: string;
  portfolio: string[];
  recent_investments: string[];
  check_size_min: string;
  check_size_max: string;
  partner: string;
  contact_channel: string;
  source_url: string;
  confidence: number;
  is_demo: boolean;
}

export interface InvestorMatch {
  id: string;
  product_id: string;
  investor_id: string;
  fit_score: number;
  reasons: { reason: string; factor: string }[];
  factors: Record<string, number>;
}

export interface Opportunity {
  id: string;
  workspace_id: string;
  product_id: string;
  type: OpportunityType;
  title: string;
  description: string;
  status: string;
  audience: string;
  reach_estimate: string;
  submission_method: string;
  cost: string;
  deadline: string | null;
  promotion_rules: string;
}

export interface Campaign {
  id: string;
  workspace_id: string;
  product_id: string;
  name: string;
  goal: string;
  audience_description: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
}

export interface CampaignMetric {
  id: string;
  campaign_id: string;
  channel: string;
  metric_date: string;
  reach: number;
  visitors: number;
  signups: number;
  conversions: number;
  responses: number;
  meetings: number;
  attribution: string;
  source_detail: string;
}

export interface ContentVariant {
  id: string;
  content_id: string;
  channel: string;
  body: string;
  status: ContentStatus;
  media_refs: string[];
  performance: Record<string, number>;
  approved_by: string | null;
  approved_at: string | null;
  published_at: string | null;
  platform_format: string;
  cta: string;
  scheduled_at: string | null;
  rejected_reason: string;
  quality_flags: { blocking_reasons?: string[]; warnings?: string[] };
  video_id: string | null;
}

export interface ContentItem {
  id: string;
  workspace_id: string;
  product_id: string;
  idea: string;
  status: ContentStatus;
  source_idea_id: string | null;
  content_type: string;
  origin: string;
  campaign_id: string | null;
  variants: ContentVariant[];
}

export interface Video {
  id: string;
  workspace_id: string;
  product_id: string;
  content_variant_id: string | null;
  script: { hook?: string; problem?: string; insight?: string; solution?: string; product?: string; cta?: string };
  aspect_ratio: string;
  duration_seconds: number;
  has_voiceover: boolean;
  storage_url: string;
  status: VideoStatus;
  render_log: string;
  rendered_at: string | null;
}

export interface OutreachMessage {
  id: string;
  outreach_id: string;
  draft_body: string;
  personalization_evidence: { field: string; value: string }[];
  status: OutreachMessageStatus;
}

export interface Outreach {
  id: string;
  workspace_id: string;
  product_id: string;
  target_type: string;
  target_id: string;
  channel: string;
  status: PipelineStage;
  messages: OutreachMessage[];
}

export interface Competitor {
  id: string;
  workspace_id: string;
  product_id: string;
  name: string;
  website: string;
  notes: string;
  last_scanned_at: string | null;
}

export interface CompetitorChange {
  id: string;
  competitor_id: string;
  change_type: string;
  description: string;
  detected_at: string;
  source_url: string;
  potential_impact: string;
  recommended_response: string;
}

export interface BrandMention {
  id: string;
  workspace_id: string;
  product_id: string;
  keyword: string;
  source_url: string;
  excerpt: string;
  category: MentionCategory;
  relevance_score: number;
  recommended_action: string;
  detected_at: string;
}

export interface ActionItem {
  id: string;
  workspace_id: string;
  product_id: string;
  title: string;
  description: string;
  category: ActionCategory;
  why: string;
  impact: string;
  effort: string;
  evidence_ids: string[];
  expected_value_score: number;
  status: ActionStatus;
  requires_approval: boolean;
  related_entity_type: string;
  related_entity_id: string | null;
  deadline: string | null;
}

export interface BrandBrain {
  id: string;
  workspace_id: string;
  product_id: string | null;
  voice: string;
  tone: string;
  positioning: string;
  key_messages: string[];
  words_to_use: string[];
  words_to_avoid: string[];
  claims: string[];
  proof_points: string[];
  founder_story: string;
  product_facts: string[];
}

export interface LearningInsight {
  id: string;
  workspace_id: string;
  product_id: string;
  dimension: string;
  hypothesis: string;
  sample_size: number;
  result_summary: { group?: string; group_rate?: number; baseline_rate?: number; lift?: number; total_sample_size?: number };
  confidence: number;
  status: LearningInsightStatus;
}

export interface ResearchRun {
  id: string;
  workspace_id: string;
  product_id: string | null;
  run_type: string;
  status: string;
  query: string;
  result_summary: Record<string, unknown>;
  error: string;
}

export interface IntegrationCatalogEntry {
  provider_name: string;
  provider_type: string;
  configured: boolean;
  connected: boolean;
  capabilities: Record<string, unknown>;
  notes: string;
}

export interface DashboardAnalytics {
  qualified_prospects: number;
  outreach_sent: number;
  outreach_replied: number;
  meetings: number;
  customers_won: number;
  investor_conversations: number;
  open_opportunities: number;
  actions_today: number;
}
