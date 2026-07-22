# Guia de Manutencao do Projeto

Este arquivo resume o contexto necessario para mexer no NVRBox sem precisar reler toda a documentacao tecnica. O controle oficial de melhorias fica em `docs/MELHORIAS.md`; evite duplicar aqui listas de bugs ou tarefas pendentes.

## Objetivo do sistema

O projeto implementa um NVR residencial simples. Ele usa Flask para o painel web, FFmpeg para consumir cameras RTSP e arquivos `.mp4` segmentados e fragmentados para armazenar as gravacoes.

O uso previsto e local: `localhost`, rede local confiavel ou Tailscale. O painel nao exige login por padrao, mas suporta autenticacao HTTP basica opcional com `NVRBOX_AUTH_USUARIO` e `NVRBOX_AUTH_SENHA`. Ele nao foi projetado para exposicao em IP publico, dominio publico ou rede nao confiavel sem autenticacao.

## Estrutura principal

- `servidor.py`: aplicacao Flask do painel web. Lista cameras, mostra status, abre live view, exibe historico, reproduz gravacoes no navegador, permite download e cadastra/edita/remove cameras.
- `captura.py`: processo continuo de captura. Le `cameras.local.json`, inicia um FFmpeg por camera e grava segmentos `.mp4` fragmentados.
- `limpeza.py`: rotina de limpeza automatica. Monitora o uso do disco e apaga videos antigos elegiveis quando o limite configurado e ultrapassado.
- `config.py`: configuracoes e funcoes compartilhadas, incluindo armazenamento, carregamento/salvamento de cameras, slug, perfis RTSP e mascaramento de RTSP.
- Perfis RTSP conhecidos ficam em `RTSP_PERFIS`, dentro de `config.py`.
- O caminho de gravacoes e resolvido por `encontrar_armazenamento()`: primeiro `NVRBOX_GRAVACOES`, depois a escolha salva em `sistema.json`, depois HD externo gravavel em caminhos Linux/Android conhecidos, e por fim `gravacoes/` local.
- A escolha de armazenamento e feita no painel por `/configurar_armazenamento` e nao deve ser versionada.
- Novas gravacoes usam MP4 fragmentado com `frag_keyframe`, `empty_moov` e `default_base_moof`, para preservar reproducao de segmentos interrompidos antes dos 10 minutos.
- A tela de detalhe valida gravacoes com `ffprobe`; somente arquivos reproduziveis viram botao de play/download.
- A reproducao no painel usa `/video_compativel/<arquivo>`, que entrega WebM gerado sob demanda por FFmpeg. O download continua usando o `.mp4` original.
- `iniciar_nvr.sh`: script manual para subir limpeza, captura e painel.
- `cameras.local.json`: configuracao persistida das cameras, ignorada pelo Git por conter credenciais.
- `cameras.example.json`: modelo versionado sem credenciais reais.
- `sistema.json`: configuracao local criada em runtime para salvar a memoria escolhida pelo usuario. Deve ficar fora do Git.
- `templates/`: HTML renderizado pelo Flask.
- `static/css/`: estilos CSS do painel.
- `docs/DOCUMENTACAO_PROJETO.md`: documentacao tecnica consolidada do projeto.
- `docs/MELHORIAS.md`: checklist unico de melhorias planejadas.

## Fluxo de execucao

1. `config.py` define configuracoes compartilhadas e resolve o armazenamento ativo.
2. `servidor.py` lista memorias gravaveis e permite escolher a memoria de gravacao pelo painel.
3. `captura.py` carrega as cameras configuradas em `cameras.local.json`.
4. Para cada camera, o script inicia um processo `ffmpeg`.
5. O FFmpeg grava segmentos de video fragmentados na pasta de gravacoes escolhida.
6. Se o armazenamento escolhido mudar ou se RTSP/protocolo de uma camera mudar, `captura.py` reinicia os FFmpeg afetados.
7. `servidor.py` lista gravacoes, valida reproducao com `ffprobe` e separa arquivos incompletos.
8. Ao clicar em uma gravacao, o front-end interrompe o live view e abre o player com `/video_compativel/<arquivo>`.
9. `limpeza.py` acompanha o armazenamento ativo e remove videos antigos quando necessario.

## Convencoes de codigo

- Use nomes de funcoes e variaveis em portugues, seguindo o padrao atual.
- Mantenha responsabilidades separadas:
  - painel web em `servidor.py`;
  - captura em `captura.py`;
  - limpeza em `limpeza.py`.
- Prefira `subprocess.Popen` com lista de argumentos para comandos externos.
- Evite `os.system` e comandos shell amplos, principalmente para controle de processos.
- Sempre abra arquivos JSON com `encoding='utf-8'`.
- Centralize caminhos compartilhados quando mexer em gravacoes ou em `cameras.local.json`.
- Use slugs sanitizados para rotas, nomes de arquivos e logs.
- Valide dados recebidos de formularios antes de salvar.
- No cadastro e na edicao, o painel recebe nome, IP, senha, perfil RTSP e campos avancados opcionais; a URL RTSP e montada no backend.
- Novas cameras sao testadas com `ffprobe` antes de salvar, salvo quando `NVRBOX_TESTAR_RTSP_CADASTRO=0`.
- Nao exponha URL RTSP completa na interface, pois ela pode conter usuario e senha.
- Rotas que alteram estado devem usar `POST`.
- Evite `except:` generico; capture excecoes especificas sempre que possivel.
- Ao mexer na captura, preserve a gravacao fragmentada. Sem isso, uma queda de energia antes do fechamento do segmento pode deixar o `.mp4` antigo sem indice final e sem reproducao no navegador.
- Ao mexer na reproducao de gravacoes, preserve a rota `/video_compativel/<arquivo>` ou ofereca alternativa equivalente. Alguns `.mp4` baixam e abrem em player externo, mas nao tocam diretamente no `<video>` do navegador.

## Convencoes de front-end

- HTML fica em `templates/`.
- CSS fica em `static/css/`.
- Templates Flask devem referenciar CSS com `url_for('static', filename='css/arquivo.css')`.
- Evite CSS inline em templates; use classes no HTML e regras nos arquivos CSS.
- Para a lista de gravacoes, mantenha botoes reais com `data-video` e listeners JavaScript. Evite voltar para `onclick` inline, porque isso dificulta diagnosticar clique e troca entre live view e gravacao.
- Ao alterar uma tela, confira a tela principal e a tela de detalhe no navegador.

## Verificacoes recomendadas

Use estes comandos antes de considerar uma alteracao concluida:

```bash
python3 -m py_compile servidor.py captura.py limpeza.py config.py
python3 -m unittest
python3 -m json.tool cameras.example.json
test ! -f cameras.local.json || python3 -m json.tool cameras.local.json
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

Quando uma tarefa documentada for resolvida, marque ou atualize a entrada correspondente em `docs/MELHORIAS.md` e evite manter a mesma pendencia duplicada em outros arquivos `.md`.
