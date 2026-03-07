param()

$ErrorActionPreference = "Stop"

docker compose exec -T backend python -c "import json; from pathlib import Path; from app import content_store; content_dir = Path('/app/data/content'); content_store.save_centers(json.loads((content_dir / 'centers.json').read_text(encoding='utf-8'))); content_store.save_presentations(json.loads((content_dir / 'presentations.json').read_text(encoding='utf-8'))); content_store.save_alumni_wall(json.loads((content_dir / 'alumni_wall.json').read_text(encoding='utf-8'))); content_store.save_student_accounts(json.loads((content_dir / 'student_accounts.json').read_text(encoding='utf-8'))); print('Contenido sincronizado a PostgreSQL')"
