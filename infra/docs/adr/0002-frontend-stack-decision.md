# ADR 0002: Entscheidung für Frontend-Stack - Heizungsleser V2

## Status
Akzeptiert

## Datum
2026-03-27

## Kontext
Für das Projekt „Heizungsleser V2“ wird ein modernes Frontend benötigt, das mit dem bereits existierenden FastAPI-Backend kommuniziert. Die Anwendung muss für Heizungsbauer intuitiv bedienbar sein und komplexe Zeitreihendaten visualisieren können.

## Entscheidung
Wir entscheiden uns für folgenden Frontend-Stack:
1. **React 18+** als UI-Framework.
2. **TypeScript** für Typsicherheit und bessere Wartbarkeit.
3. **Vite** als Build-Tool und Entwicklungs-Server.
4. **React Router 6** für das clientseitige Routing.
5. **TanStack Query (React Query)** für das Management des Server-States.
6. **Tailwind CSS** für effizientes Styling.
7. **shadcn/ui** als Basis für hochwertige, barrierefreie UI-Komponenten.
8. **ECharts** als Charting-Library.

## Begründung
- **Wartbarkeit:** React und Vite bieten ein exzellentes Ökosystem und hohe Entwicklerproduktivität.
- **Performance:** Vite ermöglicht extrem schnelle Build-Zeiten. React Query optimiert die API-Kommunikation durch Caching und effizientes Re-Fetching.
- **Typsicherheit:** TypeScript minimiert Laufzeitfehler durch statische Typen, besonders wichtig bei der Interaktion mit der Backend-API.
- **UX für Heizungsbauer:** Tailwind CSS und shadcn/ui erlauben eine schnelle Entwicklung einer klaren, modernen und mobiltauglichen Benutzeroberfläche.
- **Datenvisualisierung:** ECharts ist hochperformant bei großen Zeitreihen, bietet out-of-the-box Responsive-Support und umfangreiche Interaktionsmöglichkeiten (Zoom, Tooltips, Vergleiche).
- **Separation of Concerns:** Da bereits ein Backend existiert, ist eine SPA-Architektur (Client-Side Rendering) die sauberste und am einfachsten zu implementierende Lösung.

## Alternativen
- **Next.js:** Wurde erwogen, aber da kein Bedarf für Server-Side Rendering (SSR) besteht und das Backend separat in FastAPI implementiert ist, würde es unnötige Komplexität einführen.
- **Vue / Angular:** Ebenfalls möglich, aber React hat das größere Ökosystem für spezialisierte Bibliotheken wie shadcn/ui.
- **Recharts / Chart.js:** Gute Bibliotheken, aber ECharts bietet eine bessere Performance und mehr Features für komplexe industrielle Datenvisualisierungen.

## Konsequenzen
- Das Frontend muss als separater Docker-Container im `docker-compose.yml` konfiguriert werden.
- Die API-Typen sollten idealerweise aus der OpenAPI-Spezifikation abgeleitet werden.
- CORS-Einstellungen im Backend wurden bereits für die Frontend-Integration vorbereitet.
