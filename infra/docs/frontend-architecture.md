# Frontend Architektur - Heizungsleser V2

Dieses Dokument beschreibt die Architektur des Frontends für Meilenstein 3.

## Übersicht
Das Frontend ist eine moderne Single-Page-Application (SPA) auf Basis von **React** und **Vite**. Es kommuniziert mit dem FastAPI-Backend über eine typsichere REST-API.

## Technischer Stack
- **Framework:** React 18+ mit TypeScript
- **Build-Tool:** Vite
- **Styling:** Tailwind CSS + shadcn/ui (UI-Komponenten)
- **Routing:** React Router 6
- **Server State Management:** TanStack Query (React Query)
- **Charts:** ECharts (leistungsfähig, responsive, gut für Zeitreihen)
- **Validierung:** Zod
- **API-Client:** Typsichere Wrapper um `fetch` oder `axios`, basierend auf der OpenAPI-Spezifikation.

## Verzeichnisstruktur
- `src/api`: API-Definitionen, Hooks (React Query) und Typen.
- `src/components`: Wiederverwendbare UI-Komponenten (Atoms, Molecules).
- `src/features`: Fachliche Module (Auth, Tenants, Devices, Dashboard).
- `src/hooks`: Globale Hooks (z.B. `useAuth`, `useLocalStorage`).
- `src/lib`: Bibliotheks-Konfigurationen (ECharts, shadcn/ui Utils).
- `src/routes`: Routing-Definitionen und Guards.
- `src/types`: Globale TypeScript-Typen.

## Authentifizierungs-Konzept
- JWT-basiert (AccessToken vom Backend).
- Speicherung des Tokens im `sessionStorage` (für Persistenz während der Sitzung).
- Auth-Provider stellt den aktuellen Benutzer und Rollen (`platform_admin`, `tenant_admin`, `tenant_user`) global zur Verfügung.
- Private Routes leiten unauthentifizierte Benutzer zum Login um.

## Navigationsmodell
- **Platform Admin:** Sieht alle Tenants und alle Devices. Kann diese verwalten.
- **Tenant Admin:** Sieht nur den eigenen Tenant und dessen Devices.
- **Tenant User:** Sieht nur die Devices des eigenen Tenants.

## Datenfluss & Zeitreihen
- Daten werden über TanStack Query gecached.
- Zeitreihen-Abfragen erlauben den Vergleich mehrerer Entitäten.
- Die Normalisierung erfolgt bereits im Backend, das Frontend visualisiert die Daten mittels ECharts.

## Dashboard-MVP (Client-Side)
- Da das Backend noch keine Dashboard-Persistenz bietet, werden Dashboard-Konfigurationen (ausgewählte Entitäten pro Device) im `localStorage` gespeichert.
- Die Struktur ist so vorbereitet, dass sie später leicht auf eine API-Anbindung umgestellt werden kann.

## Vorbereitung Meilenstein 4+
- `src/features/reporting`: Platzhalter für PDF/Berichts-Funktionalität.
- `src/features/ai`: Platzhalter für KI-basierte Auswertungen.
