npx supabase functions deploy ai-orchestrator --no-verify-jwt
npx supabase functions deploy agentic-rag-loop --no-verify-jwt
npx supabase functions deploy hierarchical-summarizer --no-verify-jwt
npx supabase functions deploy temporal-rag-orchestrator --no-verify-jwt
npx supabase functions deploy agent-memory-store --no-verify-jwt
npx supabase functions deploy data-fabric-normalizer --no-verify-jwt
npx supabase functions deploy cold-archive-query --no-verify-jwt
npx supabase functions deploy semantic-fact-extractor --no-verify-jwt
npx supabase functions deploy engineering-bom-sow --no-verify-jwt
npx supabase functions deploy engineering-calc-agent --no-verify-jwt
npx supabase functions deploy scheduled-agents --no-verify-jwt
npx supabase functions deploy failure-signature-scan --no-verify-jwt
npx supabase functions deploy voice-logbook-entry --no-verify-jwt
npx supabase functions deploy cmms-sync --no-verify-jwt
npx supabase functions deploy benchmark-compute --no-verify-jwt
npx supabase functions deploy cmms-webhook-receiver --no-verify-jwt
npx supabase functions deploy cmms-push-completion --no-verify-jwt
npx supabase functions deploy intelligence-report --no-verify-jwt
npx supabase functions deploy intelligence-api --no-verify-jwt
npx supabase functions deploy analytics-orchestrator --no-verify-jwt
npx supabase functions deploy send-report-email --no-verify-jwt
npx supabase functions deploy voice-report-intent --no-verify-jwt
npx supabase functions deploy voice-transcribe --no-verify-jwt
npx supabase functions deploy voice-journal-agent --no-verify-jwt
npx supabase functions deploy ai-gateway --no-verify-jwt
npx supabase functions deploy marketplace-listing-assist --no-verify-jwt
npx supabase functions deploy semantic-search --no-verify-jwt
npx supabase functions deploy embed-entry --no-verify-jwt
npx supabase functions deploy project-progress --no-verify-jwt
npx supabase functions deploy project-orchestrator --no-verify-jwt
npx supabase functions deploy batch-risk-scoring --no-verify-jwt
npx supabase functions deploy parts-staging-recommender --no-verify-jwt
npx supabase functions deploy trigger-ml-retrain --no-verify-jwt
npx supabase functions deploy asset-brain-query --no-verify-jwt
npx supabase functions deploy shift-planner-orchestrator --no-verify-jwt
npx supabase functions deploy voice-action-router --no-verify-jwt
npx supabase functions deploy fmea-populator --no-verify-jwt
npx supabase functions deploy weibull-fitter --no-verify-jwt
npx supabase functions deploy notify-push --no-verify-jwt
npx supabase functions deploy pf-calculator --no-verify-jwt
npx supabase functions deploy ai-eval-runner --no-verify-jwt
npx supabase functions deploy platform-gateway --no-verify-jwt
npx supabase functions deploy pdf-ingest --no-verify-jwt
npx supabase functions deploy amc-orchestrator --no-verify-jwt
npx supabase functions deploy visual-defect-capture --no-verify-jwt
npx supabase functions deploy equipment-label-ocr --no-verify-jwt
npx supabase functions deploy sensor-readings-ingest --no-verify-jwt
npx supabase functions deploy tts-speak --no-verify-jwt
npx supabase functions deploy walkthrough-analyzer --no-verify-jwt
npx supabase functions deploy export-hive-data --no-verify-jwt
npx supabase functions deploy platform-scraper --no-verify-jwt
npx supabase functions deploy resume-extract --no-verify-jwt
npx supabase functions deploy resume-polish --no-verify-jwt
npx supabase functions deploy voice-embeddings --no-verify-jwt
npx supabase functions deploy voice-model-call --no-verify-jwt
npx supabase functions deploy voice-semantic-rag --no-verify-jwt

# GCash receipt intake (mig 38). Registered in config.toml and validate_edge_contracts.py the day it
# shipped, but NOT here - so a deploy would have skipped it and the automatic top-up verification
# would have been live in the schema with no endpoint behind it.
#
# verify_jwt = false is CORRECT for this one: an SMS/email forwarder has no Supabase session. It
# authenticates by signing the raw body with GCASH_INBOUND_SECRET (HMAC-SHA256), and the handler
# fails CLOSED when that secret is unset. Deploying it WITH jwt verification would lock the forwarder
# out entirely, and the automation would look broken with nothing in the logs to say why.
npx supabase functions deploy gcash-receipt-inbound --no-verify-jwt

# NOTE: gcash-receipt-ocr is deliberately NOT in this script. Every line here forces
# --no-verify-jwt, and that function is config.toml verify_jwt = TRUE - it is called from the browser
# by a signed-in provider or buyer uploading their own receipt, so the session IS the gate, and
# deploying it with --no-verify-jwt would open an Azure-billed endpoint to the internet. It follows
# the same separate-deploy rule the runbook already applies to supervisor-reset-password. See
# PRODUCTION_DEPLOY_RUNBOOK.md.
