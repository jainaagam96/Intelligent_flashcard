# Deploying upscEasy to PythonAnywhere

This guide keeps the app on SQLite for a single user. The SQLite database must stay in your PythonAnywhere home directory (the project directory is suitable); do not put it in a temporary directory or commit it to Git.

## 1. Prepare the code

The project folder should be in a **private** GitHub repository before cloning it onto PythonAnywhere. This folder is not currently a Git repository, so from Terminal on your Mac, run:

```bash
cd ~/Desktop/upscEasy-local
git init
git add .
git commit -m "Prepare upscEasy for hosting"
```

Create a private repository on GitHub, then connect and push it using the commands GitHub shows for an existing repository. The `.gitignore` excludes `.env`, `db.sqlite3`, and `.venv`; keep those exclusions in place. Do not add API keys or the database to Git.

If you already have important local data, make a separate backup of `db.sqlite3` before starting. You can upload that database to the project directory on PythonAnywhere after cloning the code.

## 2. Create the PythonAnywhere web app

1. Sign in to PythonAnywhere and open the **Web** tab.
2. Choose **Add a new web app**, select your Python version (Python 3.13 is suitable for this project's Django 5.2 requirement), and choose **Manual configuration**.
3. Open a Bash console and clone your private repository. Replace the URL with your repository URL:

   ```bash
   cd ~
   git clone YOUR_PRIVATE_REPOSITORY_URL upscEasy-local
   cd ~/upscEasy-local
   ```

4. Create a virtual environment with the same Python version selected for the web app, then install the app's requirements:

   ```bash
   mkvirtualenv --python=python3.13 upsc-easy
   cd ~/upscEasy-local
   pip install -r requirements.txt
   ```

   If PythonAnywhere's Web tab selected another Python version, use that version in the `mkvirtualenv` command instead.

## 3. Set production configuration

Create `~/upscEasy-local/.env` using PythonAnywhere's **Files** tab. Do not commit or share this file. Use these entries, substituting your PythonAnywhere username and site domain:

```dotenv
SECRET_KEY=PASTE_A_NEW_RANDOM_SECRET_HERE
DEBUG=0
ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
SQLITE_PATH=/home/YOUR_USERNAME/upscEasy-local/db.sqlite3
SECURE_SSL_REDIRECT=0
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-5.5
```

Generate a fresh secret key on your Mac with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
```

Paste its output as `SECRET_KEY`. If you do not plan to use AI evaluation or model answers, leave `OPENAI_API_KEY` empty. `SECURE_SSL_REDIRECT=0` lets PythonAnywhere handle HTTPS at its web server; Django still marks session and CSRF cookies secure whenever `DEBUG=0`.

The app loads this `.env` from its project folder in both its web process and Django management commands.

## 4. Configure the WSGI file

In the **Web** tab, open the WSGI configuration file. Replace its contents with the following, changing `YOUR_USERNAME`:

```python
import os
import sys

project_home = '/home/YOUR_USERNAME/upscEasy-local'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upsc_easy.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

In the Web tab, set **Source code** to `/home/YOUR_USERNAME/upscEasy-local` and **Virtualenv** to `/home/YOUR_USERNAME/.virtualenvs/upsc-easy`.

## 5. Initialize the database and static files

In a Bash console:

```bash
workon upsc-easy
cd ~/upscEasy-local
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

If you are transferring your existing `db.sqlite3`, upload it into the configured SQLite path before running `migrate`. `migrate` applies any pending schema changes while preserving its data.

Back on the **Web** tab, add a static files mapping:

| URL | Directory |
| --- | --- |
| `/static/` | `/home/YOUR_USERNAME/upscEasy-local/staticfiles` |

Save, then click **Reload**. Visit your `https://YOUR_USERNAME.pythonanywhere.com` address and sign in.

## Updating the hosted app

After pushing a code update to GitHub, use a PythonAnywhere Bash console:

```bash
workon upsc-easy
cd ~/upscEasy-local
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then click **Reload** on the Web tab. Make regular copies of `db.sqlite3`; it contains your saved app data.

## Troubleshooting

- Check the **error log** linked from the Web tab first.
- A `DisallowedHost` error usually means `ALLOWED_HOSTS` does not exactly include the hosted domain.
- A CSRF error usually means `CSRF_TRUSTED_ORIGINS` is missing the full `https://` site origin.
- Missing styles usually means `collectstatic` was not run or the `/static/` mapping points to the wrong `staticfiles` directory.
- OpenAI `RateLimitError`/quota issues are separate from hosting. Confirm the API key, model access, and API account billing; a PythonAnywhere free account may also restrict outbound network access. Check its current plan and outbound-network documentation before choosing a plan.
