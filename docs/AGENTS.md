# Guia de Manutencao do Projeto

Este arquivo resume o contexto necessario para mexer no NVRBox sem precisar reler toda a analise tecnica. O backlog oficial fica em `docs/ROADMAP.md`; evite duplicar aqui listas de bugs ou tarefas pendentes.

## Objetivo do sistema

O projeto implementa um NVR residencial simples. Ele usa Flask para o painel web, FFmpeg para consumir cameras RTSP e arquivos `.mp4` segmentados para armazenar as gravacoes.

O uso previsto e local: `localhost` ou rede privada Tailscale. O painel nao foi projetado para exposicao em IP publico, dominio publico ou rede nao confiavel sem autenticacao.

## Estrutura principal

- `servidor.py`: aplicacao Flask do painel web. Lista cameras, mostra status, abre live view, exibe historico, permite download e cadastra/remove cameras.
- `captura.py`: processo continuo de captura. Le `cameras.json`, inicia um FFmpeg por camera e grava segmentos `.mp4`.
- `limpeza.py`: rotina de limpeza automatica. Monitora o uso do disco e apaga os videos mais antigos quando o limite configurado e ultrapassado.
- `iniciar_nvr.sh`: script manual para subir limpeza, captura e painel.
- `cameras.json`: configuracao persistida das cameras.
- `templates/`: HTML renderizado pelo Flask.
- `static/css/`: estilos CSS do painel.
- `docs/ANALISE_PROJETO.md`: visao tecnica consolidada do projeto.
- `docs/ROADMAP.md`: tarefas pendentes e melhorias planejadas.

## Fluxo de execucao

1. `captura.py` carrega as cameras configuradas em `cameras.json`.
2. Para cada camera, o script inicia um processo `ffmpeg`.
3. O FFmpeg grava segmentos de video na pasta de gravacoes.
4. `servidor.py` le o mesmo JSON e mostra cameras, status e arquivos gravados.
5. `limpeza.py` acompanha o armazenamento e remove os videos antigos quando necessario.

## Convencoes de codigo

- Use nomes de funcoes e variaveis em portugues, seguindo o padrao atual.
- Mantenha responsabilidades separadas:
  - painel web em `servidor.py`;
  - captura em `captura.py`;
  - limpeza em `limpeza.py`.
- Prefira `subprocess.Popen` com lista de argumentos para comandos externos.
- Evite `os.system` e comandos shell amplos, principalmente para controle de processos.
- Sempre abra arquivos JSON com `encoding='utf-8'`.
- Centralize caminhos compartilhados quando mexer em gravacoes ou em `cameras.json`.
- Valide dados recebidos de formularios antes de salvar.
- Nao exponha URL RTSP completa na interface, pois ela pode conter usuario e senha.
- Rotas que alteram estado devem usar `POST`.
- Evite `except:` generico; capture excecoes especificas sempre que possivel.

## Convencoes de front-end

- HTML fica em `templates/`.
- CSS fica em `static/css/`.
- Templates Flask devem referenciar CSS com `url_for('static', filename='css/arquivo.css')`.
- Evite CSS inline em templates; use classes no HTML e regras nos arquivos CSS.
- Ao alterar uma tela, confira a tela principal e a tela de detalhe no navegador.

## Verificacoes recomendadas

Use estes comandos antes de considerar uma alteracao concluida:

```bash
python3 -m py_compile servidor.py captura.py limpeza.py
python3 -m json.tool cameras.json
bash -n iniciar_nvr.sh
```

Para validar os templates Flask sem subir o sistema completo, renderize as paginas com contexto de teste ou rode o servidor localmente:

```bash
python3 servidor.py
```

Depois acesse:

```text
http://127.0.0.1:5000
```

## Regra para documentacao

Quando uma tarefa documentada for resolvida, remova ou atualize a entrada correspondente em `docs/ROADMAP.md` e em qualquer outro `.md` que ainda trate a mesma coisa como pendente.
