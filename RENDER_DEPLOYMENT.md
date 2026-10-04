# Deploy upscEasy to Render with Supabase

This setup runs the Django app on Render and stores its persistent data in your existing Supabase PostgreSQL database. Render's free web service can sleep after 15 minutes without traffic and may take about a minute to wake; its local filesystem is temporary, so keep `DB_URL` pointed at Supabase. The free service is intended for hobby projects and has usage limits.

## 1. Push the project to a private GitHub repository

This folder is not currently a Git repository. In Terminal on your Mac:

```bash
cd ~/Desktop/upscEasy-local
git init
git add .
git commit -m "Prepare upscEasy for Render hosting"
```

Create a **private** GitHub repository, then connect and push this repository using the commands GitHub provides. `.gitignore` excludes `.env`, `db.sqlite3`, and SQLite backups. Check that no secrets or database files are included before pushing.

## 2. Create the Render service

1. Sign in to Render and choose **New → Blueprint**.
2. Connect the private GitHub repository. Render will read `render.yaml` and show the `upsceasy` web service.
3. When prompted for `DB_URL`, enter the Supabase **Session pooler** connection URI. Keep this value secret. Use the URI you tested locally, with your current Supabase database password URL-encoded (for example, encode `@` inside the password as `%40`).
4. When prompted for `OPENAI_API_KEY`, enter your OpenAI API key if you want evaluation and model-answer generation on the hosted site. This is separate from the Supabase database password. Leave it blank if you do not want hosted AI requests.
5. Apply the Blueprint and wait for the first deployment to finish.

The Blueprint sets `DEBUG=0`, disables public account creation, generates a Django `SECRET_KEY`, runs database migrations and `collectstatic`, and starts the app with Gunicorn. Django uses Render's assigned hostname for allowed hosts and CSRF origins. Your existing account can still sign in; local registration remains enabled.

## 3. Open and sign in

Open the `https://...onrender.com` URL shown on the Render service page. Sign in with the account that was copied from your local SQLite database. If you changed the user data after the earlier Supabase import, update the hosted database before relying on that newer data.

The Supabase database already contains the current local data migrated during setup, including 19 saved evaluations and 13 memory items. The local `db.sqlite3` remains as a backup and is not used by the Render service.

## 4. Future updates

Push code changes to GitHub. Render will build and deploy them automatically. The build command reapplies migrations and recollects static files. Do not add `.env` or database credentials to Git.

## Free-plan notes

- Render's free service sleeps after 15 minutes of inactivity, so the first request afterward can be slow.
- Render's free service filesystem is ephemeral; Supabase is the persistent database.
- The Render free service uses outbound traffic for Supabase and OpenAI. Monitor Render's included bandwidth and service limits.
- Supabase's free project can pause after a week of inactivity. Check the current Supabase Free plan limits and keep a separate database backup.

## Troubleshooting

- Check the Render service's **Logs** after a failed deploy.
- A database connection error usually means `DB_URL` is missing, copied incorrectly, or contains an unencoded reserved character in the password.
- `DisallowedHost` or CSRF errors: confirm the app URL is the current Render hostname. If using a custom domain, add it to `ALLOWED_HOSTS` and add its `https://` origin to `CSRF_TRUSTED_ORIGINS` in `upsc_easy/settings.py` or the corresponding environment variables.
- If the app starts but styles are missing, check the build logs for `collectstatic` errors.
