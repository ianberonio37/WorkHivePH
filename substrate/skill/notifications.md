---
name: skill-notifications
type: skill
source: skill:notifications
source_sha: 2e110e1df0055443
last_verified: 2026-07-13
supersedes: null
---
## skill · notifications

Push notifications, predictive alert thresholds, in-app alert center, email digests, scheduled automation, pg_cron, n8n, Resend, and Supabase Edge Functions for notifications. Triggers on "notificatio

**Sections:** Notifications Agent · This Platform's Notification Context · The Three-Layer Notification Stack · Layer 1: In-App Notifications (Supabase Realtime) · Toast Notification Pattern · Live Feed Notification (Realtime Subscription) · Computed Notifications Must Replace, Not Append · Cross-Page Stock Propagation Requires a Dedicated Realtime Channel · In-App Notification Center (Persistent Alerts) · Layer 2: Email Notifications (Resend + Edge Functions) · Resend Setup · Email Templates for WorkHive Alerts · Alert Thresholds — When to Trigger Email vs. In-App Only · Layer 3: n8n — Multi-Step Notification Sequences · Self-Hosting n8n (Free) · Deploy n8n on Railway: · 1. Create Railway account · 2. New project → Deploy from template → n8n · 3. Set env vars: N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD, WEBHOOK_URL · 4. Your n8n URL: https://your-app.railway.app · WorkHive n8n Workflows · n8n + Supabase Edge Function Handoff Pattern · Resend Domain Verification — Required Before Custom From Address · Verify domain before using custom from address · Rate limit email sends via automation_log · Checklist Before Shipping Any Notification Feature · Output Format · L3 — Every Realtime Channel Must Be Saved to a Module-Level Variable · L4 — `beforeunload` Completeness: Count Channels, Not Pages · L5 — Approval Queue Realtime Must Subscribe to Both INSERT and UPDATE

(Deep source: `skill:notifications` — retrieve this TOC to know WHICH section to read.)
