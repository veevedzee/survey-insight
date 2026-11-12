---
title: Survey Insight API
emoji: 📊
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Backend API for Survey Insight, an open-source survey analytics dashboard
---

# Survey Insight API

The FastAPI backend of [Survey Insight](https://github.com/veevedzee/survey-insight):
it cleans survey exports, removes personal data, runs the statistics and finds
themes in open-ended answers with an open-source multilingual model.

- Interactive API docs: `/docs`
- Health check: `/api/health`

The web app is hosted separately on Vercel. Uploaded files are kept in memory
only and deleted after 30 minutes.
