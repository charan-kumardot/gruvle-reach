"""
Demo data seed script (§75-76). Creates an isolated demo organization/
workspace/product ("Gruvle Radar") with clearly-marked synthetic data so the
product can be explored without live AI/search calls. Every synthetic
record is prefixed "[DEMO]" and/or has is_demo=True — never write demo data
into a real user's workspace, and never let this script touch a non-demo
workspace.

Usage (from apps/api, with the venv active):
    python ../../scripts/seed_demo.py
"""
import datetime as dt
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.core.security import hash_password  # noqa: E402
from app.db.models.action import Action  # noqa: E402
from app.db.models.brand import BrandMention  # noqa: E402
from app.db.models.company import Company, CompanySignal, CompanyTrigger, Contact  # noqa: E402
from app.db.models.competitor import Competitor, CompetitorChange  # noqa: E402
from app.db.models.enums import (  # noqa: E402
    ActionCategory,
    ActionStatus,
    CompanyFitCategory,
    EvidenceStatus,
    ICPStatus,
    MentionCategory,
    OpportunityType,
    OrgRole,
)
from app.db.models.investor import Investor, InvestorInteraction, InvestorMatch  # noqa: E402
from app.db.models.opportunity import Opportunity  # noqa: E402
from app.db.models.product import BrandBrain, ICPProfile, Product, ProductProfile  # noqa: E402
from app.db.models.tenancy import Organization, OrganizationMember, User, Workspace  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

DEMO_EMAIL = "demo@gruvle-reach.io"
DEMO_PASSWORD = "demo12345"

