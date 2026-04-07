# Lessons Learned: Frontend Visibility Issue

## Problem
The menu item "KI-Analyse (Beta)" was not visible in the sidebar, even though the code was updated.

## Root Cause
1.  **Silent Build Failure**: A TypeScript error in `AnalysisPage.tsx` (unused `useEffect` import) caused `npm run build` to fail within the Docker build process.
2.  **Stale Image**: Docker Compose continued to use the previous successful image (v2.0.14-esc-support) because the new build failed, leading to the user seeing an old version of the app.
3.  **Missing Backend Info**: Initially, the backend did not provide enough role information (`tenants` list) for the frontend to correctly identify a `platform_admin` who wasn't a `is_superuser`.

## Solution
1.  **Backend**: Extended `/api/v1/auth/me` to include tenant roles.
2.  **Frontend Logic**: Updated `isAdmin` check in `AppLayout.tsx` to use the new tenant role data.
3.  **Frontend Fix**: Removed the unused import in `AnalysisPage.tsx` to fix the build.
4.  **Verification**: Forced a rebuild with `docker compose up -d --build frontend` and verified the build logs.

## Rule for the future
Always check the Docker build logs for "FAILED" steps, even if the container seems to start. Use `--build` to ensure the latest code is compiled.
