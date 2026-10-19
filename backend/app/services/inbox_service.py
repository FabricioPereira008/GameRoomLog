"""Caixa de entrada do app do portátil: importação idempotente, correspondência e propostas de mudança.

O app manda eventos (jogando/zerado/platinado) com título e plataforma em texto. Aqui eles são
agrupados por jogo, casados com o catálogo por semelhança e convertidos numa proposta que o
usuário revisa. Nada é aplicado ao jogo por este serviço: a GUI grava pelo endpoint de jogos e
depois marca os eventos como resolvidos.

Rejogada é um registro novo vinculado ao original (`replay_of_id`): quando os eventos indicam
que um jogo já concluído foi jogado de novo, a proposta traz `replay` (o jogo a criar) em vez de
sobrescrever o registro antigo. Um grupo de jogadas é tratado como um jogo só, representado pela
jogada mais recente.
"""
import difflib
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from backend.app.models.game import Game, GameStatus, PlayType
from backend.app.models.inbox import InboxEvent
from backend.app.models.platform import Platform
from backend.app.schemas.inbox import (
    INBOX_VERSION, CatalogGame, CatalogResponse, InboxEventIn, InboxEventOut, InboxGroup,
    InboxImportResponse, InboxPackage, InboxPendingResponse, MatchCandidate, PlatformMatch,
)
from backend.app.services.library_service import normalize_title

DEFAULT_THRESHOLD = 85
MAX_CANDIDATES = 3
CONTAINMENT_SIMILARITY = 90  # "Hollow Knight" contido em "Hollow Knight Voidheart Edition"

PENDING, APPLIED, DISCARDED = "pending", "applied", "discarded"

# Campos que um evento pode alterar, na ordem em que aparecem na revisão
TRACKED_FIELDS = (
    "status", "play_type", "play_count", "finish_date", "platinum_date",
    "played_hours", "score", "difficulty", "notes",
)

_ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10"}
_COMPLETED = (GameStatus.ZERADO, GameStatus.PLATINADO)


class UnsupportedVersionError(Exception):
    pass


class InboxEventNotFoundError(Exception):
    pass


def match_key(title: str) -> str:
    """normalize_title + numerais romanos como dígitos e sem artigo inicial ("The")."""
    tokens = [_ROMAN.get(t, t) for t in normalize_title(title or "").split()]
    if tokens and tokens[0] == "the":
        tokens = tokens[1:]
    return " ".join(tokens)


def _compact(key: str) -> str:
    return key.replace(" ", "")


def similarity(a: str, b: str) -> int:
    """0-100 entre duas chaves já normalizadas; ignora espaços ("SquareEnix" == "Square Enix")."""
    a, b = _compact(a), _compact(b)
    if not a or not b:
        return 0
    if a == b:
        return 100
    score = round(difflib.SequenceMatcher(None, a, b).ratio() * 100)
    if min(len(a), len(b)) >= 3 and (a in b or b in a):
        score = max(score, CONTAINMENT_SIMILARITY)
    return min(score, 99)


def _event_sort_key(ev: InboxEvent) -> Tuple:
    return (ev.event_date, ev.device_created_at or ev.received_at or datetime.min, ev.id or 0)


