"""
conftest.py — Fixtures partagées entre tous les tests
Génère des fichiers de test légers à la volée (PDF, TXT, DOCX).
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_pdf_path(tmp_path_factory) -> Path:
    """PDF de test minimal généré avec PyMuPDF."""
    import pymupdf as fitz

    tmp = tmp_path_factory.mktemp("fixtures")
    path = tmp / "test_doc.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (50, 80),
        (
            "Guide de test — Documentation technique\n\n"
            "Section 1 : Introduction\n"
            "Ceci est un document de test pour valider le pipeline RAG.\n"
            "Il contient du texte factice servant aux tests unitaires.\n\n"
            "Section 2 : Spring Boot\n"
            "Spring Boot est un framework Java pour créer des applications web.\n"
            "Il simplifie la configuration et le déploiement.\n\n"
            "Section 3 : Conclusion\n"
            "Les tests unitaires garantissent la qualité du code.\n"
            "Chaque composant doit être testé indépendamment.\n"
        ),
        fontsize=11,
    )
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def test_txt_path(tmp_path_factory) -> Path:
    """Fichier texte de test."""
    tmp = tmp_path_factory.mktemp("fixtures")
    path = tmp / "test_doc.txt"
    path.write_text(
        "Règlement intérieur — Ressources Humaines\n\n"
        "Article 1 : Horaires de travail\n"
        "Les collaborateurs travaillent du lundi au vendredi, de 9h à 18h.\n"
        "Des aménagements d'horaires peuvent être accordés sur demande.\n\n"
        "Article 2 : Congés payés\n"
        "Chaque salarié bénéficie de 25 jours de congés payés par an.\n"
        "Les congés doivent être posés avec un préavis d'au moins 2 semaines.\n\n"
        "Article 3 : Télétravail\n"
        "Le télétravail est autorisé jusqu'à 2 jours par semaine.\n"
        "Un accord écrit avec le manager est requis.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture(scope="session")
def sample_documents(test_pdf_path):
    """Documents LangChain issus du PDF de test."""
    from src.loader import extract_text_from_pdf, pages_to_documents

    pages = extract_text_from_pdf(test_pdf_path)
    return pages_to_documents(pages, "technique", test_pdf_path.name)
