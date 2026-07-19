"""
Package modèles — définitions Pydantic v2 des entités du domaine.

Entités : Person, Application, Component, Document, Ticket,
Meeting, Decision, Action, BusinessRule.
Toutes les entités conservent une référence temporelle (valid_from / valid_to)
et une référence à leur source originale.
"""
