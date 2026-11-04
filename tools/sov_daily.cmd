@echo off
rem The daily share-of-voice pass (KA-V, 2026-11-04): fills this month's free-tier engine columns a few prompts a day
rem (Groq's free tier is a token budget per model per day) and scores the month. Resumes - never re-asks a read cell.
rem Scheduled by: schtasks /Create /SC DAILY /ST 21:30 /TN "WorkHive SOV daily" /TR "<repo>\tools\sov_daily.cmd" /IT
rem (21:30: the host is idle; /IT runs it as the signed-in user with no stored password)
rem Remove with:  schtasks /Delete /TN "WorkHive SOV daily" /F
cd /d "%~dp0.."
if not exist .tmp mkdir .tmp
python tools\geo_sov_free_run.py --engines groq_browser,mistral_web --score >> .tmp\sov_daily.log 2>&1
