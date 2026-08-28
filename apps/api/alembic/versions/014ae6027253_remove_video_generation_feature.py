"""remove_video_generation_feature

Revision ID: 014ae6027253
Revises: 6b28d71118dc
Create Date: 2026-08-28 20:44:16.604766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '014ae6027253'
down_revision: Union[str, None] = '6b28d71118dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Video generation feature removed — drop everything added for it while
    # keeping the content-strategy columns (content_type/origin/campaign_id,
    # platform_format/cta/scheduled_at/rejected_reason/quality_flags) that
    # the rest of the content engine still uses.
    op.drop_constraint('content_variants_video_id_fkey', 'content_variants', type_='foreignkey')
    op.drop_column('content_variants', 'video_id')
    op.drop_index('ix_video_brand_kits_workspace_id', table_name='video_brand_kits')
    op.drop_index('ix_video_brand_kits_product_id', table_name='video_brand_kits')
    op.drop_table('video_brand_kits')
    op.drop_index('ix_videos_workspace_id', table_name='videos')
    op.drop_index('ix_videos_product_id', table_name='videos')
    op.drop_table('videos')


def downgrade() -> None:
    op.create_table('videos',
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('content_variant_id', sa.Uuid(), nullable=True),
    sa.Column('script', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('aspect_ratio', sa.String(length=10), nullable=False),
    sa.Column('duration_seconds', sa.Float(), nullable=False),
    sa.Column('has_voiceover', sa.Boolean(), nullable=False),
    sa.Column('storage_url', sa.String(length=1000), nullable=False),
    sa.Column('status', sa.Enum('SCRIPT_READY', 'RENDERING', 'READY', 'FAILED', name='videostatus', native_enum=False, length=20), nullable=False),
    sa.Column('render_log', sa.Text(), nullable=False),
    sa.Column('brand_kit_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('rendered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['content_variant_id'], ['content_variants.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_videos_product_id'), 'videos', ['product_id'], unique=False)
    op.create_index(op.f('ix_videos_workspace_id'), 'videos', ['workspace_id'], unique=False)
    op.create_table('video_brand_kits',
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=True),
    sa.Column('primary_color', sa.String(length=7), nullable=False),
    sa.Column('secondary_color', sa.String(length=7), nullable=False),
    sa.Column('background_color', sa.String(length=7), nullable=False),
    sa.Column('text_color', sa.String(length=7), nullable=False),
    sa.Column('font_family', sa.String(length=100), nullable=False),
    sa.Column('logo_url', sa.String(length=500), nullable=False),
    sa.Column('product_screenshot_url', sa.String(length=500), nullable=False, server_default=''),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_brand_kits_product_id'), 'video_brand_kits', ['product_id'], unique=False)
    op.create_index(op.f('ix_video_brand_kits_workspace_id'), 'video_brand_kits', ['workspace_id'], unique=False)
    op.add_column('content_variants', sa.Column('video_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('content_variants_video_id_fkey', 'content_variants', 'videos', ['video_id'], ['id'], ondelete='SET NULL')
