# Contratos com o app do portátil

O GameRoom e o app Android (`GameRoomApp`, repositório separado) só se conhecem por estes dois formatos JSON. O GameRoom é o dono dos schemas; o app mantém uma cópia e roda os mesmos exemplos nos seus testes.

| Arquivo | Direção | Uso |
|---|---|---|
| `gameroom-inbox.v1.schema.json` | app → GameRoom | Eventos registrados no portátil (Jogando, Zerado, Platinado) |
| `gameroom-catalog.v1.schema.json` | GameRoom → app | Snapshot opcional para sugerir títulos e plataformas e preencher `game_id` |
| `examples/*.json` | — | Exemplos válidos, validados nos testes dos dois lados |

## Regras de evolução

- Campos novos entram sempre como **opcionais**. Quem recebe **ignora campos desconhecidos**.
- `version` só sobe quando houver uma mudança incompatível. O GameRoom recusa (422) pacotes de versão maior do que a que conhece.
- Cada evento é validado isoladamente: um evento inválido é rejeitado com aviso e não impede os demais.

## Semântica do `gameroom-inbox`

- `id`: UUID gerado no app. O GameRoom guarda os UUIDs recebidos, então reimportar um arquivo não duplica nada. Editar no app um evento **já exportado** deve gerar um UUID novo, para que a correção chegue como um evento novo.
- `type`: `playing` (Jogando), `finished` (Zerado) ou `platinum` (Platinado).
- `title` e `platform` são texto livre; o GameRoom faz a correspondência por semelhança na revisão. `game_id` (do catálogo) é opcional e tem precedência quando o jogo ainda existe.
- `date`: dia do evento (`YYYY-MM-DD`); se ausente, vale a data de `created_at`.
- `played_hours` é o **total** acumulado, não o tempo da sessão.
- `score` e `difficulty` vão de 0 a 10.
- Rejogadas: no GameRoom cada jogada é um registro próprio, vinculado ao original. Um `playing` (ou um novo `finished`/`platinum`) num jogo já concluído vira, na revisão, a proposta de um registro novo de rejogada; o app não precisa fazer nada diferente.

## Semântica do `gameroom-catalog`

- Cada jogo aparece **uma vez**, mesmo que tenha rejogadas: o item representa a jogada mais recente (é o `game_id` que o app deve mandar). Um `game_id` de outra jogada do mesmo jogo continua aceito e é levado para a mais recente.

## Entrega

Hoje o app exporta um arquivo `.json` e o GameRoom importa em **Importar → App do portátil** (barra lateral). O mesmo pacote pode ser enviado direto para `POST /api/v1/inbox/import` (caminho previsto para a sincronização pela rede local).