now = dt.datetime.now(dt.timezone.utc)


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Organization).filter(Organization.slug == "gruvle-demo").one_or_none()
        if existing is not None:
            print(f"Demo org already exists (id={existing.id}). Delete it first if you want to reseed.")
            return

        user = db.query(User).filter(User.email == DEMO_EMAIL).one_or_none()
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), full_name="Demo Founder")
            db.add(user)
            db.flush()

        org = Organization(name="Gruvle (Demo)", slug="gruvle-demo")
        db.add(org)
        db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

        workspace = Workspace(organization_id=org.id, name="[DEMO] Gruvle Workspace", slug="demo", is_demo=True)
        db.add(workspace)
        db.flush()

        product = Product(
            workspace_id=workspace.id,
            name="Gruvle Radar",
            website="https://gruvle.com",
            description="AI-powered change intelligence for businesses — detects and explains what changed across your stack before it causes an incident.",
            category="B2B SaaS",
            target_markets=["B2B SaaS companies", "AI companies", "API-heavy businesses"],
            target_countries=["United States", "Global"],
            pricing="Usage-based, from $199/mo",
            business_model="SaaS subscription",
            stage="Early launch",
            competitors=["Datadog", "PagerDuty", "Statuspage"],
            differentiators=["AI-explained root cause, not just alerts", "Change-first (not just metrics/logs)"],
            brand_voice="Direct, technical, founder-authentic — no hype.",
            cta="Start free trial",
            launch_status="early_launch",
            is_demo=True,
        )
        db.add(product)
        db.flush()

        db.add(
            ProductProfile(
                product_id=product.id,
                product_category="AI-driven change intelligence / observability",
                primary_problem="Engineering teams can't quickly tell which recent change caused an incident.",
                primary_buyer="VP Engineering / Head of Platform",
                secondary_buyers=["SRE", "CTO", "DevOps Lead"],
                target_industries=["B2B SaaS", "AI/ML platforms", "FinTech"],
                use_cases=["Root-cause analysis", "Change-risk scoring", "Post-incident review"],
                competitive_categories=["Observability", "APM", "Incident management"],
                keywords=["change intelligence", "observability", "incident prevention"],
                search_queries=["[DEMO] AI change intelligence platforms", "[DEMO] B2B SaaS observability tools"],
                raw_ai_output={"demo": True},
            )
        )

        icp = ICPProfile(
            product_id=product.id,
            name="[DEMO] US B2B SaaS, 20-200 employees, using Stripe + OpenAI",
            criteria={
                "industries": ["B2B SaaS"],
                "company_size_min": 20,
                "company_size_max": 200,
                "geographies": ["United States"],
                "technology_stack": ["Stripe", "OpenAI", "Kubernetes"],
                "funding_stages": ["Seed", "Series A"],
            },
            score=92.0,
            factors={"pain": 90, "ability_to_pay": 85, "reachability": 80, "product_fit": 95, "urgency": 88, "market_size": 75, "competition": 60},
            status=ICPStatus.FOUNDER_CONFIRMED,
            created_by="founder",
        )
        db.add(icp)

        db.add(
            BrandBrain(
                workspace_id=workspace.id,
                product_id=product.id,
                voice="Direct, technical, founder-authentic",
                tone="Confident but not hypey",
                positioning="The AI system that tells you what changed and why it broke something — before your customers notice.",
                key_messages=["Change is the #1 cause of incidents", "AI-explained, not just AI-detected"],
                words_to_use=["change intelligence", "root cause", "before it breaks"],
                words_to_avoid=["revolutionary", "game-changing", "disrupt"],
                claims=["[DEMO] Detects the top 5 change types that cause outages"],
                proof_points=["[DEMO] Early design partners report faster incident triage"],
                founder_story="[DEMO] Built after one too many 3am pages caused by an undocumented config change.",
                product_facts=["[DEMO] Ingests deploy, config, and infra change events", "[DEMO] Works with GitHub, Kubernetes, Terraform"],
            )
        )

        companies_data = [
            ("[DEMO] XYZ SaaS", "https://xyz-saas-demo.example", "B2B SaaS", "United States", "50-100", "Series A", 94.0, CompanyFitCategory.EXCELLENT, "Recently launched an AI feature — likely increasing infra complexity and incident risk."),
            ("[DEMO] Northwind Analytics", "https://northwind-demo.example", "Data/Analytics SaaS", "United States", "20-50", "Seed", 81.0, CompanyFitCategory.STRONG, "Fast-growing engineering team, hiring several SREs."),
            ("[DEMO] Fintra Labs", "https://fintra-demo.example", "FinTech", "United States", "100-200", "Series B", 68.0, CompanyFitCategory.POTENTIAL, "Regulated environment — change auditability could be a strong fit."),
        ]
        companies = []
        for name, website, industry, country, emp, funding, score, category, pain in companies_data:
            c = Company(
                workspace_id=workspace.id,
                product_id=product.id,
                name=name,
                website=website,
                industry=industry,
                country=country,
                employee_estimate=emp,
                funding_stage=funding,
                potential_pain=pain,
                icp_fit_score=score,
                icp_fit_category=category,
                icp_fit_factors={"icp_match": score, "technology_fit": 80, "growth": 75, "funding": 70},
                source_urls=[website],
                confidence=EvidenceStatus.HYPOTHESIS,
            )
            db.add(c)
            db.flush()
            companies.append(c)
            db.add(CompanySignal(company_id=c.id, signal_type="product_launch", description="[DEMO] Announced new AI feature", source_url=website, confidence=0.7, detected_at=now))

        db.add(
            CompanyTrigger(
                company_id=companies[0].id,
                trigger_type="product_launch",
                description="[DEMO] Launched an AI-powered feature",
                trigger_date=(now - dt.timedelta(days=7)).date(),
                source_url=companies[0].website,
                evidence_snippet="[DEMO] 'We're excited to launch our new AI copilot...'",
                confidence=0.8,
                relevance_score=90.0,
                product_fit_score=94.0,
                why_it_matters="New AI features increase infra dependency surface — higher chance of change-related incidents.",
            )
        )

        db.add(Contact(workspace_id=workspace.id, company_id=companies[0].id, name="[DEMO] Jordan Lee", role="CTO", source="[DEMO] company team page", confidence=EvidenceStatus.HYPOTHESIS))

        investor = Investor(
            fund_name="[DEMO] ABC Ventures",
            investor_name="[DEMO] Alex Rivera",
            investor_type="vc",
            website="https://abc-ventures-demo.example",
            stage=["Seed", "Series A"],
            geography=["United States"],
            sector=["B2B SaaS", "AI infrastructure", "Developer tools"],
            thesis="[DEMO] Backs technical founders building infrastructure for the AI era.",
            portfolio=["[DEMO] Datadog-adjacent startup", "[DEMO] DevOps tool"],
            recent_investments=["[DEMO] Invested in an observability startup 3 months ago"],
            check_size_min="$500K",
            check_size_max="$3M",
            partner="[DEMO] Alex Rivera",
            source_url="https://abc-ventures-demo.example",
            confidence=0.6,
            is_demo=True,
        )
        db.add(investor)
        db.flush()

        db.add(
            InvestorMatch(
                workspace_id=workspace.id,
                product_id=product.id,
                investor_id=investor.id,
                fit_score=91.0,
                reasons=[
                    {"reason": "Invests in AI infrastructure", "factor": "sector_fit"},
                    {"reason": "Seed/Series A stage match", "factor": "stage_fit"},
                    {"reason": "Recently invested in an adjacent observability startup", "factor": "recent_activity"},
                ],
                factors={"sector_fit": 90, "stage_fit": 90, "geography": 100, "portfolio_relevance": 80, "recent_activity": 85},
            )
        )
        db.add(InvestorInteraction(workspace_id=workspace.id, product_id=product.id, investor_id=investor.id, notes="[DEMO] Warm intro available via mutual connection."))

        db.add(
            Opportunity(
                workspace_id=workspace.id,
                product_id=product.id,
                type=OpportunityType.LAUNCH,
                title="[DEMO] Launch on Product Hunt",
                description="Prepare a Product Hunt launch kit — strong fit given the developer-tool audience overlap.",
                audience="Developers, SREs, platform engineers",
                submission_method="Manual submission via producthunt.com",
                status="open",
            )
        )
        db.add(
            Opportunity(
                workspace_id=workspace.id,
                product_id=product.id,
                type=OpportunityType.CONTENT,
                title="[DEMO] Publish a LinkedIn post on change-related outages",
                description="Founder-voice post about the '3am page caused by an undocumented change' story.",
                status="open",
            )
        )

        competitor = Competitor(workspace_id=workspace.id, product_id=product.id, name="[DEMO] Datadog", website="https://www.datadoghq.com", notes="Adjacent — strong in metrics/logs, weaker in change-specific root cause.")
        db.add(competitor)
        db.flush()
        db.add(
            CompetitorChange(
                competitor_id=competitor.id,
                change_type="feature",
                description="[DEMO] Added an AI-powered monitoring summary feature",
                detected_at=now,
                source_url=competitor.website,
                potential_impact="high",
                recommended_response="Review differentiation messaging around change-specific root cause vs. general AI summaries.",
            )
        )

        db.add(
            BrandMention(
                workspace_id=workspace.id,
                product_id=product.id,
                keyword="Gruvle Radar",
                source_url="https://forum-demo.example/thread/1",
                source_type="webpage",
                excerpt="[DEMO] 'What tools do people use to monitor API changes?'",
                category=MentionCategory.QUESTION,
                relevance_score=88.0,
                recommended_action="Reply with an educational answer referencing change intelligence.",
                detected_at=now,
            )
        )

        db.add(
            Action(
                workspace_id=workspace.id,
                product_id=product.id,
                title="[DEMO] Contact XYZ SaaS",
                description="XYZ SaaS scored 94/100 fit and just launched an AI feature.",
                category=ActionCategory.CUSTOMER,
                why="Recent AI feature launch increases infra dependency and incident risk.",
                impact="high",
                effort="low",
                expected_value_score=94.0,
                status=ActionStatus.TODAY,
                related_entity_type="company",
                related_entity_id=companies[0].id,
            )
        )
        db.add(
            Action(
                workspace_id=workspace.id,
                product_id=product.id,
                title="[DEMO] Follow up with ABC Ventures",
                description="91/100 investor fit — recently invested in an adjacent observability startup.",
                category=ActionCategory.INVESTOR,
                why="High computed fit score across sector/stage/geography.",
                impact="high",
                effort="medium",
                expected_value_score=91.0,
                status=ActionStatus.TODAY,
            )
        )

        db.commit()
        print(f"Demo org created: org_id={org.id} workspace_id={workspace.id} product_id={product.id}")
        print(f"Login with: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
