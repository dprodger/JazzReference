# Python Virtual Environment Setup

## Backend API Environment

### Initial Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment:**
   
   **On macOS/Linux:**
   ```bash
   source venv/bin/activate
   ```
   
   **On Windows:**
   ```bash
   venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Flask API

With the virtual environment activated:

```bash
python app.py
```

The API will be available at `http://localhost:5001`

### Research Scripts Environment

If you need to run the research scripts:

```bash
pip install -r research_requirements.txt
```

Then run research:
```bash
python jazz_song_research.py "Song Name"
```

Or batch research:
```bash
python batch_research.py sample-songs.txt
```

## Deactivating the Virtual Environment

When you're done working:

```bash
deactivate
```

## Reactivating Later

Whenever you return to work on the project:

```bash
cd backend
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

## Troubleshooting

### If `python3` command not found:
Try `python` instead of `python3`

### If you need to recreate the environment:
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Checking if virtual environment is active:
You should see `(venv)` at the beginning of your terminal prompt

### Database Configuration

The app reads the following environment variables for its database connection. Put them in `backend/.env` for local development, and set them as environment variables wherever the backend runs in production:

- `DB_HOST` — the Supabase project host (find it in the Supabase dashboard under *Project Settings → Database → Connection info*)
- `DB_NAME` — usually `postgres`
- `DB_USER` — usually `postgres`
- `DB_PASSWORD` — the database password from the Supabase dashboard (*Project Settings → Database → Database password*)
- `DB_PORT` — `5432` for direct connections, `6543` for the Supavisor pooler

Never check the actual values into git. `backend/.env` is already listed in `.gitignore`.