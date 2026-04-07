# Heizungsleser V2 - ADR 0001: Stack-Entscheidung

## Status
Akzeptiert

## Kontext
Für das Projekt „Heizungsleser V2“ wird ein moderner, wartbarer und performanter Backend-Stack benötigt, der lokal in Docker Desktop sowie später in einer Multi-Mandanten-Umgebung zuverlässig funktioniert.

## Entscheidung
Wir setzen auf folgenden Stack:

- **Programmiersprache:** Python 3.12 (Aktuell stabil, gute Typunterstützung)
- **Web-Framework:** FastAPI (Performant, asynchron, automatische OpenAPI-Generierung)
- **ORM:** SQLAlchemy 2.0 (Moderner asynchroner Support, Typsicherheit)
- **Datenbank-Migrationen:** Alembic (Standard für SQLAlchemy)
- **Validierung:** Pydantic 2.0 (Schnell, Standard für FastAPI)
- **Relationaler Speicher:** PostgreSQL (Robust, Mandantenfähigkeit via `tenant_id`)
- **Zeitreihen-Speicher:** InfluxDB 3 (Vorgabe durch Bestandssysteme)
- **Authentifizierung:** JWT (JSON Web Tokens)
- **Containerisierung:** Docker & Docker Compose

## Begründung
- **Wartbarkeit:** Die gewählten Bibliotheken sind Industriestandard und verfügen über eine hervorragende Dokumentation und Community-Support.
- **Performance:** FastAPI und SQLAlchemy 2 ermöglichen asynchrone Datenbankzugriffe, was bei vielen gleichzeitigen Anfragen (Multi-Tenancy) von Vorteil ist.
- **Erweiterbarkeit:** Pydantic und SQLAlchemy 2 bieten starke Typisierung, was das Refactoring und die Erweiterung des Datenmodells sicherer macht.
- **Docker-Tauglichkeit:** Alle Komponenten lassen sich problemlos in Docker-Containern betreiben.

## Konsequenzen
- Das Team muss mit asynchroner Programmierung in Python vertraut sein.
- Die InfluxDB 3 Integration muss flexibel genug sein, um mit verschiedenen Schemata umzugehen.
