import enum


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class EvidenceStatus(str, enum.Enum):
    FACT = "fact"
    HYPOTHESIS = "hypothesis"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


class ICPStatus(str, enum.Enum):
    AI_HYPOTHESIS = "ai_hypothesis"
    FOUNDER_CONFIRMED = "founder_confirmed"
    ARCHIVED = "archived"


class CompanyFitCategory(str, enum.Enum):
    EXCELLENT = "excellent"     # 90-100
    STRONG = "strong"           # 75-89
    POTENTIAL = "potential"     # 60-74
    LOW_PRIORITY = "low_priority"  # <60


class PipelineStage(str, enum.Enum):
    PROSPECT = "prospect"
    QUALIFIED = "qualified"
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"
    REPLIED = "replied"
    MEETING = "meeting"
    WON = "won"
    LOST = "lost"
    NOT_NOW = "not_now"


class InvestorStage(str, enum.Enum):
    DISCOVERED = "discovered"
    RESEARCHING = "researching"
    SHORTLISTED = "shortlisted"
    CONTACTED = "contacted"
    REPLIED = "replied"
    MEETING = "meeting"
    FOLLOW_UP = "follow_up"
    DUE_DILIGENCE = "due_diligence"
    PASSED = "passed"
    INVESTED = "invested"


class OpportunityType(str, enum.Enum):
    CUSTOMER = "customer"
    INVESTOR = "investor"
    MARKETING = "marketing"
    LAUNCH = "launch"
    COMMUNITY = "community"
    CONTENT = "content"
    PARTNERSHIP = "partnership"
    MEDIA = "media"
    EVENT = "event"
    SEO = "seo"
    GEO = "geo"
    AI_VISIBILITY = "ai_visibility"
    COMPETITOR = "competitor"
    SOCIAL = "social"
    GRANT = "grant"
    ACCELERATOR = "accelerator"
    PODCAST = "podcast"
    NEWSLETTER = "newsletter"
    OTHER = "other"


class ActionStatus(str, enum.Enum):
    TODAY = "today"
    UPCOMING = "upcoming"
    WAITING = "waiting"
    COMPLETED = "completed"
    SNOOZED = "snoozed"


class ActionCategory(str, enum.Enum):
    CUSTOMER = "customer"
    INVESTOR = "investor"
    MARKETING = "marketing"
    CONTENT = "content"
    COMPETITOR = "competitor"
    LAUNCH = "launch"
    VISIBILITY = "visibility"


class ContentStatus(str, enum.Enum):
    IDEA = "idea"
    GENERATING = "generating"
    DRAFT = "draft"
    READY = "ready"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class OutreachMessageStatus(str, enum.Enum):
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"
    REJECTED = "rejected"


class MentionCategory(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    QUESTION = "question"
    PURCHASE_INTENT = "purchase_intent"
    COMPETITOR_COMPARISON = "competitor_comparison"
    FEEDBACK = "feedback"


class ResearchSourceType(str, enum.Enum):
    WEBPAGE = "webpage"
    RSS = "rss"
    ATOM = "atom"
    API = "api"
    SITEMAP = "sitemap"
    USER_SUBMITTED = "user_submitted"
    OFFICIAL_INTEGRATION = "official_integration"


class IntegrationProviderType(str, enum.Enum):
    SEARCH = "search"
    EMAIL = "email"
    SOCIAL = "social"
    ANALYTICS = "analytics"
    CRM = "crm"
    ENRICHMENT = "enrichment"
    GIT = "git"
    DEPLOYMENT = "deployment"


class IntegrationStatus(str, enum.Enum):
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# ---- Visibility module -------------------------------------------------


class ConfidenceLabel(str, enum.Enum):
    """How sure we are about a scanned/measured fact (§6, §45 of the
    original spec's anti-hallucination principle, extended to website
    analysis)."""

    VERIFIED = "verified"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OptimizationMode(str, enum.Enum):
    ANALYZE_ONLY = "analyze_only"
    PROPOSE = "propose"
    PREPARE = "prepare"
    AUTONOMOUS = "autonomous"  # modeled but rejected by the API — disabled by default, not implemented


class WebsiteChangeStatus(str, enum.Enum):
    DRAFTED = "drafted"
    VALIDATED = "validated"
    BLOCKED = "blocked"
    APPROVED = "approved"
    BRANCH_CREATED = "branch_created"
    PR_CREATED = "pr_created"
    MERGED = "merged"
    REJECTED = "rejected"


class OpportunityCoverage(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WebsiteOpportunityStatus(str, enum.Enum):
    OPEN = "open"
    PROPOSED = "proposed"
    REJECTED = "rejected"
    COMPLETED = "completed"


class VisibilityCoverageStatus(str, enum.Enum):
    MENTIONED = "mentioned"
    NOT_DETECTED = "not_detected"


# ---- Autonomous growth engine -------------------------------------------


class LearningInsightStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IGNORED = "ignored"
