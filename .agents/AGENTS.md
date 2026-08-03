# Front-End Validation Protocol

Whenever making changes to the front-end code (e.g. React components, UI structure, App.tsx, etc.), you MUST ALWAYS:
1. Run the TypeScript compiler (`npx tsc --noEmit`) to verify there are no syntax or typing errors.
2. Run the linter (`npm run lint` or equivalent) to catch code quality issues.
3. Run tests if they are configured.

Do not assume the code is correct without running these verification steps. Maintaining the app's integrity is the highest priority.