def _value(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _note_line(ev: InboxEvent) -> str:
    return f"[Portátil {ev.event_date.strftime('%d/%m/%Y')}] {ev.notes.strip()}"


def propose_state(current: Optional[Game], events: Sequence[InboxEvent]) -> Dict[str, Any]:
    """Aplica os eventos (em ordem cronológica) sobre o estado atual e devolve o estado proposto.

    Regras:
    - Jogando em jogo já zerado/platinado inicia uma rejogada (play_type=Rejogada), mas o
      play_count só sobe quando a rejogada termina (Zerado/Platinado).
    - Zerado com data diferente da já registrada também é uma rejogada.
    - Platinado sem finish_date propõe a mesma data para o zeramento.
    - Um jogo com platinum_date continua Platinado ao ser zerado de novo.
    - Horas, nota e dificuldade: vale o último valor informado. Observações são acrescentadas.
    """
    return _simulate(current, events)[0]


def replay_start(current: Optional[Game], events: Sequence[InboxEvent]) -> Optional[int]:
    """Posição (nos eventos em ordem cronológica) em que começa uma rejogada; None se não houver."""
    return _simulate(current, events)[1]


def _simulate(current: Optional[Game], events: Sequence[InboxEvent]) -> Tuple[Dict[str, Any], Optional[int]]:
    if current is not None:
        state = {f: getattr(current, f) for f in TRACKED_FIELDS}
    else:
        state = {f: None for f in TRACKED_FIELDS}
        state.update(status=GameStatus.DISPONIVEL, play_type=PlayType.PRIMEIRA_JOGADA, play_count=1)
    state["play_count"] = state["play_count"] or 1

    in_replay = False
    completed_in_batch = False
    start: Optional[int] = None  # evento que abriu a 1ª rejogada (Jogando, ou zerou/platinou de novo)
    plays_before = state["play_count"]

    def close_replay():
        nonlocal in_replay
        state["play_count"] += 1
        state["play_type"] = PlayType.REJOGADA
        in_replay = False

    for index, ev in enumerate(sorted(events, key=_event_sort_key)):
        d = ev.event_date
        completed = state["status"] in _COMPLETED
        if ev.event_type == "playing":
            if completed:
                in_replay = True
                state["play_type"] = PlayType.REJOGADA
            state["status"] = GameStatus.JOGANDO
        elif ev.event_type == "finished":
            if completed and state["finish_date"] and state["finish_date"] != d:
                in_replay = True
            if in_replay:
                close_replay()
                state["finish_date"] = d
            elif not completed or not state["finish_date"]:
                state["finish_date"] = d
            state["status"] = GameStatus.PLATINADO if state["platinum_date"] else GameStatus.ZERADO
            completed_in_batch = True
        elif ev.event_type == "platinum":
            if (state["platinum_date"] and state["platinum_date"] != d
                    and state["status"] == GameStatus.PLATINADO and not completed_in_batch):
                in_replay = True
            if in_replay:
                close_replay()
                state["finish_date"] = d
            elif not state["finish_date"]:
                state["finish_date"] = d
            state["platinum_date"] = d
            state["status"] = GameStatus.PLATINADO
            completed_in_batch = True
        if start is None and (in_replay or state["play_count"] > plays_before):
            start = index

        for field in ("played_hours", "score", "difficulty"):
            if getattr(ev, field) is not None:
                state[field] = getattr(ev, field)
        if ev.notes and ev.notes.strip():
            line = _note_line(ev)
            existing = state["notes"] or ""
            if line not in existing:
                state["notes"] = f"{existing}\n{line}" if existing else line
    return state, start


def _serialize(state: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, date) else _value(v)) for k, v in state.items()}


# Campos copiados do registro original para a nova jogada (o resto vem dos eventos)
REPLAY_COPIED_FIELDS = ("title", "platform_id", "developer", "developer_id", "franchise_id", "format",
                        "hltb_hours", "cover_image")


def replay_payload(original: Game, events: Sequence[InboxEvent], root_id: int, plays: int) -> Dict[str, Any]:
    """Jogo a criar para a rejogada: dados do original + estado dos eventos, vinculado ao 1º registro."""
    payload = {f: _value(getattr(original, f)) for f in REPLAY_COPIED_FIELDS if getattr(original, f) is not None}
    payload["genre_ids"] = [g.id for g in original.genres]
    payload.update({k: v for k, v in _serialize(propose_state(None, events)).items() if v is not None})
    payload.update(play_type=PlayType.REJOGADA.value, play_count=plays + 1, replay_of_id=root_id)
    return payload


def replay_groups(games: Iterable[Game]) -> Dict[int, List[Game]]:
    """id do registro original -> jogadas do grupo, da mais antiga para a mais recente."""
    groups: Dict[int, List[Game]] = defaultdict(list)
    for g in games:
        groups[g.replay_of_id or g.id].append(g)
    for members in groups.values():
        members.sort(key=lambda g: g.id)
    return groups


