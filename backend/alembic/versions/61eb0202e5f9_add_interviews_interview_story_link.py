"""add interviews + interview_story link

Migration STRICTEMENT ADDITIVE : elle crée uniquement deux nouvelles tables et
un index. Elle ne touche à aucune table ni donnée existante (offers, contacts,
documents, activities, interview_stories, settings).

- `interviews` : rounds d'entretien rattachés à UNE offre (FK ON DELETE CASCADE).
- `interview_stories_link` : liaison M2M entre `interviews` et la Story Bank
  `interview_stories` (PK composite, FK ON DELETE CASCADE des deux côtés).
  ⚠️ Ne PAS confondre avec `interview_stories` (Story Bank STAR) qui n'est ici
  qu'une cible de FK et reste inchangée.

Le `downgrade` supprime uniquement ces deux nouvelles tables.

Revision ID: 61eb0202e5f9
Revises: a9b5ad225774
Create Date: 2026-07-08 14:46:41.219780

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61eb0202e5f9'
down_revision: Union[str, None] = 'a9b5ad225774'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('interviews',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('offer_id', sa.Integer(), nullable=False),
    sa.Column('round_label', sa.String(length=120), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('interviewer', sa.String(length=200), nullable=True),
    sa.Column('format', sa.String(length=20), nullable=True),
    sa.Column('questions', sa.Text(), nullable=True),
    sa.Column('feeling', sa.Text(), nullable=True),
    sa.Column('next_step', sa.Text(), nullable=True),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interviews_offer_id'), 'interviews', ['offer_id'], unique=False)
    op.create_table('interview_stories_link',
    sa.Column('interview_id', sa.Integer(), nullable=False),
    sa.Column('story_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['story_id'], ['interview_stories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('interview_id', 'story_id')
    )


def downgrade() -> None:
    # Drop des seules nouvelles tables (liaison d'abord), rien d'autre.
    op.drop_table('interview_stories_link')
    op.drop_index(op.f('ix_interviews_offer_id'), table_name='interviews')
    op.drop_table('interviews')
