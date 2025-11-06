# Mind-Q web app

*Automatically synced with your [v0.app](https://v0.app) deployments*

[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?style=for-the-badge&logo=vercel)](https://vercel.com/haithamhaj-1163s-projects/v0-mind-q-web-app)
[![Built with v0](https://img.shields.io/badge/Built%20with-v0.app-black?style=for-the-badge)](https://v0.app/chat/projects/W7UHBHyyDqn)

## Overview

This repository will stay in sync with your deployed chats on [v0.app](https://v0.app).
Any changes you make to your deployed app will be automatically pushed to this repository from [v0.app](https://v0.app).

## Deployment

Your project is live at:

**[https://vercel.com/haithamhaj-1163s-projects/v0-mind-q-web-app](https://vercel.com/haithamhaj-1163s-projects/v0-mind-q-web-app)**

## Build your app

Continue building your app on:

**[https://v0.app/chat/projects/W7UHBHyyDqn](https://v0.app/chat/projects/W7UHBHyyDqn)**

## How It Works

1. Create and modify your project using [v0.app](https://v0.app)
2. Deploy your chats from the v0 interface
3. Changes are automatically pushed to this repository
4. Vercel deploys the latest version from this repository

## Visualization architecture

- ECharts is used as the primary charting engine via `src/bi/components/layer2/EChartBase` and `components/bi-chart`.
- A new `components/VisualizationAdapter` routes to advanced charts (heatmap, boxplot, waterfall, scatter, multi-axis) under `src/bi/components/layer2`.
- Performance defaults: canvas renderer, lazy updates, dataset/encode, progressive rendering, dataZoom/brush/toolbox.

### Usage

```tsx
<VisualizationAdapter
  data={rows}
  viz={{ chartType: "heatmap", xKey: "dt", valueKey: "val" }}
  height={360}
/>
```

Supported chartType examples: `bar`, `line`, `area`, `pie`, `heatmap`, `boxplot`, `scatter`, `waterfall`, `multi-line`.