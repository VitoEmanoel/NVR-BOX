# Analise do Projeto NVRBox

## Visao geral

O NVRBox e um prototipo de NVR residencial com arquitetura simples e funcional. O sistema usa Flask para o painel web, FFmpeg para captura RTSP e arquivos `.mp4` segmentados e fragmentados para armazenar as gravacoes.

A proposta atual e adequada para uso local, estudo e demonstracao de TCC. O projeto ja recebeu melhorias importantes de confiabilidade e usabilidade, incluindo configuracao de armazenamento pelo painel, cadastro simplificado de cameras, teste RTSP antes de salvar novas cameras, mascaramento de RTSP na interface, separacao de HTML/CSS, slugs seguros, escrita atomica de JSON, MP4 fragmentado para gravacoes curtas, validacao de arquivos gravados, autenticacao opcional, rotacao simples de logs do FFmpeg e arquivo local de cameras fora do Git. As proximas evolucoes mais importantes sao melhorar mensagens operacionais, validar melhor Android/TV Box e preparar operacao como servico. As tarefas acionaveis ficam centralizadas em `docs/ROADMAP.md`.

## Arquitetura atual

O projeto esta dividido em tres processos principais:

- `servidor.py`: painel web em Flask.
- `captura.py`: captura continua usando FFmpeg.
- `limpeza.py`: limpeza automatica dos videos antigos.
- `config.py`: configuracoes e funcoes compartilhadas entre painel, captura e limpeza.

Arquivos e pastas de apoio:

- `cameras.local.json`: configuracao local das cameras, ignorada pelo Git porque pode conter credenciais.
- `cameras.example.json`: modelo versionado sem credenciais reais.
- `iniciar_nvr.sh`: inicializacao manual dos processos com controle por arquivos PID.
- `templates/`: HTML das telas renderizadas pelo Flask.
- `static/css/`: CSS separado dos templates.
- `docs/`: documentacao tecnica e roadmap.
- `sistema.json`: arquivo local criado em runtime para salvar a memoria escolhida pelo usuario.

Fluxo principal:

1. `config.py` define caminhos, perfis RTSP e opcoes compartilhadas.
2. `servidor.py` lista memorias gravaveis e permite escolher onde gravar.
3. `captura.py` le `cameras.local.json`.
4. Para cada camera configurada, inicia um processo `ffmpeg`.
5. O FFmpeg grava segmentos `.mp4` na pasta escolhida.
6. Se o armazenamento for alterado no painel, `captura.py` reinicia os FFmpeg para usar o novo caminho.
7. `servidor.py` lista cameras, status e arquivos gravados no armazenamento ativo.
8. `limpeza.py` monitora o uso do armazenamento ativo e remove videos antigos quando necessario.

## Estado atual

O projeto ja entrega as funcoes centrais de um painel NVR simples:

- cadastro simplificado de cameras por nome, IP, senha e perfil RTSP;
- listagem de cameras;
- status online/offline;
- live view via MJPEG;
- historico de gravacoes;
- filtro por data;
- download de videos;
- limpeza automatica de gravacoes antigas;
- configuracao central do caminho de gravacoes, com selecao de armazenamento pelo painel;
- MP4 fragmentado para preservar trechos curtos em paradas antes do fechamento normal;
- separacao visual entre gravacoes reproduziveis e arquivos incompletos no historico;
- teste real de RTSP com `ffprobe` antes de salvar novas cameras;
- remocao de cameras por `POST`;
- mascaramento de credenciais RTSP na interface;
- arquivo real de cameras fora do Git, com exemplo sem segredo;
- slugs sanitizados usados nas rotas;
- escrita atomica dos arquivos JSON salvos pelo sistema;
- mensagens de erro e sucesso exibidas no painel;
- autenticacao HTTP basica opcional via `NVRBOX_AUTH_USUARIO` e `NVRBOX_AUTH_SENHA`;
- uso do campo UDP/TCP na captura e no live stream;
- rotacao simples de logs do FFmpeg por tamanho;
- script de inicializacao com controle por arquivos PID;
- `requirements.txt` com dependencia Flask.

A interface tambem ja foi organizada em HTML e CSS separados:

- `templates/index.html` usa `static/css/index.css`;
- `templates/detalhe.html` usa `static/css/detalhe.css`.

## Pontos fortes

- A separacao entre painel, captura e limpeza deixa as responsabilidades claras.
- FFmpeg e uma escolha adequada para RTSP, gravacao e segmentacao de video.
- A segmentacao em arquivos de 10 minutos facilita navegacao, download e limpeza.
- O MP4 fragmentado melhora a chance de reproducao quando um segmento e interrompido antes dos 10 minutos.
- O codigo ainda e pequeno e facil de entender.
- A configuracao em JSON simplifica o prototipo e facilita edicao manual.
- A interface cobre as operacoes principais do sistema.
- O cadastro simplificado reduz erro de configuracao para usuarios nao tecnicos.
- A escolha de armazenamento pelo painel atende TV Box, PC Linux e Android com multiplas memorias.

## Pontos de atencao

### Seguranca

