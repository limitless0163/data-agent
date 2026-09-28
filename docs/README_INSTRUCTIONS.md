# README Instructions

Inspect the entire repository before writing any documentation.

Create or update:

- `README.md` — main English GitHub README
- `README_zh.md` — Chinese version of the main README
- `frontend/README.md` — frontend technical documentation
- `backend/README.md` — backend technical documentation

## General Rules

- Base everything on the actual repository.
- Never invent features, commands, ports, dependencies, versions, paths, configuration, architecture, URLs, or screenshots.
- Keep documentation concise, factual, well-structured, and easy to scan.
- Remove outdated, duplicated, or unnecessary content.
- Prefer short paragraphs, bullet lists, tables, directory trees, diagrams, and runnable code blocks.
- Use GitHub-compatible Markdown and HTML only.
- Verify every technical claim, command, and path against the repository before finishing.

---

## Root README

The root README is the project's **GitHub landing page**, not an exhaustive technical manual.

It should let a visitor understand within seconds:

1. What the project is.
2. What problem it solves.
3. What its main features are.
4. What technologies it uses.
5. How the system works at a high level.
6. How to run it quickly.

Keep it polished, visually clean, concise, and suitable for a public open-source repository.

### Header

Use a centered header.

Include:

- Project name
- One short tagline
- Language switch
- Optional meaningful badges if supported by the repository

Example structure:

```html
<h1 align="center">Project Name</h1>

<p align="center">
  Short project description.
</p>

<p align="center">
  <a href="./README.md">English</a> |
  <a href="./README_zh.md">简体中文</a>
</p>
```

`README.md` must be the default English version.

`README_zh.md` must mirror the same structure and information in Chinese.

Do not maintain different technical content between the two versions.

### Recommended Structure

Adapt sections to the actual project and omit irrelevant ones.

Prefer this order:

1. Header
2. Overview
3. Key Features
4. Tech Stack
5. Architecture
6. Quick Start
7. Project Structure
8. Development / Common Commands
9. Documentation
10. License, if present

Do not add sections only to make the README longer.

### Overview

Explain the project in 1–2 short paragraphs.

Clearly state:

- what it does;
- who or what it is for;
- its core workflow or value.

Avoid generic marketing language.

### Key Features

List only the project's most important capabilities.

Use short bullets.

Do not describe implementation details here unless necessary to understand the feature.

### Tech Stack

Show only technologies actually used by the project.

Prefer a compact, visually clean presentation using recognizable technology badges/icons where appropriate.

For example:

```html
<p>
  <img src="..." alt="Python">
  <img src="..." alt="FastAPI">
  <img src="..." alt="Next.js">
</p>
```

Use stable GitHub-compatible badge/icon sources such as Shields.io or Simple Icons.

Do not add technologies merely because they are common for this type of project.

Group technologies when useful, such as:

- Frontend
- Backend
- Agent / AI
- Database / Search
- Infrastructure
- Testing

Keep the section compact.

### Architecture

Explain only the high-level architecture.

Prefer a small Mermaid diagram or concise flow diagram when it improves understanding.

Do not expose excessive internal implementation details.

Move detailed backend/frontend architecture to their respective README files.

### Quick Start

Provide the shortest verified path from clone to running application.

Prefer:

```bash
git clone ...
cd ...
cp .env.example .env
...
```

Only include commands verified from the repository.

Keep advanced configuration out of this section.

### Project Structure

Show only important top-level directories and files.

Do not dump the entire repository tree.

Example:

```text
.
├── frontend/       # Web application
├── backend/        # API and Agent services
├── tests/          # Cross-system tests
├── docs/           # Documentation
└── docker-compose.yml
```

### Development

Show only the most useful project-level commands.

Prefer a small table.

Detailed frontend/backend commands belong in their module README files.

### Documentation

Link to detailed documentation instead of duplicating it.

At minimum, when present:

- `frontend/README.md`
- `backend/README.md`
- `AGENTS.md`
- testing or architecture documentation

### Content to Avoid in Root README

Unless essential to first-time setup, do not place detailed material such as:

- exhaustive environment-variable tables;
- complete API contracts;
- every internal service;
- detailed database schemas;
- implementation-level request flows;
- exhaustive Docker configuration;
- internal class/function descriptions;
- long testing explanations;
- operational troubleshooting;
- duplicated frontend/backend documentation.

Link to dedicated documentation instead.

Aim for a README that feels like a polished open-source project homepage rather than an internal engineering manual.

---

## Frontend README

`frontend/README.md` is technical documentation for frontend developers.

Include only repository-supported sections such as:

- purpose;
- technology stack;
- prerequisites;
- installation;
- development/build/test commands;
- routes;
- environment variables;
- source structure;
- important scripts;
- development notes.

Technical detail is acceptable here.

---

## Backend README

`backend/README.md` is technical documentation for backend developers.

Include only repository-supported sections such as:

- purpose;
- architecture;
- core components;
- technology stack;
- prerequisites;
- installation;
- configuration;
- running;
- testing;
- source structure;
- development commands;
- code style.

Technical detail is acceptable here.

---

## Final Review

Before finishing:

- Verify all commands, paths, versions, ports, environment variables, and technical claims.
- Ensure `README.md` and `README_zh.md` have equivalent content and structure.
- Ensure `README.md` is English and is the default GitHub README.
- Ensure the project title and language switch are centered.
- Ensure the root README is visually clean and concise.
- Ensure the technology stack is easy to recognize visually.
- Ensure detailed implementation information is delegated to module or dedicated documentation.
- Remove unnecessary verbosity and duplication.