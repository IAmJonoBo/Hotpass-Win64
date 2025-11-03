# Hotpass Web UI

Modern React-based web interface for Hotpass data pipeline monitoring and management.

## Features

- **Dashboard**: Real-time monitoring of pipeline runs with status and metrics
- **Lineage View**: Interactive data lineage visualization from OpenLineage/Marquez
- **Run Details**: Detailed view of individual runs with QA results
- **Admin Panel**: Configure API endpoints and environment settings
- **Governance Inventory**: Asset manifest explorer linked to the backend inventory service
- **Assistant**: AI-powered chat interface for exploring flows and lineage
- **Human-in-the-Loop**: Approval workflows for quality gates
- **Dark Mode**: System-aware dark/light theme with manual toggle
- **Responsive Design**: Optimized for desktop (1024px+) with mobile support
- **Docker Support**: Complete ecosystem in containers
- **Model Profiles**: Runtime switcher for GitHub Copilot (recommended) and alternate LLM providers

## Tech Stack

- **React 18** - Latest React features
- **Vite** - Fast build tool and dev server
- **TypeScript** - Type-safe development
- **TailwindCSS** - Utility-first styling
- **shadcn/ui** - Accessible component primitives
- **React Query** - Server state management
- **React Router** - Client-side routing
- **Storybook** - Component documentation

## Getting Started

### Prerequisites

- Node.js 20+ and npm 10+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- Marquez backend (optional, mock data available)
- Prefect API (optional, mock data available)

### Quick Start with Docker

The easiest way to get the full Hotpass ecosystem running is with Docker Compose:

```bash
# From the repository root
docker compose -f deploy/docker/docker-compose.yml up --build

# Or use the Makefile shortcut (if available)
make docker-up
```

This starts:
- **Hotpass Web UI** at [http://localhost:3001](http://localhost:3001)
- **Marquez** at [http://localhost:5000](http://localhost:5000)
- **Prefect Server** at [http://localhost:4200](http://localhost:4200)

All services are networked together and the UI is pre-configured to connect to them.

### Local Development (without Docker)

### Installation

```bash
cd apps/web-ui
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3001](http://localhost:3001) in your browser.

### Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

### Storybook

View component documentation and test components in isolation:

```bash
npm run storybook
```

Open [http://localhost:6006](http://localhost:6006) to view the Storybook.

## Configuration

Configuration can be set via environment variables or the Admin page:

### Environment Variables

Create a `.env.local` file:

```env
VITE_PREFECT_API_URL=http://localhost:4200
VITE_MARQUEZ_API_URL=http://localhost:5000
VITE_ENVIRONMENT=local  # or 'docker', 'staging', 'prod'
# Optional: override default artifact directories
HOTPASS_IMPORT_ROOT=./dist/import
HOTPASS_CONTRACT_ROOT=./dist/contracts
```

**Environment Options:**
- `local` - Local development (no banner shown)
- `docker` - Running in Docker containers (shows banner)
- `staging` - Staging environment (shows yellow banner)
- `prod` - Production environment (shows red banner)

### Admin Page

Navigate to `/admin` to configure API endpoints through the UI. Settings are stored in localStorage.

### Assistant Model Providers

LLM preferences live in `public/config/llm-providers.yaml`. By default the UI recommends GitHub Copilot in VS Code, but you can toggle Groq, OpenRouter, Hugging Face, or a local Ollama runtime from the **Admin → Assistant Model** panel. The same YAML drives MCP integrations and the Dockerised GUI.

## Project Structure

```
apps/web-ui/
├── public/              # Static assets
├── src/
│   ├── api/            # API client functions
│   │   ├── marquez.ts  # Marquez/OpenLineage API
│   │   └── prefect.ts  # Prefect API
│   ├── components/     # React components
│   │   ├── ui/         # Base UI components
│   │   ├── Layout.tsx  # App layout wrapper
│   │   └── Sidebar.tsx # Navigation sidebar
│   ├── lib/            # Utility functions
│   │   └── utils.ts    # Helpers and utilities
│   ├── pages/          # Route pages
│   │   ├── Dashboard.tsx
│   │   ├── Lineage.tsx
│   │   ├── RunDetails.tsx
│   │   └── Admin.tsx
│   ├── stories/        # Storybook stories
│   ├── types/          # TypeScript type definitions
│   ├── App.tsx         # Root application component
│   ├── main.tsx        # Application entry point
│   └── index.css       # Global styles
├── .storybook/         # Storybook configuration
├── index.html          # HTML entry point
├── package.json        # Dependencies and scripts
├── tsconfig.json       # TypeScript configuration
├── vite.config.ts      # Vite configuration
└── tailwind.config.js  # Tailwind configuration
```

## Design System

### Colors

The UI uses a semantic color system that adapts to light/dark mode:

- **Primary**: Main brand color (indigo)
- **Secondary**: Secondary actions
- **Muted**: Subtle backgrounds and borders
- **Accent**: Highlights and interactive elements
- **Destructive**: Dangerous actions

### Typography

- **Headings**: Bold, tight tracking
- **Body**: Regular weight, comfortable line height
- **Code**: Monospace for technical content

### Components

All components follow shadcn/ui patterns:
- Composable and accessible
- Variants for different contexts
- Consistent spacing and sizing

## API Integration

### Marquez API

The app fetches lineage data from Marquez:

- Namespaces
- Jobs and job runs
- Datasets and their relationships
- Lineage graphs

Mock data is used when the API is unavailable.

### Prefect API

The app fetches flow data from Prefect:

- Flows and flow runs
- Deployments
- Run parameters and state

Mock data is used when the API is unavailable.

## Testing

Run linting:

```bash
npm run lint
```

Build for production (TypeScript check):

```bash
npm run build
```

## Future Enhancements

- [ ] Interactive lineage graph visualization (react-flow or d3)
- [ ] Real-time updates via WebSocket
- [ ] Search and filter across all runs
- [ ] Export functionality for reports
- [ ] Integration with Label Studio for data review
- [ ] Notification system for failed runs
- [ ] Custom dashboard widgets
- [ ] Telemetry strip showing live system status
- [ ] Power tools launcher for common operations

## Integration with Hotpass CLI

The web UI is designed to complement the Hotpass CLI:

```bash
# Start Marquez backend
make marquez-up

# Run a pipeline
uv run hotpass refine --input-dir ./data --output-path ./dist/refined.xlsx

# View results in the web UI
npm run dev
```

## License

See repository root LICENSE file.