O painel nao exige login por padrao, por decisao de projeto. Essa escolha e aceitavel somente se o acesso ficar restrito a `localhost`, rede local confiavel ou Tailscale. Para redes compartilhadas, o projeto suporta autenticacao HTTP basica opcional com `NVRBOX_AUTH_USUARIO` e `NVRBOX_AUTH_SENHA`.

O sistema nao deve ser publicado em:

- IP publico;
- dominio publico;
- rede Wi-Fi de terceiros;
- porta aberta no roteador;
- proxy reverso publico sem autenticacao.

Mesmo em rede privada, ainda e importante mascarar URLs RTSP na interface e evitar que usuario e senha aparecam em tela ou logs. A interface ja mascara a URL RTSP, e a configuracao real fica em `cameras.local.json`, arquivo ignorado pelo Git. O repositorio mantem `cameras.example.json` como modelo sem credenciais reais.

### Controle de processos

O script de inicializacao controla os processos principais por arquivos PID. O motor de captura tambem encerra os processos FFmpeg filhos quando uma camera e removida de `cameras.local.json` ou quando o processo recebe sinal de encerramento.

O proximo passo recomendado e evoluir esse controle para `systemd`, com restart automatico e logs separados por servico.

### Caminhos de gravacao

Painel, captura e limpeza usam o mesmo caminho definido em `config.py`. O usuario pode escolher o armazenamento pelo painel, e a escolha fica salva em `sistema.json`. O sistema tambem respeita `NVRBOX_GRAVACOES` como override de ambiente e lista caminhos comuns de Linux, TV Box e Android, como `/media`, `/mnt`, `/storage`, `/run/media`, `/sdcard` e `/storage/emulated/0`.

Quando o armazenamento muda, a captura encerra os processos FFmpeg ativos e reinicia a gravacao no novo caminho. Videos antigos permanecem no armazenamento anterior; hoje o sistema nao move gravacoes automaticamente.

### Dados e validacao

O cadastro de cameras monta a URL RTSP no backend a partir de nome, IP, senha, usuario, porta e perfil RTSP. O fluxo padrao pede nome, IP, senha e perfil, mantendo campos avancados para modelos fora do padrao. O sistema testa o stream RTSP com `ffprobe` antes de salvar novas cameras, comportamento que pode ser desligado com `NVRBOX_TESTAR_RTSP_CADASTRO=0`.

O campo `protocolo` e salvo no JSON e usado pelo FFmpeg na captura e no live stream.

O carregamento e salvamento de JSON usa `encoding='utf-8'`. A escrita de configuracoes e cameras e atomica, com arquivo temporario e `os.replace`. Ainda falta exibir erro mais claro no painel quando o JSON local estiver invalido.

Os slugs de camera sao sanitizados para usar caracteres seguros em rotas, nomes de arquivo e logs.

### Tratamento de erros

Ainda existem alguns pontos onde o tratamento de erro pode ser refinado, mas os caminhos principais do painel, live view e listagem de gravacoes usam excecoes mais especificas.

### Reproducao de gravacoes

A tela de detalhe da camera usa `ffprobe` para validar cada `.mp4` antes de liberar reproducao. Arquivos reproduziveis exibem duracao e tamanho; arquivos incompletos ou invalidos aparecem separados para nao confundir falha de gravacao antiga com falha do player. Novas gravacoes usam MP4 fragmentado para preservar trechos interrompidos antes dos 10 minutos.

### Limpeza de gravacoes

A limpeza automatica remove o arquivo `.mp4` mais antigo quando o disco passa do limite configurado. Para reduzir risco de apagar um segmento ainda ativo, ela ignora arquivos modificados recentemente. A captura usa MP4 fragmentado para que um segmento interrompido antes dos 10 minutos continue com chance alta de reproducao.

## Operacao

Hoje o sistema pode ser executado manualmente com processos separados:

```bash
python3 limpeza.py
python3 captura.py
python3 servidor.py
```

Para uso mais confiavel, o projeto deve evoluir para gerenciamento por `systemd` ou mecanismo equivalente, com restart automatico, logs separados e permissoes bem definidas.

## Verificacoes basicas

Comandos uteis para validar alteracoes:

```bash
python3 -m py_compile servidor.py captura.py limpeza.py config.py
python3 -m json.tool cameras.example.json
test ! -f cameras.local.json || python3 -m json.tool cameras.local.json
bash -n iniciar_nvr.sh
```

Essas verificacoes cobrem sintaxe Python, validade do JSON e sintaxe do script shell. Elas nao substituem testes funcionais com cameras reais, gravacao em disco, reproducao pelo painel e limpeza automatica.

Tambem e util validar rotas Flask com `test_client` para cobrir renderizacao da home, detalhe de camera, validacao de formulario e download inexistente sem iniciar o FFmpeg.

## Conclusao

O NVRBox tem uma base tecnica coerente para um prototipo residencial: Flask resolve bem o painel, FFmpeg resolve a captura RTSP e a separacao dos processos facilita entender o sistema.

O foco das proximas evolucoes deve ser tratar falhas de JSON com mais clareza no painel, validar melhor armazenamento em Android/TV Box e preparar operacao como servico. O acompanhamento dessas tarefas deve ser feito em `docs/ROADMAP.md`.