def diff_state(current: Game, proposed: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(valores atuais, valores propostos) apenas dos campos que mudam."""
    before, after = {}, {}
    for field in TRACKED_FIELDS:
        old, new = getattr(current, field), proposed[field]
        if _value(old) != _value(new):
            before[field], after[field] = old, new
    return _serialize(before), _serialize(after)


class InboxService:
    @staticmethod
    def import_package(db: Session, package: InboxPackage) -> InboxImportResponse:
        if package.version > INBOX_VERSION:
            raise UnsupportedVersionError(
                f"Versão {package.version} do pacote não suportada (máximo: {INBOX_VERSION}). Atualize o GameRoom."
            )
        received = len(package.events)
        rejected: List[str] = []
        valid: List[InboxEventIn] = []
        for idx, raw in enumerate(package.events, start=1):
            try:
                valid.append(InboxEventIn.model_validate(raw))
            except ValidationError as exc:
                title = raw.get("title") if isinstance(raw, dict) else None
                first = exc.errors()[0]
                field = ".".join(str(p) for p in first.get("loc", ())) or "evento"
                rejected.append(f"Evento {idx}{f' ({title})' if title else ''}: campo '{field}' inválido")

        known = {u for (u,) in db.query(InboxEvent.uuid).filter(InboxEvent.uuid.in_([e.id for e in valid]))}
        imported = duplicates = 0
        for ev in valid:
            if ev.id in known:
                duplicates += 1
                continue
            known.add(ev.id)
            created = ev.created_at
            if created is not None and created.tzinfo is not None:
                created = created.astimezone(timezone.utc).replace(tzinfo=None)
            event_date = ev.date or (created.date() if created else date.today())
            db.add(InboxEvent(
                uuid=ev.id, event_type=ev.type, title=ev.title.strip(),
                platform=(ev.platform or "").strip() or None, game_id=ev.game_id,
                event_date=event_date, device_created_at=created,
                played_hours=ev.played_hours, score=ev.score, difficulty=ev.difficulty,
                notes=(ev.notes or "").strip() or None, status=PENDING,
            ))
            imported += 1
        db.commit()
        return InboxImportResponse(received=received, imported=imported, duplicates=duplicates, rejected=rejected)

    @staticmethod
    def _match_platform(text: Optional[str], platforms: Sequence[Platform], threshold: int) -> Optional[PlatformMatch]:
        if not text:
            return None
        key = match_key(text)
        best: Optional[Tuple[int, Platform]] = None
        for p in platforms:
            score = similarity(key, match_key(p.name))
            if best is None or score > best[0]:
                best = (score, p)
        if best and best[0] >= threshold:
            return PlatformMatch(platform_id=best[1].id, name=best[1].name, similarity=best[0])
        return PlatformMatch(platform_id=None, name=text, similarity=0, is_new=True)

    @staticmethod
    def _candidate(game: Game, score: int, platform_match: Optional[PlatformMatch],
                   events: Sequence[InboxEvent], group: Optional[Sequence[Game]] = None) -> MatchCandidate:
        """`game` deve ser a jogada mais recente do grupo (`group`: todas as jogadas, da 1ª à última)."""
        group = list(group or [game])
        ordered = sorted(events, key=_event_sort_key)
        start = replay_start(game, ordered)
        replay = None
        if start is not None:  # o que veio antes da rejogada ainda vale para este registro
            replay = replay_payload(game, ordered[start:], group[0].id, len(group))
            ordered = ordered[:start]
        current, changes = diff_state(game, propose_state(game, ordered))
        platform_ok = bool(platform_match and platform_match.platform_id
                           and platform_match.platform_id == game.platform_id)
        return MatchCandidate(
            game_id=game.id, title=game.title, platform=game.platform.name if game.platform else None,
            status=_value(game.status), cover_image=game.cover_image, similarity=score,
            platform_matches=platform_ok or platform_match is None, current=current, changes=changes,
            replay=replay,
        )

    @staticmethod
    def pending(db: Session, threshold: int = DEFAULT_THRESHOLD) -> InboxPendingResponse:
        events = db.query(InboxEvent).filter(InboxEvent.status == PENDING).all()
        if not events:
            return InboxPendingResponse(total_events=0, groups=[])

        games = db.query(Game).options(joinedload(Game.platform), joinedload(Game.genres)).all()
        by_id = {g.id: g for g in games}
        groups_by_root = replay_groups(games)
        group_of = {g.id: groups_by_root[g.replay_of_id or g.id] for g in games}
        # Cada grupo de jogadas aparece uma vez, pela jogada mais recente
        heads = [members[-1] for members in groups_by_root.values()]
        game_keys = [(g, match_key(g.title)) for g in heads]
        platforms = db.query(Platform).all()

        grouped: Dict[str, List[InboxEvent]] = defaultdict(list)
        for ev in events:
            if ev.game_id is not None and ev.game_id in by_id:
                key = f"id:{ev.game_id}"
            else:
                key = f"t:{match_key(ev.title)}|{_compact(match_key(ev.platform or ''))}"
            grouped[key].append(ev)

        groups: List[InboxGroup] = []
        for key, evs in grouped.items():
            evs.sort(key=_event_sort_key)
            latest = evs[-1]
            plat = InboxService._match_platform(latest.platform, platforms, threshold)

            if key.startswith("id:"):
                group = group_of[int(key[3:])]
                candidates = [InboxService._candidate(group[-1], 100, plat, evs, group)]
                match = "exact"
            else:
                tkey = match_key(latest.title)
                scored = [(similarity(tkey, gk), g) for g, gk in game_keys]
                scored = [(s, g) for s, g in scored if s >= threshold]
                candidates = [InboxService._candidate(g, s, plat, evs, group_of[g.id]) for s, g in scored]
                candidates.sort(key=lambda c: (c.similarity, c.platform_matches), reverse=True)
                candidates = candidates[:MAX_CANDIDATES]
                exact = [c for c in candidates if c.similarity == 100]
                exact_same_platform = [c for c in exact if c.platform_matches]
                if len(exact) == 1 or len(exact_same_platform) == 1:
                    match = "exact"
                    chosen = exact[0] if len(exact) == 1 else exact_same_platform[0]
                    candidates = [chosen] + [c for c in candidates if c is not chosen]
                elif candidates:
                    match = "confirm"
                else:
                    match = "none"

            new_state = _serialize(propose_state(None, evs))
            new_game = {"title": latest.title, **{k: v for k, v in new_state.items() if v is not None}}
            if plat and plat.platform_id:
                new_game["platform_id"] = plat.platform_id

            groups.append(InboxGroup(
                key=key, title=latest.title, platform=latest.platform,
                events=[InboxEventOut.model_validate(e) for e in evs],
                match=match, candidates=candidates, platform_match=plat, new_game=new_game,
            ))
        groups.sort(key=lambda g: g.events[0].event_date)
        return InboxPendingResponse(total_events=len(events), groups=groups)

    @staticmethod
    def proposal_for(db: Session, event_ids: Iterable[int], game_id: int,
                     threshold: int = DEFAULT_THRESHOLD) -> MatchCandidate:
        """Proposta para um jogo escolhido manualmente na revisão ("Vincular a outro jogo")."""
        events = db.query(InboxEvent).filter(InboxEvent.id.in_(list(event_ids))).all()
        if not events:
            raise InboxEventNotFoundError("Nenhum evento encontrado")
        game = db.query(Game).filter(Game.id == game_id).first()
        if game is None:
            raise InboxEventNotFoundError("Jogo não encontrado")
        root_id = game.replay_of_id or game.id
        group = (db.query(Game).options(joinedload(Game.platform), joinedload(Game.genres))
                 .filter((Game.id == root_id) | (Game.replay_of_id == root_id)).order_by(Game.id).all())
        latest = max(events, key=_event_sort_key)
        plat = InboxService._match_platform(latest.platform, db.query(Platform).all(), threshold)
        score = similarity(match_key(latest.title), match_key(group[-1].title))
        return InboxService._candidate(group[-1], score, plat, events, group)

    @staticmethod
    def resolve(db: Session, event_ids: Iterable[int], action: str, game_id: Optional[int] = None) -> int:
        ids = list(set(event_ids))
        rows = db.query(InboxEvent).filter(InboxEvent.id.in_(ids)).all()
        if not rows:
            raise InboxEventNotFoundError("Nenhum evento encontrado")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        count = 0
        for ev in rows:
            if ev.status != PENDING:
                continue
            ev.status = action
            ev.resolved_at = now
            ev.applied_game_id = game_id if action == APPLIED else None
            count += 1
        db.commit()
        return count

    @staticmethod
    def catalog(db: Session) -> CatalogResponse:
        games = db.query(Game).options(joinedload(Game.platform)).order_by(Game.title).all()
        # Um item por grupo de jogadas (a mais recente), para o app não listar o mesmo jogo várias vezes
        games = sorted((members[-1] for members in replay_groups(games).values()), key=lambda g: (g.title, g.id))
        platforms = [p.name for p in db.query(Platform).order_by(Platform.name)]
        return CatalogResponse(
            exported_at=datetime.now(timezone.utc),
            games=[CatalogGame(id=g.id, title=g.title, platform=g.platform.name if g.platform else None,
                               status=_value(g.status)) for g in games],
            platforms=platforms,
        )


inbox_service = InboxService()
