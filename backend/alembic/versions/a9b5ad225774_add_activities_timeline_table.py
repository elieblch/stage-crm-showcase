"""add activities timeline table

Table `activities` : journal d'événements append-only rattaché à UNE offre OU
UN contact (contrainte CHECK). Migration strictement additive : elle ne touche
à aucune donnée existante et ne supprime aucune colonne.

Le seed est idempotent (guardé par NOT EXISTS) : pour chaque offre / contact
sans historique, il crée un événement initial afin que la timeline ne soit pas
vide. Il n'INSÈRE que des lignes `activities`, il ne modifie aucune offre ni
aucun contact.

Revision ID: a9b5ad225774
Revises: ec7f62a56ae8
Create Date: 2026-07-07 13:28:51.368849

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b5ad225774'
down_revision: Union[str, None] = 'ec7f62a56ae8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'activities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('offer_id', sa.Integer(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('activity_type', sa.String(length=30), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.CheckConstraint(
            '(offer_id IS NOT NULL AND contact_id IS NULL) '
            'OR (offer_id IS NULL AND contact_id IS NOT NULL)',
            name='ck_activities_exactly_one_parent',
        ),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_activities_contact_id'), 'activities', ['contact_id'], unique=False)
    op.create_index(op.f('ix_activities_offer_id'), 'activities', ['offer_id'], unique=False)

    # ── Seed additif idempotent ───────────────────────────────────────────
    # Offres sans historique → événement initial (`applied` si une candidature
    # a été envoyée, sinon un marqueur neutre daté de date_added).
    op.execute(
        """
        INSERT INTO activities (offer_id, activity_type, event_date, note, created_at)
        SELECT o.id,
               CASE WHEN o.date_applied IS NOT NULL THEN 'applied' ELSE 'other' END,
               COALESCE(o.date_applied, o.date_added),
               CASE WHEN o.date_applied IS NOT NULL
                    THEN 'Candidature envoyée'
                    ELSE 'Offre ajoutée au tracker' END,
               now()
        FROM offers o
        WHERE NOT EXISTS (SELECT 1 FROM activities a WHERE a.offer_id = o.id);
        """
    )
    # Contacts sans historique → `contacted` si un premier contact a eu lieu,
    # sinon un marqueur neutre daté de la création de la fiche.
    op.execute(
        """
        INSERT INTO activities (contact_id, activity_type, event_date, note, created_at)
        SELECT c.id,
               CASE WHEN c.date_first_contact IS NOT NULL THEN 'contacted' ELSE 'other' END,
               COALESCE(c.date_first_contact, c.created_at::date),
               CASE WHEN c.date_first_contact IS NOT NULL
                    THEN 'Premier contact'
                    ELSE 'Contact ajouté au tracker' END,
               now()
        FROM contacts c
        WHERE NOT EXISTS (SELECT 1 FROM activities a WHERE a.contact_id = c.id);
        """
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_activities_offer_id'), table_name='activities')
    op.drop_index(op.f('ix_activities_contact_id'), table_name='activities')
    op.drop_table('activities')
