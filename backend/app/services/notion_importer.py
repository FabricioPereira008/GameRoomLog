import csv
import logging
import re
import threading
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.game import Game, GameStatus, PlayType, GameFormat
from backend.app.models.genre import Genre
from backend.app.models.platform import Platform
from backend.app.models.franchise import Franchise
from backend.app.models.developer import Developer
from backend.app.core.database import SessionLocal
from backend.app.services.cover_service import find_cover_sync

logger = logging.getLogger(__name__)

MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
}

GENRE_COLORS = [
    "#4f46e5", "#7c3aed", "#2563eb", "#059669", "#d97706",
    "#dc2626", "#db2777", "#0891b2", "#475569", "#ea580c"
]

def clean_relation(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    val = val.strip()
    # Pega apenas o primeiro item se houver vírgulas com links
    first_item = val.split(",")[0].strip()
    # Remove padrão de link do Notion: Nome (Path/to/file.md)
    m = re.match(r"^(.*?)\s*\(.*?\)$", first_item)
    if m:
        cleaned = m.group(1).strip()
    else:
        cleaned = first_item
    return cleaned if cleaned else None

def parse_notion_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    date_str = date_str.strip()
    if not date_str:
        return None

    # Formato DD/MM/YYYY
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", date_str):
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except Exception:
            pass

    # Formato YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            pass

    # Formato por extenso em PT: "13 de abril de 2024"
    m = re.match(r"^(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})$", date_str.lower())
    if m:
        day = int(m.group(1))
        month_str = m.group(2)
        year = int(m.group(3))
        month = MONTHS_PT.get(month_str)
        if month:
            try:
                return date(year, month, day)
            except Exception:
                pass

    return None

def clean_number(val: Optional[str]) -> Optional[float]:
    if not val:
        return None
    val = str(val).strip()
    # Extrai números e decimais (ex: '⏳ 91h' -> 91.0, '53h' -> 53.0)
    match = re.search(r"(\d+(?:[\.,]\d+)?)", val)
    if match:
        num_str = match.group(1).replace(",", ".")
        try:
            return float(num_str)
        except ValueError:
            return None
    return None

def clean_play_count(val: Optional[str]) -> int:
    if not val:
        return 1
    val = str(val).strip()
    match = re.search(r"(\d+)", val)
    if match:
        try:
            c = int(match.group(1))
            return max(1, c)
        except ValueError:
            pass
    return 1

def map_play_type(pt_str: Optional[str]) -> PlayType:
    if not pt_str:
        return PlayType.PRIMEIRA_JOGADA
    s = pt_str.strip().lower()
    if "rejog" in s or "re-jog" in s or "replay" in s:
        return PlayType.REJOGADA
    return PlayType.PRIMEIRA_JOGADA

def map_status(status_str: Optional[str]) -> GameStatus:
    if not status_str:
        return GameStatus.DISPONIVEL
    s = status_str.strip().lower()
    if "zerad" in s:
        return GameStatus.ZERADO
    if "platin" in s:
        return GameStatus.PLATINADO
    if "jogand" in s:
        return GameStatus.JOGANDO
    if "fila" in s:
        return GameStatus.FILA
    if "próxim" in s or "proxim" in s:
        return GameStatus.PROXIMO
    if "pausad" in s:
        return GameStatus.PAUSADO
    if "desist" in s:
        return GameStatus.DESISTI
    if "desejo" in s or "wishlist" in s:
        return GameStatus.WISHLIST
    if "dispon" in s:
        return GameStatus.DISPONIVEL
    return GameStatus.DISPONIVEL

def sanitize_filename_for_lookup(name: str) -> str:
    """Remove caracteres especiais para busca aproximada de arquivos .md."""
    return re.sub(r"[^\w\s]", "", name).lower().strip()

def background_fetch_covers_for_games(game_ids: List[int]):
    """Thread em background para buscar capas dos jogos importados sem travar a interface."""
    def worker():
        db = SessionLocal()
        try:
            for gid in game_ids:
                game = db.query(Game).filter(Game.id == gid).first()
                if game and not game.cover_image:
                    cover_file = find_cover_sync(game.title)
                    if cover_file:
                        game.cover_image = cover_file
                        db.commit()
        except Exception as e:
            logger.exception("Erro no background cover fetcher")
        finally:
            db.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


class NotionImporterService:
    @staticmethod
    def find_export_files(root_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
        """Localiza o arquivo CSV principal de jogos e o diretório de subpáginas Markdown."""
        csv_path = None
        jogos_dir = None

        all_csvs = list(root_dir.glob("**/Jogos*_all.csv"))
        if all_csvs:
            csv_path = all_csvs[0]
        else:
            std_csvs = list(root_dir.glob("**/Jogos*.csv"))
            if std_csvs:
                csv_path = std_csvs[0]

        for p in root_dir.rglob("Jogos"):
            if p.is_dir():
                jogos_dir = p
                break

        return csv_path, jogos_dir

    @staticmethod
    def import_notion_folder(
        db: Session, folder_path: str, auto_fetch_covers: bool = True
    ) -> Dict[str, Any]:
        root = Path(folder_path)
        if not root.exists() or not root.is_dir():
            raise ValueError(f"O caminho informado não é um diretório válido: {folder_path}")

        csv_file, _ = NotionImporterService.find_export_files(root)
        if not csv_file or not csv_file.exists():
            raise ValueError(
                "Não foi encontrado o arquivo de banco de dados 'Jogos.csv' ou 'Jogos_all.csv' no diretório selecionado."
            )

        imported_count = 0
        updated_count = 0
        created_game_ids = []
        errors = []

        genres_cache = {g.name.lower(): g for g in db.query(Genre).all()}
        platforms_cache = {p.name.lower(): p for p in db.query(Platform).all()}
        franchises_cache = {f.name.lower(): f for f in db.query(Franchise).all()}
        devs_cache = {d.name.lower(): d for d in db.query(Developer).all()}

        with open(csv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_found = len(rows)

        for idx, row in enumerate(rows):
            try:
                title = (row.get("Jogo") or "").strip()
                if not title:
                    continue

                status = map_status(row.get("Status"))
                play_type = map_play_type(row.get("Tipo de Jogada"))
                play_count = clean_play_count(row.get("Vez jogada") or row.get("Número da jogada"))
                
                score = clean_number(row.get("Nota"))
                difficulty = clean_number(row.get("Dificuldade"))
                hltb_hours = clean_number(row.get("Expectativa de Horas"))
                played_hours = clean_number(row.get("Horas Jogadas"))

                finish_date = parse_notion_date(row.get("Data de Finalização"))
                platinum_date = parse_notion_date(row.get("Data da Platina"))


                # 1. Plataforma
                platform_id = None
                plat_name = clean_relation(row.get("Plataforma"))
                if plat_name:
                    plat_key = plat_name.lower()
                    if plat_key not in platforms_cache:
                        new_plat = Platform(name=plat_name)
                        db.add(new_plat)
                        db.flush()
                        platforms_cache[plat_key] = new_plat
                    platform_id = platforms_cache[plat_key].id

                # 2. Desenvolvedora
                dev_id = None
                dev_name = clean_relation(row.get("Desenvolvedora")) or (row.get("Desenvolvedora") or "").strip()
                if dev_name:
                    dev_key = dev_name.lower()
                    if dev_key not in devs_cache:
                        new_dev = Developer(name=dev_name)
                        db.add(new_dev)
                        db.flush()
                        devs_cache[dev_key] = new_dev
                    dev_id = devs_cache[dev_key].id

                # 3. Franquia
                franchise_id = None
                fran_name = clean_relation(row.get("Franquia"))
                if fran_name:
                    fran_key = fran_name.lower()
                    if fran_key not in franchises_cache:
                        new_fran = Franchise(name=fran_name)
                        db.add(new_fran)
                        db.flush()
                        franchises_cache[fran_key] = new_fran
                    franchise_id = franchises_cache[fran_key].id

                # 4. Gênero
                genre_obj = None
                genre_name = clean_relation(row.get("Gênero"))
                if genre_name:
                    gen_key = genre_name.lower()
                    if gen_key not in genres_cache:
                        color = GENRE_COLORS[len(genres_cache) % len(GENRE_COLORS)]
                        new_gen = Genre(name=genre_name, color=color)
                        db.add(new_gen)
                        db.flush()
                        genres_cache[gen_key] = new_gen
                    genre_obj = genres_cache[gen_key]

                # 5. Criação ou Atualização do Jogo
                existing_game = db.query(Game).filter(
                    Game.title.ilike(title),
                    Game.platform_id == platform_id
                ).first()

                completion_year = None
                if finish_date:
                    completion_year = finish_date.year
                elif platinum_date:
                    completion_year = platinum_date.year
                elif status in [GameStatus.ZERADO, GameStatus.PLATINADO]:
                    completion_year = date.today().year

                if existing_game:
                    existing_game.status = status
                    existing_game.developer = dev_name
                    existing_game.developer_id = dev_id
                    existing_game.franchise_id = franchise_id
                    existing_game.score = score
                    existing_game.difficulty = difficulty
                    existing_game.hltb_hours = hltb_hours
                    existing_game.played_hours = played_hours
                    existing_game.finish_date = finish_date
                    existing_game.platinum_date = platinum_date
                    existing_game.completion_year = completion_year
                    existing_game.play_type = play_type
                    existing_game.play_count = play_count
                    if genre_obj and genre_obj not in existing_game.genres:
                        existing_game.genres = [genre_obj]
                    
                    db.flush()
                    updated_count += 1
                    if not existing_game.cover_image:
                        created_game_ids.append(existing_game.id)
                else:
                    new_game = Game(
                        title=title,
                        status=status,
                        platform_id=platform_id,
                        developer=dev_name,
                        developer_id=dev_id,
                        franchise_id=franchise_id,
                        score=score,
                        difficulty=difficulty,
                        hltb_hours=hltb_hours,
                        played_hours=played_hours,
                        finish_date=finish_date,
                        platinum_date=platinum_date,
                        completion_year=completion_year,
                        play_type=play_type,
                        play_count=play_count,
                        format=GameFormat.DIGITAL,
                        is_favorite=False,
                    )
                    if genre_obj:
                        new_game.genres = [genre_obj]

                    db.add(new_game)
                    db.flush()
                    imported_count += 1
                    created_game_ids.append(new_game.id)

            except Exception as e:
                errors.append(f"Erro na linha {idx + 1} ({row.get('Jogo', 'Sem título')}): {str(e)}")

        db.commit()

        if auto_fetch_covers and created_game_ids:
            background_fetch_covers_for_games(created_game_ids)

        return {
            "total_found": total_found,
            "imported": imported_count,
            "updated": updated_count,
            "covers_queue_count": len(created_game_ids) if auto_fetch_covers else 0,
            "errors": errors
        }
